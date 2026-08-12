#!/usr/bin/env python3
"""Arm / disarm / inspect the pipeline autopilot for the active run.

The Stop gate (.claude/hooks/run_stop_gate.py) is inert unless the active run
carries an AUTOPILOT file. This is the operator surface for that file.

Usage:
    python3 .claude/scripts/autopilot.py arm [--max N] [--run RUN_ID]
    python3 .claude/scripts/autopilot.py disarm [--run RUN_ID]
    python3 .claude/scripts/autopilot.py status [--run RUN_ID]

--run defaults to the id in workspace/runs/ACTIVE_RUN.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "workspace" / "runs"
DEFAULT_MAX_CONTINUATIONS = 12


def resolve_run(run_id: str | None) -> Path | None:
    if run_id is None:
        active = RUNS / "ACTIVE_RUN"
        if not active.is_file():
            return None
        run_id = active.read_text().strip()
    run = RUNS / run_id
    return run if run.is_dir() else None


def cmd_arm(run: Path, cap: int) -> int:
    state_file = run / "AUTOPILOT"
    state = {"session_id": None, "max_continuations": cap, "used": 0}
    if state_file.is_file():  # re-arming keeps the owner, resets the budget
        try:
            state["session_id"] = json.loads(state_file.read_text()).get("session_id")
        except (json.JSONDecodeError, OSError):
            pass
    state_file.write_text(json.dumps(state, indent=2) + "\n")
    print(f"Autopilot armed for {run.name}: up to {cap} continuations.")
    print("The next session to finish a turn claims it; other sessions are unaffected.")
    print("Disarm with: python3 .claude/scripts/autopilot.py disarm")
    return 0


def cmd_disarm(run: Path) -> int:
    state_file = run / "AUTOPILOT"
    if not state_file.is_file():
        print(f"Autopilot was not armed for {run.name}.")
        return 0
    state_file.unlink()
    print(f"Autopilot disarmed for {run.name}.")
    return 0


def cmd_status(run: Path) -> int:
    state_file = run / "AUTOPILOT"
    if not state_file.is_file():
        print(f"Autopilot: not armed for {run.name}.")
        return 0
    try:
        state = json.loads(state_file.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Autopilot: AUTOPILOT file unreadable ({exc}) — the gate treats "
              f"this as not armed.", file=sys.stderr)
        return 1
    owner = state.get("session_id") or "unclaimed"
    print(f"Autopilot: armed for {run.name}")
    print(f"  continuations used: {state.get('used', 0)}/"
          f"{state.get('max_continuations', DEFAULT_MAX_CONTINUATIONS)}")
    print(f"  owning session: {owner}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["arm", "disarm", "status"])
    p.add_argument("--max", type=int, default=DEFAULT_MAX_CONTINUATIONS,
                   dest="cap", help="continuation budget for arm (default 12)")
    p.add_argument("--run", default=None)
    args = p.parse_args()

    if args.cap < 1:
        print("--max must be at least 1", file=sys.stderr)
        return 1

    run = resolve_run(args.run)
    if run is None:
        print("No active run. Start one with /research or new_run.py.", file=sys.stderr)
        return 1

    if args.command == "arm":
        return cmd_arm(run, args.cap)
    if args.command == "disarm":
        return cmd_disarm(run)
    return cmd_status(run)


if __name__ == "__main__":
    sys.exit(main())
