#!/usr/bin/env python3
"""Stop gate for the claim-verifier agent: it may not finish while claims in
paper/claims.jsonl still lack a definitive verdict, or while the verification
report is missing. Exit 2 blocks the stop and feeds the unfinished-claim list
back to the agent. Respects stop_hook_active to avoid infinite loops."""
import json
import os
import sys
from pathlib import Path

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
    report = run / "paper" / "verification-report.md"

    problems = []
    if unresolved:
        problems.append(f"claims without a definitive verdict (PASS/FAIL/PARTIAL): "
                        f"{unresolved}")
    if not report.is_file():
        problems.append("paper/verification-report.md has not been written")
    if problems:
        print("Verification incomplete — " + "; ".join(problems) +
              ". Resolve every claim in paper/claims.jsonl (update its status and "
              "prefix detail with 'LLM:'), write verification-report.md including "
              "a 'Method-Code Alignment: PASS|FAIL' line, then finish.",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
