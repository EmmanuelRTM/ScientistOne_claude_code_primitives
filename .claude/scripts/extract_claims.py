#!/usr/bin/env python3
"""Extract Claims: parse the paper draft into paper/claims.jsonl.

A claim is a sentence that carries >=1 evidence tag OR states a factual
number/citation. Claim type is inferred from its tags:
  score/log tags        -> numerical
  cite tags             -> citation
  artifact/config tags, or Method-section sentence -> methodological

Usage: python3 .claude/scripts/extract_claims.py <run-dir-or-run-id> [--file paper/draft.md]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evtags import SENTENCE_SPLIT_RE, find_tags, numbers_in

ROOT = Path(__file__).resolve().parents[2]


def infer_type(tags, section: str) -> str:
    types = {t for t, _ in tags}
    if "score" in types or "log" in types:
        return "numerical"
    if "cite" in types:
        return "citation"
    if types & {"artifact", "config"}:
        return "methodological"
    return "methodological" if "METHOD" in section.upper() else "numerical"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("run")
    p.add_argument("--file", default="paper/draft.md")
    args = p.parse_args()

    run_dir = Path(args.run)
    if not run_dir.is_dir():
        run_dir = ROOT / "workspace" / "runs" / args.run
    doc = run_dir / args.file
    if not doc.is_file():
        print(f"ERROR: {doc} not found", file=sys.stderr)
        return 1

    claims = []
    section = "PREAMBLE"
    in_fence = False
    counter = 0
    for lineno, line in enumerate(doc.read_text().splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if stripped.startswith("#"):
            section = stripped.lstrip("#").strip()
            continue
        if not stripped or stripped.startswith(("|", "<!--")):
            continue
        for sentence in SENTENCE_SPLIT_RE.split(stripped):
            sentence = sentence.strip()
            if not sentence:
                continue
            tags = find_tags(sentence)
            if not tags and not numbers_in(sentence):
                continue
            if "BIBLIOGRAPHY" in section.upper() or "REFERENCES" in section.upper():
                continue  # bib entries are validated by bib_validate/chain_of_evidence
            counter += 1
            claims.append({
                "id": f"C{counter:03d}",
                "type": infer_type(tags, section),
                "text": sentence,
                "evidence_tags": [f"EV:{t}:{r}" for t, r in tags],
                "section": section,
                "line": lineno,
                "status": "PENDING",
                "detail": "",
            })

    out = run_dir / "paper" / "claims.jsonl"
    out.parent.mkdir(exist_ok=True)
    out.write_text("".join(json.dumps(c) + "\n" for c in claims))
    n_untagged = sum(1 for c in claims if not c["evidence_tags"])
    print(f"Extracted {len(claims)} claims ({n_untagged} without evidence tags) -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
