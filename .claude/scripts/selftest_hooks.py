#!/usr/bin/env python3
"""Regression suite for the integrity hooks and the skill/agent wiring.
Run: python3 .claude/scripts/selftest_hooks.py

Hook cases feed a real PreToolUse payload to a real hook on a throwaway
fixture run and assert the exit code (2 = blocked, 0 = allowed). The point is
the *allowed* half as much as the blocked half: a guard that blocks a solver's
`python3 solution.py >> solve.log` is worse than no guard at all.

Wiring cases check every `skills:` entry in .claude/agents/*.md against
.claude/skills/. Claude Code SKIPS a missing or disabled preload with only a
debug-log warning (docs: sub-agents.md#preload-skills-into-subagents), so a
typo'd name or a later-added `disable-model-invocation: true` silently strips
an agent of the protocol it is judged against. This makes that loud.

Exits 0 if every case matches, 1 otherwise (naming the failures).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"


def run_hook(hook: str, payload: dict, cwd: Path, args: list[str] | None = None) -> int:
    proc = subprocess.run(
        [sys.executable, str(HOOKS / hook), *(args or [])],
        input=json.dumps(payload), capture_output=True, text=True,
        cwd=str(cwd), env={"CLAUDE_PROJECT_DIR": str(cwd), "PATH": "/usr/bin:/bin"},
    )
    return proc.returncode


def bash(command: str, cwd: str | None = None) -> dict:
    p = {"tool_name": "Bash", "tool_input": {"command": command}}
    if cwd:
        p["cwd"] = cwd
    return p


def write(path: str, content: str = "") -> dict:
    return {"tool_name": "Write", "tool_input": {"file_path": path, "content": content}}


def build_fixture(base: Path) -> Path:
    """A minimal run: one bibliography key, one branch, one paper dir."""
    run = base / "workspace" / "runs" / "r1"
    (run / "paper").mkdir(parents=True)
    (run / "final").mkdir()
    (run / "iterations" / "i1" / "branches" / "b1").mkdir(parents=True)
    (run / "bibliography.jsonl").write_text('{"key": "real2020paper", "title": "t"}\n')
    (run / "brief.md").write_text("brief\n")
    (base / "workspace" / "runs" / "ACTIVE_RUN").write_text("r1")
    return run


def cases(base: Path):
    branch = str(base / "workspace" / "runs" / "r1" / "iterations" / "i1" / "branches" / "b1")
    R = "workspace/runs/r1"
    yield from [
        # hook, payload, expected exit, label
        ("citation_guard.py", write(f"{R}/paper/draft.md", "x [EV:cite:fake2020paper]"), 2,
         "Write: unknown citation key into paper/"),
        ("citation_guard.py", write(f"{R}/paper/draft.md", "x [EV:cite:real2020paper]"), 0,
         "Write: known citation key into paper/"),
        ("citation_guard.py", write(f"{R}/paper/draft.md", "x [@fake2020paper]"), 2,
         "Write: unknown pandoc-style key"),
        ("citation_guard.py", write("notes.md", "x [EV:cite:fake2020paper]"), 0,
         "Write: unknown key outside a paper area is not this guard's business"),
        ("citation_guard.py", bash(f"cat > {R}/paper/draft.md <<'EOF'\n[EV:cite:fake2020paper]\nEOF"), 2,
         "Bash: heredoc smuggling an unknown key into paper/"),
        ("citation_guard.py", bash(f"cat > {R}/paper/draft.md <<'EOF'\n[EV:cite:real2020paper]\nEOF"), 0,
         "Bash: heredoc with a known key"),
        ("citation_guard.py", bash(f"grep -n 'EV:cite:fake2020paper' {R}/paper/draft.md"), 0,
         "Bash: grepping FOR a bogus key is a read, not a write"),

        ("paper_area_guard.py", write(f"{R}/paper/draft.md"), 2,
         "Write: discovery agent into paper/"),
        ("paper_area_guard.py", write(f"{R}/bibliography.jsonl"), 2,
         "Write: discovery agent into bibliography.jsonl"),
        ("paper_area_guard.py", write(f"{R}/iterations/i1/branches/b1/solution.py"), 0,
         "Write: discovery agent into its own branch"),
        ("paper_area_guard.py", bash(f"echo x > {R}/paper/draft.md"), 2,
         "Bash: redirect into paper/"),
        ("paper_area_guard.py", bash(f"python3 -c \"open('{R}/bibliography.jsonl','a').write('x')\""), 2,
         "Bash: interpreter one-liner appending to bibliography"),
        ("paper_area_guard.py", bash(f"sed -i s/a/b/ {R}/final/paper.md"), 2,
         "Bash: sed -i on the final paper"),
        ("paper_area_guard.py", bash("echo x > ../../../../paper/notes.md", cwd=branch), 2,
         "Bash: ../ traversal out of a branch into paper/"),
        ("paper_area_guard.py", bash("python3 solution.py >> solve.log 2>&1", cwd=branch), 0,
         "Bash: a solver's normal logged run"),
        ("paper_area_guard.py", bash(f"cat {R}/brief.md"), 0,
         "Bash: reading the brief"),
        ("paper_area_guard.py", bash(f"python3 {R}/task/evaluate.py solution.py"), 0,
         "Bash: the evaluator executing the golden evaluator"),
        ("paper_area_guard.py", bash("python3 .claude/scripts/ground_check.py workspace/runs/r1"), 0,
         "Bash: running a pipeline script that itself writes into paper/"),
    ]


def frontmatter(path: Path) -> str:
    text = path.read_text()
    if not text.startswith("---\n"):
        return ""
    return text.split("---\n", 2)[1]


def preloaded_skills(agent_md: Path) -> list[str]:
    """The `skills:` list from agent frontmatter, parsed with stdlib only."""
    names, in_skills = [], False
    for line in frontmatter(agent_md).splitlines():
        if re.match(r"^skills:\s*$", line):
            in_skills = True
            continue
        if in_skills:
            m = re.match(r"^\s+-\s+(\S+)\s*$", line)
            if m:
                names.append(m.group(1))
                continue
            in_skills = False
    return names


def wiring_failures() -> list[str]:
    """Every skills: entry must exist and be preloadable (docs: a missing or
    disable-model-invocation skill is skipped with only a debug warning)."""
    problems = []
    skills_dir = ROOT / ".claude" / "skills"
    for agent_md in sorted((ROOT / ".claude" / "agents").glob("*.md")):
        for name in preloaded_skills(agent_md):
            skill_md = skills_dir / name / "SKILL.md"
            if not skill_md.is_file():
                problems.append(
                    f"  {agent_md.name}: preloads '{name}' but "
                    f".claude/skills/{name}/SKILL.md does not exist "
                    f"(Claude Code would skip it silently)")
            elif re.search(r"^disable-model-invocation:\s*true",
                           frontmatter(skill_md), re.M):
                problems.append(
                    f"  {agent_md.name}: preloads '{name}' but that skill sets "
                    f"disable-model-invocation: true, which blocks preloading "
                    f"(Claude Code would skip it silently)")
    return problems


def main() -> int:
    failures = []
    total = 0
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        build_fixture(base)
        for hook, payload, want, label in cases(base):
            total += 1
            got = run_hook(hook, payload, base)
            if got != want:
                failures.append(f"  {hook}: {label}\n      expected exit {want}, got {got}")
    n_hook_failures = len(failures)
    wiring = wiring_failures()
    n_preloads = sum(len(preloaded_skills(p))
                     for p in (ROOT / ".claude" / "agents").glob("*.md"))
    if failures or wiring:
        if failures:
            print(f"FAIL — {n_hook_failures}/{total} hook cases wrong:")
            print("\n".join(failures))
        if wiring:
            print(f"FAIL — {len(wiring)} broken skill preload(s):")
            print("\n".join(wiring))
        return 1
    print(f"OK — {total}/{total} hook cases behave as specified; "
          f"{n_preloads}/{n_preloads} skill preloads resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
