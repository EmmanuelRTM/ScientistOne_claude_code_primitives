#!/usr/bin/env python3
"""SubagentStart/SubagentStop hook: append agent lifecycle events to the
active run's ledger.jsonl. Usage: ledger_log.py start|stop. Always exits 0."""
import datetime
import json
import os
import sys
from pathlib import Path


def main() -> int:
    phase = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        payload = {}
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
    active = root / "workspace" / "runs" / "ACTIVE_RUN"
    if not active.is_file():
        return 0
    run = root / "workspace" / "runs" / active.read_text().strip()
    if not run.is_dir():
        return 0
    agent = (payload.get("agent_type") or payload.get("agent_name")
             or payload.get("subagent_type") or "unknown")
    event = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "event": f"agent_{phase}",
        "agent": agent,
        "session_id": payload.get("session_id", ""),
    }
    if agent == "unknown":
        # Open issue: some SubagentStop payloads carry no recognizable agent
        # name. Record the keys actually present so one real run settles which
        # field to read, instead of guessing a fourth alias. The same line
        # answers whether concurrent subagents get distinct session_ids —
        # the fact that branch-ownership enforcement would need.
        event["payload_keys"] = sorted(payload.keys())
    with (run / "ledger.jsonl").open("a") as fh:
        fh.write(json.dumps(event) + "\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
