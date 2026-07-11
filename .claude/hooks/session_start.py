#!/usr/bin/env python3
"""SessionStart hook: surface the active run's state so any session (or agent
resuming after compaction) knows where the pipeline stands. Always exits 0."""
import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    active = root / "workspace" / "runs" / "ACTIVE_RUN"
    if not active.is_file():
        print("Research pipeline: no active run. Start one with "
              "/research \"<topic>\" [--task digits] [--branches 5] [--iterations 2].")
        return 0
    run_id = active.read_text().strip()
    if not (root / "workspace" / "runs" / run_id).is_dir():
        print(f"Research pipeline: ACTIVE_RUN points to missing run '{run_id}'.")
        return 0
    result = subprocess.run(
        [sys.executable, str(root / ".claude" / "scripts" / "ledger.py"), "status"],
        capture_output=True, text=True, cwd=root)
    print("Research pipeline state:")
    print(result.stdout.strip())
    # suggest the next stage
    run = root / "workspace" / "runs" / run_id
    if (run / "final" / "paper.md").is_file():
        hint = "run complete — final/paper.md exists"
    elif (run / "paper" / "draft.md").is_file():
        hint = "next: /verify-claims"
    elif (run / "best" / "SELECTED.json").is_file():
        hint = "next: /write-paper"
    elif (run / "brief.md").is_file():
        hint = "next: /discover"
    else:
        hint = "next: /investigate"
    print(f"Suggested next step: {hint}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # a broken hook must never block a session
        try:
            print(f"session_start hook error (ignored): {exc}")
        except Exception:
            pass
        sys.exit(0)
