#!/usr/bin/env python3
"""Run-ledger utility: append events / show status of a run.

Usage:
    python3 .claude/scripts/ledger.py append '<json-object>' [--run RUN_ID]
    python3 .claude/scripts/ledger.py status [--run RUN_ID]

--run defaults to the id in workspace/runs/ACTIVE_RUN.
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "workspace" / "runs"


def resolve_run(run_id: str | None) -> Path | None:
    if run_id is None:
        active = RUNS / "ACTIVE_RUN"
        if not active.is_file():
            return None
        run_id = active.read_text().strip()
    run = RUNS / run_id
    return run if run.is_dir() else None


def cmd_append(run: Path, payload: str) -> int:
    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        event = {"event": "note", "note": payload}
    event.setdefault("ts", datetime.datetime.now().isoformat(timespec="seconds"))
    with (run / "ledger.jsonl").open("a") as fh:
        fh.write(json.dumps(event) + "\n")
    return 0


def cmd_status(run: Path) -> int:
    config = json.loads((run / "run-config.json").read_text())
    events = []
    ledger = run / "ledger.jsonl"
    if ledger.is_file():
        events = [json.loads(l) for l in ledger.read_text().splitlines() if l.strip()]
    print(f"Run: {config['run_id']}")
    print(f"Topic: {config['topic']}")
    print(f"Task: {config['task']}  branches={config['branches']}  "
          f"iterations={config['iterations']}  offline={config['offline']}")
    stage_events = [e for e in events if e.get("event", "").startswith("stage_")]
    if stage_events:
        print("Stages:")
        for e in stage_events:
            print(f"  {e['ts']}  {e['event']}  {e.get('detail', '')}")
    # branch scores
    scores = []
    for eval_file in sorted(run.glob("iterations/i*/branches/b*/eval.json")):
        try:
            data = json.loads(eval_file.read_text())
            rel = eval_file.relative_to(run)
            scores.append((rel.parents[2].name, rel.parent.name, data.get("score")))
        except (json.JSONDecodeError, OSError):
            continue
    if scores:
        print("Branch scores:")
        for it, br, score in scores:
            print(f"  {it}/{br}: {score}")
    selected = run / "best" / "SELECTED.json"
    if selected.is_file():
        print(f"Selected: {selected.read_text().strip()}")
    ground = run / "paper" / "ground-report.json"
    if ground.is_file():
        gr = json.loads(ground.read_text())
        print(f"Grounding ratio: {gr.get('grounding_ratio')}")
    key_artifacts = ["brief.md", "paper/research-representation.md", "paper/draft.md",
                     "paper/verification-report.md", "final/paper.md"]
    done = [a for a in key_artifacts if (run / a).is_file()]
    print("Artifacts present: " + (", ".join(done) if done else "none"))
    if events:
        last = events[-1]
        print(f"Last event: {last['ts']}  {last.get('event')}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["append", "status"])
    p.add_argument("payload", nargs="?", default=None)
    p.add_argument("--run", default=None)
    args = p.parse_args()

    run = resolve_run(args.run)
    if run is None:
        print("No active run. Start one with /research or new_run.py.")
        return 0 if args.command == "status" else 1
    if args.command == "append":
        if args.payload is None:
            print("append requires a JSON payload", file=sys.stderr)
            return 1
        return cmd_append(run, args.payload)
    return cmd_status(run)


if __name__ == "__main__":
    sys.exit(main())
