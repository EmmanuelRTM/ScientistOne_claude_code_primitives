#!/usr/bin/env python3
"""Agent-scoped PreToolUse guard for discovery agents (solver, evaluator).

Blocks Write/Edit to the narrative record: paper/, final/, brief.md,
bibliography.jsonl, investigation/, literature/. Discovery agents work only
inside their iteration/branch directories. Exit 2 = block. Fails open.
"""
import json
import re
import sys

FORBIDDEN_RE = re.compile(
    r"workspace/runs/[^/]+/"
    r"(paper/|final/|brief\.md$|bibliography\.jsonl$|investigation/|literature/)"
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    file_path = (payload.get("tool_input", {}).get("file_path") or "").replace("\\", "/")
    if FORBIDDEN_RE.search(file_path):
        print(
            f"BLOCKED: discovery agents must not modify the narrative record "
            f"({file_path}). Solvers and evaluators write only inside their own "
            f"iterations/iN/branches/bK/ directory.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
