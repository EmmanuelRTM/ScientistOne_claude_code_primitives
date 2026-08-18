#!/usr/bin/env python3
"""Verify Sources (deterministic half): check claims.jsonl against artifacts.

  numerical      -> resolve score/config tags, compare sentence numbers +-5%
                    (paper's tolerance); log tags -> file+line must exist
  citation       -> key must exist in bibliography.jsonl; entailment judgment
                    is left to the claim-verifier agent (status PENDING_LLM)
  methodological -> referenced artifacts must exist; method-code alignment is
                    left to the claim-verifier agent (status PENDING_LLM)
  untagged       -> FAIL (no declared evidence source)

LLM verdicts are quote-grounded: a PASS/PARTIAL judgment on a citation or
methodological claim must carry a "quote" field that is a verbatim excerpt of
the claim's evidence source (literature note / solution.py / solve.log). A
verdict whose quote is missing or not found verbatim is downgraded to FAIL
with a QUOTE-CHECK detail — an ungrounded judgment does not count.

Rewrites claims.jsonl in place with updated status/detail.
Usage: python3 .claude/scripts/verify_claims.py <run-dir-or-run-id>
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evtags import (check_log_ref, check_quote, load_bibliography, needs_quote,
                    numbers_in, numbers_match, resolve_json_pointer)

ROOT = Path(__file__).resolve().parents[2]
NUM_TOL = 0.05  # +-5% per the Chain-of-Evidence protocol


def verify_claim(run_dir: Path, bib: dict, claim: dict) -> None:
    tags = [t.split(":", 2) for t in claim["evidence_tags"]]  # [EV, type, ref]
    if not tags:
        claim["status"] = "FAIL"
        claim["detail"] = "no evidence tag declared"
        return

    details, failed, needs_llm = [], False, False
    for _, tag_type, ref in tags:
        if tag_type in ("score", "config"):
            value, err = resolve_json_pointer(run_dir, ref)
            if err:
                failed = True
                details.append(err)
                continue
            nums = numbers_in(claim["text"])
            if nums and not any(numbers_match(n, value, NUM_TOL) for n in nums):
                failed = True
                details.append(f"number mismatch: artifact={value}, sentence={nums}")
            else:
                details.append(f"{tag_type} ok ({value})")
        elif tag_type == "log":
            ok, detail = check_log_ref(run_dir, ref)
            failed |= not ok
            details.append(detail)
        elif tag_type == "cite":
            if ref not in bib:
                failed = True
                details.append(f"citation key '{ref}' not in bibliography")
            else:
                needs_llm = True
                details.append(f"cite '{ref}' resolved; entailment pending LLM")
        elif tag_type == "artifact":
            if (run_dir / ref).exists():
                details.append("artifact exists")
                if claim["type"] == "methodological":
                    needs_llm = True
            else:
                failed = True
                details.append(f"artifact missing: {ref}")
        else:
            failed = True
            details.append(f"unknown tag type {tag_type}")

    if claim["type"] == "methodological" and not failed:
        needs_llm = True
    # conclusion claims (CoE taxonomy: "outperforms X by Y") pass their
    # per-tag numeric checks above, but whether the comparison actually
    # FOLLOWS from those numbers is a derivation judgment -> LLM
    if claim["type"] == "conclusion" and not failed:
        needs_llm = True

    claim["status"] = "FAIL" if failed else ("PENDING_LLM" if needs_llm else "PASS")
    claim["detail"] = "; ".join(details)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("run")
    args = p.parse_args()
    run_dir = Path(args.run)
    if not run_dir.is_dir():
        run_dir = ROOT / "workspace" / "runs" / args.run
    claims_file = run_dir / "paper" / "claims.jsonl"
    if not claims_file.is_file():
        print(f"ERROR: {claims_file} not found (run extract_claims.py first)", file=sys.stderr)
        return 1

    bib = load_bibliography(run_dir)
    claims = [json.loads(l) for l in claims_file.read_text().splitlines() if l.strip()]
    for claim in claims:
        old_status, old_detail = claim["status"], claim.get("detail", "")
        verify_claim(run_dir, bib, claim)
        # deterministic re-verification never downgrades a definitive verdict
        # back to PENDING_LLM — only a deterministic FAIL overrides it
        if claim["status"] == "PENDING_LLM" and old_status in ("PASS", "FAIL", "PARTIAL"):
            claim["status"], claim["detail"] = old_status, old_detail
        # an LLM PASS/PARTIAL only counts if its quote is a verbatim excerpt
        # of the evidence source — the verifier must re-judge or FAIL honestly
        if needs_quote(claim):
            ok, qdetail = check_quote(run_dir, claim)
            if not ok:
                claim["status"] = "FAIL"
                claim["detail"] = f"QUOTE-CHECK: {qdetail}; discarded verdict: {claim['detail']}"
    claims_file.write_text("".join(json.dumps(c) + "\n" for c in claims))

    counts = {}
    for c in claims:
        counts[c["status"]] = counts.get(c["status"], 0) + 1
    print(f"Verified {len(claims)} claims: " +
          ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    for c in claims:
        if c["status"] == "FAIL":
            print(f"  FAIL {c['id']} (L{c['line']}): {c['detail']}")
    return 1 if counts.get("FAIL") else 0


if __name__ == "__main__":
    sys.exit(main())
