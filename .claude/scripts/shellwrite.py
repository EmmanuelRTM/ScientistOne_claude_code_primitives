#!/usr/bin/env python3
"""Shell write-target extraction, shared by the Bash PreToolUse guards.

The Write/Edit guards (`citation_guard.py`, `paper_area_guard.py`) are only as
strong as the tools they match on: any agent holding Bash can reach the same
files through a redirect, `tee`, `sed -i`, or a `python -c` one-liner and never
trip them. This module answers the one question both guards need of a shell
command — "which paths is it about to WRITE?" — so the guards can apply the
same rules to Bash that they already apply to Write and Edit.

Deliberately conservative: it reports targets it can identify positionally, and
reports nothing for commands with no write intent. Reading a file is never a
write. It is a speed bump against the obvious bypasses, not a sandbox — a
determined command (base64-encoded payloads, a written-then-executed script)
still gets through, which is why the prompt-level rules stay in place.
"""
from __future__ import annotations

import re
import shlex

# commands whose non-flag arguments (or last argument) name a file they write
_LAST_ARG_WRITERS = {"cp", "mv", "install", "rsync", "ln"}
_ALL_ARG_WRITERS = {"tee", "truncate", "touch"}
# in-place editors: every non-flag argument is a file they rewrite
_INPLACE_RE = re.compile(r"\b(sed|perl|ruby)\b[^|;&]*\s-[a-zA-Z]*i")
# python/perl one-liners that open something for writing
_OPEN_WRITE_RE = re.compile(
    r"""open\(\s*['"]([^'"]+)['"]\s*,\s*['"][awx+]"""
    r"""|['"]([^'"]+)['"]\s*\)\s*\.\s*write_text\("""
    r"""|Path\(\s*['"]([^'"]+)['"]\s*\)\s*\.\s*(?:write_text|write_bytes|open)\("""
)
_HEREDOC_RE = re.compile(r"<<-?\s*['\"]?[A-Za-z_][A-Za-z0-9_]*['\"]?")


def _tokens(command: str) -> list[str]:
    try:
        return shlex.split(command, posix=True)
    except ValueError:  # unbalanced quotes — fall back to whitespace split
        return command.split()


def write_targets(command: str) -> list[str]:
    """Paths this shell command appears about to create, overwrite or append.

    Returns [] when no write intent is detectable. Never raises.
    """
    if not command:
        return []
    targets: list[str] = []
    text = command.replace("\\\n", " ")

    # 1. redirections: > file, >> file, 1> file, >| file  (but not 2>&1, <)
    for m in re.finditer(r"(?<![0-9<>])[0-9]?>>?\|?\s*([^\s;|&()<>]+)", text):
        tgt = m.group(1)
        if not tgt.startswith("&"):
            targets.append(tgt)

    # 2. in-place editors: sed -i, perl -i
    for m in _INPLACE_RE.finditer(text):
        segment = text[m.end():]
        segment = re.split(r"[|;&]", segment, maxsplit=1)[0]
        targets.extend(t for t in _tokens(segment) if not t.startswith("-"))

    # 3. interpreter one-liners opening a file for writing
    for m in _OPEN_WRITE_RE.finditer(text):
        targets.extend(g for g in m.groups() if g)

    # 4. commands whose arguments are their own output
    for segment in re.split(r"[|;&]+|\bthen\b|\bdo\b", text):
        toks = _tokens(segment)
        if not toks:
            continue
        # skip env-var prefixes and sudo-ish wrappers
        while toks and ("=" in toks[0] and not toks[0].startswith("-")):
            toks = toks[1:]
        if not toks:
            continue
        cmd = toks[0].rsplit("/", 1)[-1]
        args = [t for t in toks[1:] if not t.startswith("-")]
        if cmd in _ALL_ARG_WRITERS:
            targets.extend(args)
        elif cmd in _LAST_ARG_WRITERS and args:
            targets.append(args[-1])
        elif cmd == "dd":
            targets.extend(t.split("=", 1)[1] for t in toks[1:] if t.startswith("of="))

    return [t for t in targets if t and not t.startswith("&")]


def writes_content(command: str) -> str:
    """The text a command appears to be writing, for content-level checks.

    Heredoc bodies, echo/printf payloads and quoted one-liner strings all land
    here; when in doubt this returns the whole command, since a false positive
    only means the caller inspects a little more text than necessary.
    """
    if not command:
        return ""
    if _HEREDOC_RE.search(command) or write_targets(command):
        return command
    return ""
