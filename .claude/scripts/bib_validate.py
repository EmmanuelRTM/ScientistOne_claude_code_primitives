#!/usr/bin/env python3
"""Validate bibliography.jsonl: schema, unique keys, provenance, local notes.

Usage: python3 .claude/scripts/bib_validate.py <run-dir-or-run-id>
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = ["key", "title", "authors", "year", "provenance", "read_status", "local_note"]
PROVENANCE = {"websearch", "webfetch", "seed", "user-provided"}
READ_STATUS = {"full", "abstract-only"}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("run")
    args = p.parse_args()
    run_dir = Path(args.run)
    if not run_dir.is_dir():
        run_dir = ROOT / "workspace" / "runs" / args.run
    bib_file = run_dir / "bibliography.jsonl"
    if not bib_file.is_file():
        print(f"ERROR: {bib_file} not found", file=sys.stderr)
        return 1

    errors, keys = [], set()
    n = 0
    for lineno, line in enumerate(bib_file.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        n += 1
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {lineno}: invalid JSON ({exc})")
            continue
        missing = [f for f in REQUIRED if f not in entry or entry[f] in (None, "", [])]
        if missing:
            errors.append(f"line {lineno} ({entry.get('key', '?')}): missing fields {missing}")
        key = entry.get("key")
        if key in keys:
            errors.append(f"line {lineno}: duplicate key '{key}'")
        keys.add(key)
        if entry.get("provenance") not in PROVENANCE:
            errors.append(f"line {lineno} ({key}): provenance '{entry.get('provenance')}' "
                          f"not in {sorted(PROVENANCE)}")
        if entry.get("read_status") not in READ_STATUS:
            errors.append(f"line {lineno} ({key}): read_status '{entry.get('read_status')}' "
                          f"not in {sorted(READ_STATUS)}")
        note = entry.get("local_note")
        if note and not (run_dir / note).is_file():
            errors.append(f"line {lineno} ({key}): local_note '{note}' does not exist")

    if errors:
        print(f"bibliography.jsonl: {len(errors)} error(s) in {n} entries:")
        for e in errors:
            print(f"  {e}")
        return 1
    print(f"bibliography.jsonl: {n} entries, all valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
