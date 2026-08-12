#!/usr/bin/env python3
"""Stop gate for the MAIN session (pipeline autopilot).

While a run is armed and still has an unfinished stage, block the session's
stop and feed the next stage back as the instruction. This turns /research
from a prose checklist the main agent has to remember into an enforced loop
that survives compaction.

Opt-in twice over, so it can never surprise an unrelated session:
  1. the run must be armed  -> workspace/runs/<id>/AUTOPILOT exists
  2. the session must own it -> AUTOPILOT.session_id matches this session
     (the first session to fire the gate after arming claims it)

Bounded by a counter in AUTOPILOT, not by stop_hook_active: the counter is a
file, so it survives --resume and is unaffected by whatever stop_hook_active
turns out to mean. The observed stop_hook_active value is recorded in the
ledger on every fire so its real semantics become checkable after one run.

Arm/disarm:  python3 .claude/scripts/autopilot.py arm [--max N] | disarm | status
Kill switch: RESEARCH_AUTOPILOT_OFF=1, or delete the AUTOPILOT file.

Exit 2 blocks the stop and feeds stderr back to Claude. Any error exits 0 —
a broken hook must never wedge a session.
"""
import datetime
import json
import os
import sys
from pathlib import Path

DEFAULT_MAX_CONTINUATIONS = 12


def next_stage(run: Path):
    """Mirror of session_start.py's ladder: (skill-dir, human label) or None."""
    if (run / "final" / "paper.md").is_file():
        return None
    if (run / "paper" / "draft.md").is_file():
        return ("verify-claims", "Stage 4 — Claim Verifier")
    if (run / "best" / "SELECTED.json").is_file():
        return ("write-paper", "Stage 3 — Paper Writer")
    if (run / "brief.md").is_file():
        return ("discover", "Stage 2 — Discovery (parallel explore-exploit)")
    return ("investigate", "Stage 1 — Problem Investigator")


def log(run: Path, event: dict) -> None:
    event.setdefault("ts", datetime.datetime.now().isoformat(timespec="seconds"))
    try:
        with (run / "ledger.jsonl").open("a") as fh:
            fh.write(json.dumps(event) + "\n")
    except OSError:
        pass  # the ledger is a convenience; never fail the gate over it


def emit(payload: dict) -> int:
    """Surface a message to the user while still allowing the stop."""
    print(json.dumps(payload))
    return 0


def main() -> int:
    if os.environ.get("RESEARCH_AUTOPILOT_OFF"):
        return 0
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    root = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    active = root / "workspace" / "runs" / "ACTIVE_RUN"
    if not active.is_file():
        return 0
    run = root / "workspace" / "runs" / active.read_text().strip()
    if not run.is_dir():
        return 0

    state_file = run / "AUTOPILOT"
    if not state_file.is_file():
        return 0  # not armed — this is the common case, and the gate is inert
    try:
        state = json.loads(state_file.read_text())
    except (json.JSONDecodeError, OSError):
        return 0

    session_id = hook_input.get("session_id")
    owner = state.get("session_id")
    if owner is None and session_id:
        state["session_id"] = owner = session_id  # first fire claims the run
    elif owner and session_id and owner != session_id:
        return 0  # a different session in this repo — leave it alone

    used = int(state.get("used", 0))
    cap = int(state.get("max_continuations", DEFAULT_MAX_CONTINUATIONS))
    stage = next_stage(run)

    if stage is None:
        state_file.unlink(missing_ok=True)
        log(run, {"event": "autopilot_complete", "continuations": used})
        return emit({"systemMessage":
                     f"Autopilot: run complete — {run.name}/final/paper.md exists "
                     f"after {used} continuation(s). Disarmed."})

    skill, label = stage
    if used >= cap:
        state_file.unlink(missing_ok=True)
        log(run, {"event": "autopilot_budget_exhausted",
                  "continuations": used, "cap": cap, "pending_stage": skill})
        return emit({"systemMessage":
                     f"Autopilot: continuation budget spent ({used}/{cap}) with "
                     f"{label} still pending for {run.name}. Disarmed — re-arm with "
                     f"`python3 .claude/scripts/autopilot.py arm --max N` to continue."})

    state["used"] = used + 1
    try:
        state_file.write_text(json.dumps(state, indent=2) + "\n")
    except OSError:
        return 0  # cannot bound the loop -> refuse to start one

    log(run, {"event": "autopilot_continue", "continuation": used + 1, "cap": cap,
              "next_stage": skill,
              "stop_hook_active": hook_input.get("stop_hook_active")})

    print(
        f"Autopilot ({used + 1}/{cap}): run {run.name} is unfinished. "
        f"Next is {label}.\n"
        f"Read .claude/skills/{skill}/SKILL.md and carry out that stage for "
        f"workspace/runs/{run.name}. Read the file directly — the stage skills set "
        f"disable-model-invocation: true, so /{skill} is not yours to invoke.\n"
        f"If the stage cannot proceed (missing input artifact, aborted run), run "
        f"`python3 .claude/scripts/autopilot.py disarm` and report why instead of "
        f"fabricating the missing input.",
        file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # a broken hook must never wedge a session
        try:
            print(f"run_stop_gate error (ignored): {exc}", file=sys.stderr)
        except Exception:
            pass
        sys.exit(0)
