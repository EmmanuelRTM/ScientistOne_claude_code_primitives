#!/usr/bin/env python3
"""Chain-of-Evidence final audit (the paper's four integrity checks):

  1. Score Verification    headline score in final paper re-derivable from
                           best/eval.json (+-0.5% formatting tolerance)
  2. Reference Verification every [EV:cite:] key in the final paper resolves in
                           bibliography.jsonl; bibliography itself validates
  3. Specification Violation the selected branch's audit.md verdict is PASS
  4. Method-Code Alignment  attested by the claim-verifier agent in
                           verification-report.md (LLM-verified; reported here)

Plus tag-coverage stats. Appends the PASS/FAIL table to
paper/verification-report.md. Exit 1 if any deterministic check FAILs.

Usage: python3 .claude/scripts/chain_of_evidence.py <run-dir-or-run-id>
"""
import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evtags import find_tags, load_bibliography, numbers_in, numbers_match

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("run")
    args = p.parse_args()
    run_dir = Path(args.run)
    if not run_dir.is_dir():
        run_dir = ROOT / "workspace" / "runs" / args.run

    paper = run_dir / "final" / "paper.md"
    if not paper.is_file():
        paper = run_dir / "paper" / "draft.md"
    results = []  # (check, PASS/FAIL/INFO, detail)

    # --- 1. Score Verification -------------------------------------------
    best_eval = run_dir / "best" / "eval.json"
    if not paper.is_file():
        results.append(("Score Verification", "FAIL", "no paper found"))
    elif not best_eval.is_file():
        results.append(("Score Verification", "FAIL", "best/eval.json missing"))
    else:
        score = json.loads(best_eval.read_text()).get("score")
        text = paper.read_text()
        score_tag_sentences = [l for l in text.splitlines()
                               if any(t == "score" for t, _ in find_tags(l))]
        nums = [n for l in score_tag_sentences for n in numbers_in(l)]
        # any sentence citing the headline artifact must not contradict it
        headline_tag = "best/eval.json#score"
        contradictions = []
        for line in text.splitlines():
            if any(t == "score" and r == headline_tag for t, r in find_tags(line)):
                line_nums = numbers_in(line)
                if line_nums and not any(numbers_match(n, score, 0.005) for n in line_nums):
                    contradictions.append(line_nums)
        if score is None:
            results.append(("Score Verification", "FAIL", "best/eval.json has no score"))
        elif contradictions:
            results.append(("Score Verification", "FAIL",
                            f"sentence(s) tagged {headline_tag} state {contradictions[:3]} "
                            f"but the artifact says {score}"))
        elif nums and any(numbers_match(n, score, 0.005) for n in nums):
            results.append(("Score Verification", "PASS",
                            f"headline score {score} restated in paper"))
        elif not nums:
            results.append(("Score Verification", "FAIL",
                            "no score-tagged sentence with a number found in paper"))
        else:
            results.append(("Score Verification", "FAIL",
                            f"paper numbers {nums[:5]} do not match best score {score}"))

    # --- 2. Reference Verification ---------------------------------------
    bib = load_bibliography(run_dir)
    cited = {ref for t, ref in find_tags(paper.read_text() if paper.is_file() else "")
             if t == "cite"}
    unknown = sorted(k for k in cited if k not in bib)
    bibv = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "bib_validate.py"), str(run_dir)],
        capture_output=True, text=True)
    if unknown:
        results.append(("Reference Verification", "FAIL",
                        f"unresolvable citation keys: {unknown}"))
    elif bibv.returncode != 0:
        results.append(("Reference Verification", "FAIL",
                        "bibliography.jsonl invalid: " + bibv.stdout.strip()[:200]))
    else:
        results.append(("Reference Verification", "PASS",
                        f"{len(cited)} distinct citations, all resolve; "
                        f"bibliography valid ({len(bib)} entries)"))

    # --- 3. Specification Violation --------------------------------------
    selected = run_dir / "best" / "SELECTED.json"
    if not selected.is_file():
        results.append(("Specification Violation", "FAIL", "best/SELECTED.json missing"))
    else:
        sel = json.loads(selected.read_text())
        audit = run_dir / "iterations" / sel.get("iteration", "") / "branches" / \
            sel.get("branch", "") / "audit.md"
        if not audit.is_file():
            results.append(("Specification Violation", "FAIL",
                            f"audit.md missing for selected branch {sel}"))
        else:
            first_verdict = ""
            for line in audit.read_text().splitlines():
                if "VERDICT" in line.upper() or line.strip().upper().startswith(("PASS", "FAIL")):
                    first_verdict = line.strip()
                    break
            if "PASS" in first_verdict.upper() and "FAIL" not in first_verdict.upper():
                results.append(("Specification Violation", "PASS",
                                f"selected {sel.get('iteration')}/{sel.get('branch')} audit: PASS"))
            else:
                results.append(("Specification Violation", "FAIL",
                                f"selected branch audit verdict: '{first_verdict or 'not found'}'"))

    # --- 4. Method-Code Alignment (LLM-attested) --------------------------
    vr = run_dir / "paper" / "verification-report.md"
    if vr.is_file() and "METHOD-CODE ALIGNMENT: PASS" in vr.read_text().upper():
        results.append(("Method-Code Alignment", "PASS",
                        "attested by claim-verifier in verification-report.md"))
    elif vr.is_file():
        results.append(("Method-Code Alignment", "FAIL",
                        "no 'Method-Code Alignment: PASS' attestation in verification-report.md"))
    else:
        results.append(("Method-Code Alignment", "FAIL", "verification-report.md missing"))

    # --- claims + coverage stats ------------------------------------------
    claims_file = run_dir / "paper" / "claims.jsonl"
    if claims_file.is_file():
        claims = [json.loads(l) for l in claims_file.read_text().splitlines() if l.strip()]
        bad = [c["id"] for c in claims if c["status"] not in ("PASS", "PARTIAL")]
        status = "PASS" if not bad else "FAIL"
        results.append(("Claim Verdicts", status,
                        f"{len(claims)} claims; unresolved/failed: {bad or 'none'}"))
    tag_count = len(find_tags(paper.read_text())) if paper.is_file() else 0
    results.append(("Tag Coverage", "INFO", f"{tag_count} evidence tags in {paper.name}"))

    # --- report -------------------------------------------------------------
    width = max(len(r[0]) for r in results)
    lines = ["", "## Chain-of-Evidence Audit",
             f"_{datetime.datetime.now().isoformat(timespec='seconds')} — {paper.relative_to(run_dir) if paper.is_file() else 'no paper'}_", ""]
    ok = True
    for name, verdict, detail in results:
        print(f"{name:<{width}}  {verdict:<4}  {detail}")
        lines.append(f"- **{name}**: {verdict} — {detail}")
        ok &= verdict != "FAIL"
    if vr.parent.is_dir():
        with (vr if vr.is_file() else vr).open("a") as fh:
            fh.write("\n".join(lines) + "\n")
    print("\nCHAIN-OF-EVIDENCE: " + ("ALL PASS" if ok else "FAILURES PRESENT"))
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:  # output piped to head etc. — not an error
        sys.exit(0)
