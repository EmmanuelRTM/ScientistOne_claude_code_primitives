#!/usr/bin/env python3
"""GROUND stage (deterministic): validate every evidence tag in the research
representation against the run's raw materials.

Usage: python3 .claude/scripts/ground_check.py <run-dir-or-run-id> [--file paper/research-representation.md]

Writes paper/ground-report.json. Exit 1 if grounding ratio < 0.85.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evtags import (SENTENCE_SPLIT_RE, find_tags, load_bibliography, numbers_in,
                    numbers_match, check_log_ref, resolve_json_pointer)

ROOT = Path(__file__).resolve().parents[2]
FORMAT_TOL = 0.005  # 0.5% formatting/rounding tolerance
MIN_RATIO = 0.85


def resolve_run_dir(arg: str) -> Path:
    p = Path(arg)
    if p.is_dir():
        return p.resolve()
    return (ROOT / "workspace" / "runs" / arg).resolve()


def check_tag(run_dir: Path, bib: dict, tag_type: str, ref: str, sentence: str):
    """Return (verdict, detail): SUPPORTED | PARTIAL | UNSUPPORTED."""
    if tag_type in ("score", "config"):
        value, err = resolve_json_pointer(run_dir, ref)
        if err:
            return "UNSUPPORTED", err
        nums = numbers_in(sentence)
        if not nums:
            return "SUPPORTED", f"artifact value {value} (no number restated in sentence)"
        if any(numbers_match(n, value, FORMAT_TOL) for n in nums):
            return "SUPPORTED", f"sentence number matches artifact value {value}"
        return "UNSUPPORTED", (f"MISMATCH: artifact value {value}, sentence numbers {nums}")
    if tag_type == "log":
        ok, detail = check_log_ref(run_dir, ref)
        return ("SUPPORTED" if ok else "UNSUPPORTED"), detail
    if tag_type == "cite":
        entry = bib.get(ref)
        if entry is None:
            return "UNSUPPORTED", f"citation key '{ref}' not in bibliography.jsonl"
        if entry.get("read_status") == "abstract-only":
            return "PARTIAL", "citation resolved but paper read abstract-only"
        return "SUPPORTED", "citation resolved (read in full)"
    if tag_type == "artifact":
        fp = run_dir / ref
        if fp.is_file() or fp.is_dir():
            return "SUPPORTED", "artifact exists"
        return "UNSUPPORTED", f"artifact not found: {ref}"
    return "UNSUPPORTED", f"unknown tag type '{tag_type}'"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("run")
    p.add_argument("--file", default="paper/research-representation.md")
    args = p.parse_args()

    run_dir = resolve_run_dir(args.run)
    doc_path = run_dir / args.file
    if not doc_path.is_file():
        print(f"ERROR: {doc_path} not found", file=sys.stderr)
        return 1

    text = doc_path.read_text()
    bib = load_bibliography(run_dir)
    checks = []

    # Track ASSUMPTIONS block: sentences under a header containing 'ASSUMPTION'
    current_header = ""
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if stripped.startswith("#"):
            current_header = stripped.lstrip("#").strip().upper()
            continue
        if not stripped or stripped.startswith(("|", "<!--")):
            continue
        in_assumptions = "ASSUMPTION" in current_header
        for sentence in SENTENCE_SPLIT_RE.split(stripped):
            sentence = sentence.strip()
            if not sentence:
                continue
            tags = find_tags(sentence)
            if tags:
                for tag_type, ref in tags:
                    verdict, detail = check_tag(run_dir, bib, tag_type, ref, sentence)
                    checks.append({"line": lineno, "sentence": sentence,
                                   "tag": f"[EV:{tag_type}:{ref}]",
                                   "verdict": verdict, "detail": detail})
            elif not in_assumptions and numbers_in(sentence):
                checks.append({"line": lineno, "sentence": sentence, "tag": None,
                               "verdict": "UNSUPPORTED",
                               "detail": "factual number without evidence tag"})

    supported = sum(1 for c in checks if c["verdict"] == "SUPPORTED")
    partial = sum(1 for c in checks if c["verdict"] == "PARTIAL")
    total = len(checks)
    ratio = round((supported + 0.5 * partial) / total, 4) if total else 1.0

    report = {
        "file": args.file,
        "total_checks": total,
        "supported": supported,
        "partial": partial,
        "unsupported": total - supported - partial,
        "grounding_ratio": ratio,
        "min_ratio": MIN_RATIO,
        "checks": checks,
    }
    out = run_dir / "paper" / "ground-report.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")

    print(f"GROUND: {supported} supported, {partial} partial, "
          f"{report['unsupported']} unsupported of {total} checks "
          f"-> grounding ratio {ratio}")
    for c in checks:
        if c["verdict"] != "SUPPORTED":
            print(f"  [{c['verdict']}] L{c['line']}: {c['detail']}")
    if ratio < MIN_RATIO:
        print(f"FAIL: grounding ratio {ratio} < {MIN_RATIO} — RESOLVE stage must fix "
              f"unsupported claims before composing.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
