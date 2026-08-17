#!/usr/bin/env python3
"""Agent-scoped PreToolUse guard for discovery agents (ideator, solver,
evaluator, auditor).

Blocks writes to the narrative record: paper/, final/, brief.md,
bibliography.jsonl, investigation/, literature/. Discovery agents work only
inside their iteration/branch directories. Exit 2 = block. Fails open.

Matches Write and Edit by file_path, and Bash by the paths the command is
about to write (redirects, tee, sed -i, cp/mv, interpreter one-liners) — an
agent holding Bash could otherwise reach the same files through a redirect and
never trip a Write/Edit guard.
"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from shellwrite import write_targets  # noqa: E402

FORBIDDEN_RE = re.compile(
    r"workspace/runs/[^/]+/"
    r"(paper/|final/|brief\.md$|bibliography\.jsonl$|investigation/|literature/)"
)


def normalized(path: str, cwd: str) -> str:
    """Project-relative form, so ../.. traversal out of a branch dir still matches."""
    p = path.replace("\\", "/")
    if cwd and not p.startswith("/"):
        p = os.path.normpath(os.path.join(cwd, p))
    root = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if root and p.startswith(root):
        p = p[len(root):].lstrip("/")
    return p.replace("\\", "/")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    tool_input = payload.get("tool_input", {}) or {}
    cwd = payload.get("cwd", "") or ""

    if payload.get("tool_name") == "Bash" or "command" in tool_input:
        candidates = write_targets(tool_input.get("command", "") or "")
    else:
        candidates = [tool_input.get("file_path") or ""]

    for raw in candidates:
        if not raw:
            continue
        if FORBIDDEN_RE.search(normalized(raw, cwd)):
            print(
                f"BLOCKED: discovery agents must not modify the narrative record "
                f"({raw}). Discovery agents write only inside iterations/iN/ — "
                f"solvers, evaluators and auditors inside their own branches/bK/ "
                f"directory. The paper, brief, bibliography and literature notes "
                f"belong to other stages; a shell redirect does not make them "
                f"yours to edit.",
                file=sys.stderr,
            )
            return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
