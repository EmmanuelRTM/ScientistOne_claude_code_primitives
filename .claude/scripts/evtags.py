"""Shared evidence-tag grammar and helpers (single source of truth).

Tag grammar:
    [EV:score:<path/to.json>#<dotted.key>]   numerical evidence in a JSON artifact
    [EV:log:<path>:L<start>[-L<end>]]        line(s) in a log file
    [EV:cite:<bibkey>]                       key in bibliography.jsonl
    [EV:artifact:<path>]                     artifact existence
    [EV:config:<path.json>#<dotted.key>]     config value

All paths are run-directory-relative.
"""
import json
import re
from pathlib import Path

EV_RE = re.compile(r"\[EV:(score|log|cite|artifact|config):([^\]]+)\]")
# numbers that count as factual: decimals, percentages, or integers >= 3 digits
NUMBER_RE = re.compile(r"\d+\.\d+|\d+(?:\.\d+)?\s*%|\b\d{3,}\b")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def find_tags(text: str):
    """Return list of (type, ref) tuples for all EV tags in text."""
    return EV_RE.findall(text)


def strip_tags(text: str) -> str:
    return EV_RE.sub("", text)


def sentences(markdown: str):
    """Yield (line_number, sentence) over a markdown document.

    Skips code fences, headers, tables and blank lines; line_number points at
    the line where the sentence starts.
    """
    in_fence = False
    for lineno, line in enumerate(markdown.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped or stripped.startswith(("#", "|", "<!--")):
            continue
        for sent in SENTENCE_SPLIT_RE.split(stripped):
            if sent.strip():
                yield lineno, sent.strip()


def resolve_json_pointer(run_dir: Path, ref: str):
    """Resolve 'path/to.json#dotted.key' -> (value, error)."""
    if "#" not in ref:
        return None, f"missing '#dotted.key' in ref '{ref}'"
    path_part, key_part = ref.split("#", 1)
    fp = run_dir / path_part
    if not fp.is_file():
        return None, f"artifact not found: {path_part}"
    try:
        value = json.loads(fp.read_text())
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON in {path_part}: {exc}"
    for key in key_part.split("."):
        if isinstance(value, list):
            try:
                value = value[int(key)]
            except (ValueError, IndexError):
                return None, f"key '{key_part}' not found in {path_part}"
        elif isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return None, f"key '{key_part}' not found in {path_part}"
    return value, None


def load_bibliography(run_dir: Path) -> dict:
    """Return {key: entry} from bibliography.jsonl (empty dict if absent)."""
    bib_file = run_dir / "bibliography.jsonl"
    entries = {}
    if bib_file.is_file():
        for line in bib_file.read_text().splitlines():
            if line.strip():
                try:
                    entry = json.loads(line)
                    entries[entry["key"]] = entry
                except (json.JSONDecodeError, KeyError):
                    continue
    return entries


def numbers_in(text: str):
    """Extract candidate factual numbers as floats from text (tags stripped)."""
    out = []
    for m in NUMBER_RE.finditer(strip_tags(text)):
        raw = m.group(0).replace("%", "").strip()
        try:
            out.append(float(raw))
        except ValueError:
            continue
    return out


def numbers_match(sentence_num: float, artifact_value, rel_tol: float) -> bool:
    """True if sentence_num matches artifact_value within rel_tol.

    Handles percent-vs-fraction mismatch (0.96 vs 96) transparently.
    """
    try:
        av = float(artifact_value)
    except (TypeError, ValueError):
        return False
    for candidate in (sentence_num, sentence_num / 100.0, sentence_num * 100.0):
        if av == candidate:
            return True
        if av != 0 and abs(candidate - av) / abs(av) <= rel_tol:
            return True
    return False


def check_log_ref(run_dir: Path, ref: str):
    """Validate 'path:L42' or 'path:L42-L57'. Returns (ok, detail)."""
    m = re.match(r"^(.*?):L(\d+)(?:-L?(\d+))?$", ref)
    if not m:
        # bare path is acceptable: whole-file reference
        fp = run_dir / ref
        return (True, "file exists") if fp.is_file() else (False, f"log not found: {ref}")
    path_part, start, end = m.group(1), int(m.group(2)), m.group(3)
    fp = run_dir / path_part
    if not fp.is_file():
        return False, f"log not found: {path_part}"
    n_lines = len(fp.read_text().splitlines())
    last = int(end) if end else start
    if start < 1 or last > n_lines:
        return False, f"line range L{start}-L{last} outside {path_part} ({n_lines} lines)"
    return True, "line range valid"
