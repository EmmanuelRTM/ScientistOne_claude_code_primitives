#!/usr/bin/env python3
"""PreToolUse guard (Write|Edit|Bash): make hallucinated references
mechanically impossible.

If the target file lives under workspace/runs/<id>/paper/ or /final/, every
[EV:cite:KEY] (or pandoc-style [@KEY]) in the content being written must exist
in that run's bibliography.jsonl. Unknown key -> exit 2 (block) with the
reason on stderr, which Claude receives as feedback.

Bash is matched too: a shell command that writes into a paper area (redirect,
tee, sed -i, cp/mv, interpreter one-liner) is checked the same way, so the
guard cannot be stepped around with `cat > draft.md <<EOF`. Commands that only
READ paper files are untouched — grepping for a bogus key to find it is not
the same as writing one.

Fails open (exit 0) on unexpected input — the guard must never break normal
editing outside paper areas.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from shellwrite import write_targets, writes_content  # noqa: E402

EV_CITE_RE = re.compile(r"\[EV:cite:([^\]]+)\]")
PANDOC_CITE_RE = re.compile(r"\[@([A-Za-z0-9_:.\-]+)\]")
PAPER_PATH_RE = re.compile(r"(.*workspace/runs/([^/]+))/(?:paper|final)/")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    tool_input = payload.get("tool_input", {})

    if payload.get("tool_name") == "Bash" or "command" in tool_input:
        command = tool_input.get("command", "") or ""
        m = None
        for target in write_targets(command):
            m = PAPER_PATH_RE.match(target.replace("\\", "/"))
            if m:
                break
        content = writes_content(command)
    else:
        file_path = tool_input.get("file_path", "") or ""
        m = PAPER_PATH_RE.match(file_path.replace("\\", "/"))
        content = tool_input.get("content") or tool_input.get("new_string") or ""
    if not m:
        return 0
    run_dir = Path(m.group(1))

    keys = set(EV_CITE_RE.findall(content)) | set(PANDOC_CITE_RE.findall(content))
    if not keys:
        return 0

    bib_file = run_dir / "bibliography.jsonl"
    known = set()
    if bib_file.is_file():
        for line in bib_file.read_text().splitlines():
            if line.strip():
                try:
                    known.add(json.loads(line)["key"])
                except (json.JSONDecodeError, KeyError):
                    continue

    unknown = sorted(keys - known)
    if unknown:
        print(
            f"BLOCKED by citation guard: citation key(s) {unknown} not found in "
            f"{bib_file}. Citations must first be retrieved and recorded by the "
            f"problem-investigator (a paper that was not retrieved and read does "
            f"not exist). Either remove the citation or have the investigator add "
            f"the source to bibliography.jsonl with full provenance.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)  # fail open
