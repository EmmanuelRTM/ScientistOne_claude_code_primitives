#!/usr/bin/env python3
"""Stop gate for the claim-verifier agent: it may not finish while claims in
paper/claims.jsonl still lack a definitive verdict, while an LLM PASS/PARTIAL
verdict lacks a verbatim supporting quote from its evidence source, or while
the verification report is missing. Exit 2 blocks the stop and feeds the
unfinished-claim list back to the agent. Respects stop_hook_active to avoid
infinite loops."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from evtags import check_quote, needs_quote  # noqa: E402

DEFINITIVE = {"PASS", "FAIL", "PARTIAL"}


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    if payload.get("stop_hook_active"):
        return 0  # already continued once for this stop; don't loop forever

    root = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    active = root / "workspace" / "runs" / "ACTIVE_RUN"
    if not active.is_file():
        return 0
    run = root / "workspace" / "runs" / active.read_text().strip()
    claims_file = run / "paper" / "claims.jsonl"
    if not claims_file.is_file():
        return 0  # nothing extracted yet; not this gate's business

    claims = [json.loads(l) for l in claims_file.read_text().splitlines() if l.strip()]
    unresolved = [c["id"] for c in claims if c.get("status") not in DEFINITIVE]
    # a QUOTE-CHECK downgrade means a verdict was discarded, not resolved:
    # the verifier must re-judge with a genuine quote or record an honest FAIL
    discarded = [c["id"] for c in claims
                 if str(c.get("detail", "")).startswith("QUOTE-CHECK:")]
    ungrounded = []
    for c in claims:
        if needs_quote(c):
            ok, detail = check_quote(run, c)
            if not ok:
                ungrounded.append(f"{c['id']} ({detail})")
    report = run / "paper" / "verification-report.md"

    problems = []
    if unresolved:
        problems.append(f"claims without a definitive verdict (PASS/FAIL/PARTIAL): "
                        f"{unresolved}")
    if ungrounded:
        problems.append("LLM PASS/PARTIAL verdicts without a verbatim supporting "
                        f"quote from their evidence source: {ungrounded}")
    if discarded:
        problems.append("verdicts discarded by QUOTE-CHECK (re-judge with a real "
                        f"quote, or record an honest 'LLM: FAIL'): {discarded}")
    if not report.is_file():
        problems.append("paper/verification-report.md has not been written")
    if problems:
        print("Verification incomplete — " + "; ".join(problems) +
              ". Resolve every claim in paper/claims.jsonl (update its status, "
              "prefix detail with 'LLM:', and for PASS/PARTIAL on citation/"
              "methodological claims set 'quote' to a verbatim excerpt of the "
              "evidence source), write verification-report.md including a "
              "'Method-Code Alignment: PASS|FAIL' line, then finish.",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
