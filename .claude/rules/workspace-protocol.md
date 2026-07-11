# Workspace protocol (all agents)

- Resolve the run directory from your task message; if absent, read
  `workspace/runs/ACTIVE_RUN`.
- Write outputs to the EXACT paths named in your task. Creating extra
  top-level files in the run directory is a protocol violation.
- Paths inside artifacts (evidence tags, reports) are run-directory-relative.
- Log stage progress with:
  `python3 .claude/scripts/ledger.py append '{"event":"stage_<name>","detail":"..."}'`
- Finish your reply with one line of JSON:
  `{"ok": true|false, "outputs": ["<relative paths written>"], "notes": "<one sentence>"}`
- If a required input artifact is missing, stop and report `ok: false` —
  never fabricate a stand-in for another stage's output.
