#!/usr/bin/env python3
"""Pipeline autopilot enforcement. Two events, one mechanism.

`Stop`        — while an armed run still has an unfinished stage, block the
                stop and feed the next stage back as the instruction. This
                turns /research from a prose checklist the main agent has to
                remember into a loop the runtime enforces across compaction.
`PreToolUse`  — while an armed run is being driven by THIS session, deny
                AskUserQuestion. Nobody is watching an unattended loop, so a
                question would stall it indefinitely rather than end the turn
                and let the Stop gate push it forward.

Both share the same arming check, which is why they live in one file.

Opt-in twice over, so it can never surprise an unrelated session:
  1. the run must be armed  -> workspace/runs/<id>/AUTOPILOT exists
  2. the session must own it -> AUTOPILOT.session_id matches this session
     (the first session to fire the Stop gate after arming claims it)

Bounded by a counter in AUTOPILOT, not by stop_hook_active: the counter is a
file, so it survives --resume and is unaffected by whatever stop_hook_active
turns out to mean. The observed stop_hook_active value is recorded in the
ledger on every fire so its real semantics become checkable after one run.

Arm/disarm:  python3 .claude/scripts/autopilot.py arm [--max N] | disarm | status
Kill switch: RESEARCH_AUTOPILOT_OFF=1, or delete the AUTOPILOT file.

Stop exits 2 to block and feeds stderr back to Claude. Any error exits 0 —
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


def armed_run(root: Path):
    """Return (run_dir, state, state_file) for an armed active run, else None."""
    active = root / "workspace" / "runs" / "ACTIVE_RUN"
    if not active.is_file():
        return None
    run = root / "workspace" / "runs" / active.read_text().strip()
    if not run.is_dir():
        return None
    state_file = run / "AUTOPILOT"
    if not state_file.is_file():
        return None
    try:
        return run, json.loads(state_file.read_text()), state_file
    except (json.JSONDecodeError, OSError):
        return None


def log(run: Path, event: dict) -> None:
    event.setdefault("ts", datetime.datetime.now().isoformat(timespec="seconds"))
    try:
        with (run / "ledger.jsonl").open("a") as fh:
            fh.write(json.dumps(event) + "\n")
    except OSError:
        pass  # the ledger is a convenience; never fail the gate over it


def emit(payload: dict) -> int:
    """Print JSON for the runtime and allow the action."""
    print(json.dumps(payload))
    return 0


def handle_pre_tool_use(hook_input: dict, root: Path) -> int:
    if hook_input.get("tool_name") != "AskUserQuestion":
        return 0
    armed = armed_run(root)
    if armed is None:
        return 0
    run, state, _ = armed
    owner = state.get("session_id")
    # Deny only once the loop is actually being driven by this session. An
    # unclaimed run means the operator is still at the keyboard.
    if not owner or owner != hook_input.get("session_id"):
        return 0
    log(run, {"event": "autopilot_blocked_question"})
    return emit({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": (
            f"Autopilot is driving run {run.name} — no one is watching, so a "
            f"question cannot be answered and would stall the loop. Decide from "
            f"the run artifacts and the stage skill. If the stage genuinely "
            f"cannot proceed, run `python3 .claude/scripts/autopilot.py disarm` "
            f"and report why instead of fabricating a missing input."),
    }})


def handle_stop(hook_input: dict, root: Path) -> int:
    armed = armed_run(root)
    if armed is None:
        return 0
    run, state, state_file = armed

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


def main() -> int:
    if os.environ.get("RESEARCH_AUTOPILOT_OFF"):
        return 0
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    root = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    if hook_input.get("hook_event_name") == "PreToolUse":
        return handle_pre_tool_use(hook_input, root)
    return handle_stop(hook_input, root)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # a broken hook must never wedge a session
        try:
            print(f"run_stop_gate error (ignored): {exc}", file=sys.stderr)
        except Exception:
            pass
        sys.exit(0)
