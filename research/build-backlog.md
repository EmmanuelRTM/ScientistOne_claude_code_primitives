# Build backlog

Candidate `.claude/` artifacts, ordered by build order: two cheap probes that close
the open questions in the findings, then deterministic scripts, then the hooks that
call them, then skills, then subagents, then the composed proactive layer. Later
rows assume earlier ones exist.

`Confidence` uses the findings file's markers — `verified` (read in official docs
or working code), `observed` (seen in this machine's `.claude/` or session
behavior), `inferred` (my design conclusion, undocumented).

| Artifact | Type | Loop type | Trigger | Stop condition | Verifiable output | Depends on | Confidence |
|---|---|---|---|---|---|---|---|
| `probe-loop-state` | script | time-based | run once by hand: snapshot `.claude/`, run `/loop 1m echo`, snapshot again | one diff taken after the first fire | file diff naming the scheduled-task file (findings §3 records this as Not determined) | `/loop` available; `CLAUDE_CODE_DISABLE_CRON` unset `[verified: scheduled-tasks.md]` | inferred |
| `probe-routine-hooks` | script | proactive | one-off Routine whose prompt runs it once | single fire, routine auto-disables `[verified: routines.md]` | presence/absence of a sentinel file written by a committed `SessionStart` hook — settles whether repo hooks fire in cloud runs | claude.ai login; committed `.claude/settings.json` | inferred |
| `checks.sh` | script | turn-based | invoked from a skill body via `${CLAUDE_SKILL_DIR}` | runs every check, exits 0 or first non-zero | process exit code | none | inferred |
| `run_state.py` | script | turn-based | called by each stage and by the `SessionStart` hook | single-shot; exits 0 after append/print | append-only JSONL + `status` stdout | none | observed (`.claude/scripts/ledger.py`) |
| `session-state-brief` | hook | turn-based | `SessionStart` event in `.claude/settings.json` | fires once per session; always exits 0 (event does not block on exit 2) | non-empty state text injected into context | `run_state.py` | observed (`.claude/hooks/session_start.py`) |
| `qa-gate` | skill | turn-based | `description` auto-match ("before reporting a change done") or `/qa-gate`; leave `disable-model-invocation` unset | `checks.sh` exits 0 | `checks.sh` exit code | `checks.sh`; `allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/checks.sh *)` `[verified: skills.md]` | verified |
| `stop_gate.py` | script | goal-based | run by a `Stop` hook, event JSON on stdin | exit 0 when the artifact satisfies the rule, else exit 2; returns 0 immediately if `stop_hook_active` | exit code + unmet-item list on stderr | `checks.sh` or the artifact it parses | observed (`.claude/hooks/verifier_stop_gate.py`) |
| `deterministic-stop-gate` | hook | goal-based | `Stop` event, `type: "command"` | `stop_gate.py` exits 0 | exit code; stderr text becomes next instruction | `stop_gate.py`; workspace trust accepted; `disableAllHooks` unset `[verified: goal.md]` | verified |
| `turn-budget-guard` | hook | goal-based | `PostToolBatch` event, `type: "command"` | counter file exceeds N → exit 2, documented as "stops agentic loop before next model call" | counter value + exit code | `run_state.py` | verified (event blocks `[verified: hooks reference]`) / inferred (counter design) |
| `goal-eval` | hook | goal-based | `Stop` event, `type: "prompt"` | model returns `{"ok": true}`; `{"ok": false, "reason": ...}` feeds `reason` back as next instruction | subjective — model verdict on transcript only | none; `model` field optional, defaults to a fast model `[verified: hooks.md]` | verified |
| `verify-tests-agent` | hook | goal-based | `Stop` event, `type: "agent"`, `$ARGUMENTS` = hook input | `{"ok": true}` after the subagent runs the suite; 60s default timeout, 50 tool-use turns | test-runner exit code the agent quotes in `reason` | test runner; **experimental — docs prefer command hooks for production** `[verified: hooks-guide.md]` | verified |
| `fresh-reviewer` | subagent | turn-based | delegated when a diff needs an unbiased read; no conversation history or auto memory inherited | `maxTurns` cap, or review file written | review JSON with `file:line` findings and a count | none; set `tools`, `maxTurns`, `effort` `[verified: sub-agents.md]` | verified |
| `review-diff` | skill | turn-based | `/review-diff`; `context: fork`, `agent: fresh-reviewer`, `background: false` | forked subagent returns | review file exists; finding count | `fresh-reviewer`; `background` needs v2.1.218+ `[verified: skills.md]` | verified |
| `.claude/loop.md` | command | time-based | bare `/loop` (project file wins over `~/.claude/loop.md`) | `Esc`, `ScheduleWakeup stop:true`, or 7-day expiry | one status line appended per iteration to a log file | none; truncated past 25,000 bytes `[verified: scheduled-tasks.md]` | verified |
| `ci-babysit` | skill | time-based | `/loop 10m /ci-babysit`; **must not set `disable-model-invocation: true`** or the fire delivers plain text instead of running it | CI conclusion is `success`, or the PR is merged | CI check conclusion string from the API | GitHub MCP or `gh`; v2.1.196+ skill-invocation rule `[verified: scheduled-tasks.md]` | verified |
| `cron-audit` | script | time-based | called from `ci-babysit` or ad hoc | exits 0 after listing tasks | task count compared against the 50-per-session cap | `CronList` `[verified: scheduled-tasks.md]` | verified |
| `triage-pr` | skill | proactive | Routine GitHub trigger on `pull_request.opened`, optionally filtered by base branch or label | labels applied and summary comment posted, then the run ends | PR label set + comment ID | skill committed to the repo (cloud clones fresh); claude.ai login; routines enabled for the org `[verified: routines.md]` | verified |
| `outcome-sentinel` | script | proactive | last step of `triage-pr` | exits 0 only if the expected artifact was produced this run | sentinel file diff + exit code — green run status "does not mean the task succeeded" | `triage-pr` | verified (status caveat) / inferred (sentinel design) |
| `alert-investigate` | skill | proactive | Routine API trigger; POST `/fire` with `text` | draft PR opened, or a "no action" note written | draft PR number, or sentinel file | routine prompt must **explicitly reference the `<routine-fire-payload>` block** or the text stays inert `[verified: routines.md]` | verified |

## Sequencing notes

- The two probes cost one `/loop` run and one Routine run and remove the only two
  "Not determined" items in the findings. Do them before designing anything that
  depends on scheduled-task state or on hooks firing in the cloud.
- `deterministic-stop-gate` and `goal-eval` are alternatives, not a stack. Build the
  command hook when the verdict is computable from an artifact; the prompt hook only
  when it genuinely isn't. `verify-tests-agent` sits between them and is
  experimental.
- `turn-budget-guard` is the only enforced turn cap available inside an interactive
  session. `/goal` has no turn-cap flag, and a "stop after N turns" clause written
  into a goal condition is judged by the evaluator from the transcript rather than
  counted — and its counter resets on `--resume` `[verified: goal.md]`.
- `qa-gate`, `review-diff`, and `ci-babysit` all wrap the same `checks.sh`. Build the
  script once; the three loop types differ only in what starts it and what stops it.
