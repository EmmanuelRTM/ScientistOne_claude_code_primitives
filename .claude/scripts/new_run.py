#!/usr/bin/env python3
"""Scaffold a new research run directory (the artifact bus for the pipeline).

Usage:
    python3 .claude/scripts/new_run.py "TOPIC" [--task digits] [--branches 5]
                                       [--iterations 2] [--offline] [--slug word]

Prints the run id on success. Sets workspace/runs/ACTIVE_RUN.
"""
import argparse
import datetime
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "workspace" / "runs"


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:24] or "run"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("topic")
    p.add_argument("--task", default="digits")
    p.add_argument("--branches", type=int, default=5)
    p.add_argument("--iterations", type=int, default=2)
    p.add_argument("--offline", action="store_true")
    p.add_argument("--votes", type=int, default=1,
                   help="best-of-N samples for LLM-only claim verdicts")
    p.add_argument("--slug", default=None)
    args = p.parse_args()

    task_dir = ROOT / "workspace" / "tasks" / args.task
    if not task_dir.is_dir():
        print(f"ERROR: task '{args.task}' not found under workspace/tasks/", file=sys.stderr)
        return 1

    now = datetime.datetime.now()
    run_id = f"{now:%Y%m%d-%H%M}-{args.slug or slugify(args.topic)}"
    run = RUNS / run_id
    if run.exists():
        print(f"ERROR: run dir {run} already exists", file=sys.stderr)
        return 1

    for sub in ("literature", "investigation", "best", "paper", "final"):
        (run / sub).mkdir(parents=True)
    for i in range(1, args.iterations + 1):
        (run / "iterations" / f"i{i}" / "proposals").mkdir(parents=True)
        for b in range(1, args.branches + 1):
            (run / "iterations" / f"i{i}" / "branches" / f"b{b}").mkdir(parents=True)
    shutil.copytree(task_dir, run / "task")
    (run / "bibliography.jsonl").touch()

    config = {
        "run_id": run_id,
        "topic": args.topic,
        "task": args.task,
        "branches": args.branches,
        "iterations": args.iterations,
        "offline": args.offline,
        "verifier_votes": max(1, args.votes),
        "created_at": now.isoformat(timespec="seconds"),
    }
    (run / "run-config.json").write_text(json.dumps(config, indent=2) + "\n")
    (run / "ledger.jsonl").write_text(
        json.dumps({"ts": config["created_at"], "event": "run_created", **config}) + "\n"
    )
    (RUNS / "ACTIVE_RUN").write_text(run_id + "\n")
    print(run_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
