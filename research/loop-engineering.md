# Loop engineering in `.claude/`

Findings for building repeating-work loops out of Claude Code primitives.
Pinned to **Claude Code 2.1.228** `[observed: claude --version]`. Several fields
carry explicit "requires vX" notes in the docs, so treat version as part of every
claim.

Markers: `[verified: <source>]` read in official docs or working code ·
`[observed: <path>]` seen in this machine's files or session ·
`[inferred]` my own design conclusion.

Primary sources opened this session: `code.claude.com/docs/en/{skills, sub-agents,
hooks, hooks-guide, goal, scheduled-tasks, routines, commands, settings}.md`, plus
the on-disk `.claude/` tree of this repository.

---

## Shared primitive schemas

All four loop types draw on the same four file shapes. Stated once here; the
per-type sections below reference them rather than repeat them.

### Skill — `.claude/skills/<name>/SKILL.md` or `~/.claude/skills/<name>/SKILL.md`

The command name comes from the **directory name**, not the `name` field, for
personal and project skills; `name` only sets the display label. Plugin skills are
the exception — there `name` sets the last command segment `[verified: skills.md,
"How a skill gets its command name"]`. `.claude/commands/deploy.md` and
`.claude/skills/deploy/SKILL.md` both produce `/deploy` and behave identically
`[verified: skills.md]`.

All frontmatter fields are optional; only `description` is recommended
`[verified: skills.md]`. Fields relevant to loops:

| Field | Value | Loop relevance |
|---|---|---|
| `description` | string | What Claude matches on for auto-invocation. `description` + `when_to_use` truncated at 1,536 chars in the listing |
| `when_to_use` | string | Trigger phrases, appended to `description` |
| `argument-hint` | e.g. `[issue-number]` | Autocomplete hint only |
| `arguments` | space-separated or YAML list | Named positional args for `$name` substitution |
| `disable-model-invocation` | bool, default `false` | Manual-only. **Also blocks the skill from being preloaded into subagents, and (v2.1.196+) from running when a scheduled task fires with it as the prompt** |
| `user-invocable` | bool, default `true` | `false` hides from the `/` menu |
| `allowed-tools` | string or list | Pre-approved tools **for the invoking turn only**; grant clears on your next message |
| `disallowed-tools` | string or list | Removes tools while active. Docs name the loop case explicitly: "such as `AskUserQuestion` for a background loop" |
| `model` | `/model` values or `inherit` | Applies for the rest of the turn, not saved to settings |
| `effort` | `low`\|`medium`\|`high`\|`xhigh`\|`max` | Overrides session effort |
| `context` | `fork` | Runs the skill as a subagent; skill body becomes the prompt; **no conversation history** |
| `agent` | subagent type | Which subagent type `context: fork` uses |
| `background` | bool, default `true` | Only with `context: fork`. `false` waits in the invoking turn. Requires v2.1.218+ |
| `hooks` | map | Hooks scoped to this skill's lifetime |
| `paths` | globs | Auto-activate only when working on matching files |
| `shell` | `bash` (default) \| `powershell` | For `` !`cmd` `` blocks |

`[verified: skills.md frontmatter reference]`

Substitutions inside the body **and** inside `allowed-tools` Bash rules:
`$ARGUMENTS`, `$ARGUMENTS[N]`, `$N` (`$0` is the first argument),
`${CLAUDE_SKILL_DIR}`, `${CLAUDE_PROJECT_DIR}` (v2.1.196+)
`[verified: skills.md]`. Using the same `${CLAUDE_SKILL_DIR}` in body and in
`allowed-tools` is the documented way to run a bundled script with no permission
prompt `[verified: skills.md]`.

Skill content **stays in context across turns** once loaded — every line is a
recurring token cost `[verified: skills.md]`.

### Subagent — `.claude/agents/<file>.md`, `~/.claude/agents/<file>.md`, plugin `agents/`

Only `name` and `description` are required `[verified: sub-agents.md]`. Identity
comes from `name`, not the filename or subdirectory. Precedence: managed >
`--agents` > `.claude/agents/` > `~/.claude/agents/` > plugin `[verified:
sub-agents.md]`.

| Field | Value |
|---|---|
| `name` | lowercase + hyphens, no `:`. Hooks receive it as `agent_type` |
| `description` | when to delegate |
| `tools` | allowlist; inherits all if omitted |
| `disallowedTools` | denylist applied after `tools` |
| `model` | `sonnet`\|`opus`\|`haiku`\|`fable`\|full ID\|`inherit` (default `inherit`) |
| `permissionMode` | `default`\|`acceptEdits`\|`auto`\|`dontAsk`\|`bypassPermissions`\|`plan`\|`manual` (alias for `default`, v2.1.200+) |
| `maxTurns` | **hard cap on agentic turns before the subagent stops** |
| `skills` | preloads full skill content at startup |
| `mcpServers` | names or inline defs |
| `hooks` | lifecycle hooks |
| `memory` | `user`\|`project`\|`local` |
| `background` | `true` forces background; unset lets Claude choose (background by default as of v2.1.198) |
| `effort` | `low`…`max` |
| `isolation` | `worktree` — isolated repo copy, auto-cleaned if unchanged |
| `color` | red\|blue\|green\|yellow\|purple\|orange\|pink\|cyan |
| `initialPrompt` | auto-submitted first turn when run as main session agent via `--agent` |

`[verified: sub-agents.md supported frontmatter fields]`

`hooks`, `mcpServers`, and `permissionMode` are **ignored for plugin subagents**
`[verified: sub-agents.md]`. Project-subagent frontmatter hooks require accepting
the workspace trust dialog; user-level and `--agents` definitions don't
`[verified: sub-agents.md]`.

> **Naming gotcha.** Skills use kebab-case `allowed-tools` / `disallowed-tools`;
> subagents use camelCase `disallowedTools`. Mixing them silently does nothing.
> `[verified: skills.md + sub-agents.md side by side]`

### Hook — `settings.json`, or `hooks:` frontmatter in a skill or subagent

31 event names exist `[verified: code.claude.com/docs/en/hooks]`. The loop-relevant
ones: `SessionStart`, `Setup`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`,
`PostToolBatch`, `SubagentStart`, `SubagentStop`, `Stop`, `StopFailure`,
`TaskCreated`, `TaskCompleted`, `PreCompact`, `PostCompact`, `SessionEnd`.

Config shape:

```json
{
  "hooks": {
    "Stop": [
      { "matcher": "", "hooks": [ { "type": "command", "command": "..." } ] }
    ]
  }
}
```

Hook entry types: `"command"`, `"http"`, `"mcp_tool"`, `"prompt"`, `"agent"`
`[verified: hooks.md common fields]`. Common optional fields: `if` (permission-rule
syntax; **only evaluated on tool events** — on other events a hook with `if` set
never runs), `timeout` (seconds; defaults 600 command/http/mcp_tool, 30 prompt,
60 agent), `statusMessage`, `once` (**only honored in skill frontmatter**; ignored
in settings files and agent frontmatter) `[verified: hooks.md]`.

Exit-code contract for command hooks: `0` = proceed (stdout parsed as JSON for
decision fields, otherwise debug log only); `2` = blocking error where the event
supports it, and the message comes from JSON `reason` or else stderr; other codes
are non-blocking `[verified: code.claude.com/docs/en/hooks]`.

Events that **block on exit 2**: `PreToolUse`, `UserPromptSubmit`,
`UserPromptExpansion`, `Stop`, `SubagentStop`, `TeammateIdle`, `TaskCreated`,
`TaskCompleted`, `ConfigChange`, `PostToolBatch`, `Elicitation`,
`ElicitationResult`, `PreCompact`, `WorktreeCreate`. Events that do **not**:
`PermissionRequest`, `StopFailure`, `PostToolUse`, `PostToolUseFailure`,
`PermissionDenied`, `Notification`, `SubagentStart`, `SessionStart`, `Setup`,
`SessionEnd` `[verified: code.claude.com/docs/en/hooks, exit-code-2 table]`.

Universal JSON output fields: `continue` (false stops Claude entirely, takes
precedence over event decisions), `stopReason`, `systemMessage` (capped 10,000
chars), `terminalSequence`. `suppressOutput` is **accepted but has no effect**
`[verified: code.claude.com/docs/en/hooks]`. Decision fields: top-level
`decision`/`reason`, and nested `hookSpecificOutput` with `hookEventName`,
`additionalContext`, `permissionDecision`, `permissionDecisionReason`,
`updatedInput`, `retry` `[verified: same]`.

Input every hook receives on stdin: `session_id`, `prompt_id`, `transcript_path`,
`cwd`, `permission_mode`, `hook_event_name`, `effort.level`, `agent_id`,
`agent_type`; `Stop`/`SubagentStop` additionally get `stop_hook_active`
`[verified: code.claude.com/docs/en/hooks]`.

Frontmatter hooks use the identical format and are scoped to the component's
lifetime. **All hook events are supported, and for subagents `Stop` is
automatically converted to `SubagentStop`** `[verified: hooks.md, "Hooks in skills
and agents"]` — so writing `Stop:` in an agent file registers a `SubagentStop`
hook, which is what this repo does `[observed: .claude/agents/claim-verifier.md]`.

### Settings — `.claude/settings.json`, `.claude/settings.local.json`, `~/.claude/settings.json`

Precedence, highest first: managed → command line → `.claude/settings.local.json`
→ `.claude/settings.json` → `~/.claude/settings.json` `[verified: settings.md]`.
`model` and `outputStyle` are read once at startup; most other keys reload live
`[verified: settings.md]`.

---

## 1. Turn-based

**Trigger.** A human prompt, or Claude auto-invoking a skill whose `description`
matches the request. Auto-invocation is the trigger surface you actually design:
put the key use case first in `description`, add trigger phrases in `when_to_use`,
and scope with `paths` globs when the skill should only fire on certain files
`[verified: skills.md]`. Setting `disable-model-invocation: true` converts the
skill to `/name`-only and removes its description from context entirely
`[verified: skills.md]`.

**Stop condition.** The human. There is no encoded exit — the turn ends when Claude
judges the work done, and the operator decides whether to prompt again. The
engineering move is not to add an exit condition but to move more verification
*inside* the turn, so the human's judgment call is cheaper and better-informed.

**Driving primitive.** Skill. The QA checklist that used to live in your head
becomes `SKILL.md` body, and the checks it names become scripts referenced through
`${CLAUDE_SKILL_DIR}`. Pre-approving the exact command in `allowed-tools` with the
same substitution means the check runs with no permission prompt `[verified:
skills.md]`.

**Fitting tasks.** Anything where the acceptance criteria are known but the work is
open-ended: implement-a-feature, fix-this-bug, write-this-doc.

**Files.**

```
.claude/skills/qa-gate/SKILL.md          # the checklist
.claude/skills/qa-gate/scripts/checks.sh # deterministic part
```

```yaml
---
description: >
  Verify a change end to end before handing it back. Use after editing
  application code, before saying a change is done.
allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/checks.sh *) Read Grep
---
Run `${CLAUDE_SKILL_DIR}/scripts/checks.sh` and fix every non-zero result
before reporting back.
```

`[inferred, from verified field semantics in skills.md]`

**State.** The context window, plus whatever the skill writes to disk. Skill
content persists across turns once loaded `[verified: skills.md]`, which is a cost
as much as a feature — keep the body short. Durable cross-session state needs
either files (this repo's run-directory pattern `[observed:
.claude/scripts/new_run.py`, `workspace/runs/ACTIVE_RUN]`) or subagent `memory:`.

**Cost controls.** `model` and `effort` in frontmatter to right-size the turn;
`allowed-tools` to remove prompt round-trips; `disallowed-tools` to remove tools
the skill must never reach for; a script instead of prose for anything with a
deterministic answer.

---

## 2. Goal-based

**Trigger.** `/goal <condition>` — setting a goal starts a turn immediately with
the condition itself as the directive `[verified: goal.md]`. Aliases for clearing:
`clear`, `stop`, `off`, `reset`, `none`, `cancel`. `/goal` with no argument shows
status. One goal per session; a new one replaces the old `[verified: goal.md]`.

Works in `-p`: `claude -p "/goal CHANGELOG.md has an entry for every PR merged this
week"` runs the loop to completion in one invocation. Add `--output-format
stream-json --verbose` or nothing prints until it finishes `[verified: goal.md]`.

**Stop condition — and the biggest correction to the framing.**

`/goal` is documented as a wrapper around a session-scoped **prompt-based Stop
hook**. After each turn the condition and the conversation are sent to the
configured small fast model (Haiku by default on the Claude API), which answers
yes/no with a short reason `[verified: goal.md, "How evaluation works"]`.

Two consequences that change how you build:

1. **The evaluator does not run commands or read files.** "It doesn't run commands
   or read files independently, so write the condition as something Claude's own
   output can demonstrate" `[verified: goal.md]`. "All tests in `test/auth` pass"
   works *only because Claude ran the tests and the output landed in the
   transcript*. A condition about ground truth the agent never printed is
   unverifiable — and an agent that misreports its own test run will be believed.
2. **There is no turn-cap flag.** The `<subject>` framing says the loop ends "when
   the goal is met or a user-defined turn cap is reached." No such cap exists on
   `/goal`. The documented way to bound it is to write the bound into the condition
   text — "include a turn or time clause in the condition, such as `or stop after
   20 turns`" — and "the evaluator judges it from the conversation" `[verified:
   goal.md]`. That makes the cap *model-judged*, not enforced. The only hard turn
   caps in the product are `--max-turns` (print mode only) and subagent frontmatter
   `maxTurns` `[verified: cli-reference / sub-agents.md]`.

So: if you need a genuinely deterministic gate, do not use `/goal`. Write a `Stop`
hook. The docs themselves lay out the three-way choice `[verified: goal.md,
"Compare ways to keep a session running"]`:

| Approach | Next turn starts when | Stops when |
|---|---|---|
| `/goal` | previous turn finishes | a model confirms the condition is met |
| `/loop` | a time interval elapses | you stop it, or Claude decides work is done |
| Stop hook | previous turn finishes | your own script or prompt decides |

A `Stop` hook is the buildable, checked-in, repo-scoped version of `/goal`, and it
comes in three flavors:

- **`type: "command"`** — fully deterministic. Exit 2 blocks the stop; the stderr
  text is fed back as the next instruction. This repo already has a working one
  `[observed: .claude/hooks/verifier_stop_gate.py]`: it reads `claims.jsonl`, and
  while any claim lacks a `PASS`/`FAIL`/`PARTIAL` verdict it prints the unresolved
  IDs to stderr and returns 2. It guards against runaway with
  `if payload.get("stop_hook_active"): return 0`, and wraps `main()` so an
  exception exits 0 rather than wedging the session.
- **`type: "prompt"`** — model judgment on the hook input alone. Returns
  `{"ok": true}` or `{"ok": false, "reason": "..."}`; on `Stop`/`SubagentStop` the
  `reason` is fed back to Claude so it keeps working `[verified: hooks-guide.md]`.
  Model defaults to a fast model, overridable per-hook with `model` `[verified:
  hooks.md prompt/agent fields]`.
- **`type: "agent"`** — spawns a subagent that *can* read files and run commands
  before deciding. Same `ok`/`reason` shape, 60s default timeout, up to 50 tool-use
  turns; `$ARGUMENTS` is replaced with the hook's JSON input `[verified:
  hooks-guide.md]`. Marked **experimental**; the docs say prefer command hooks for
  production `[verified: hooks-guide.md]`.

**What makes a condition deterministic enough to hand off.** Concretely: the
verdict must be computable from an artifact, not from prose. In descending order of
trustworthiness — a script that exits 0/2 on a file it parsed (command hook); an
agent hook that ran the suite itself; a prompt hook or `/goal` reading a transcript
where the agent printed the number. The last is the only one where the worker and
the witness share a source. `[inferred, from the verified evaluator limitation]`

**Files.**

```
.claude/settings.json          # Stop hook registration
.claude/hooks/stop_gate.py     # the gate
```

```json
{ "hooks": { "Stop": [ { "hooks": [
  { "type": "command",
    "command": "python3 \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/stop_gate.py" }
] } ] } }
```

`[observed: this repo's settings.json uses exactly this shape for PreToolUse and
SubagentStart/Stop]`

**State.** A goal active at session end is restored by `--resume`/`--continue`, but
**the turn count, timer, and token-spend baseline all reset on resume**; achieved
or cleared goals are not restored, and `/clear` removes an active goal `[verified:
goal.md]`. That reset is a real hazard for any "or stop after N turns" clause —
resuming silently rearms the budget. Stop-hook state has no such problem because it
lives in a file you control.

**Cost and blast radius.** A goal does not change permissions — in default mode
Claude still asks before unapproved tool calls, so unattended goal turns need
pairing with auto mode `[verified: goal.md]`. Evaluator tokens bill on the small
fast model and are described as typically negligible `[verified: goal.md]`.
`/goal` is unavailable in untrusted workspaces, and when `disableAllHooks` is set
at any level or `allowManagedHooksOnly` is set in managed settings — in each case
it tells you why `[verified: goal.md]`.

A hard turn cap for a hook-driven loop does exist, in an unexpected place:
**`PostToolBatch` blocks on exit 2 and the documented effect is "Stops agentic loop
before next model call"** `[verified: code.claude.com/docs/en/hooks]`. A counter
script on that event is the closest thing to an enforced budget inside an
interactive session `[inferred]`.

---

## 3. Time-based

Two different products, and the `<subject>` framing conflates their durability.

### `/loop` — session-scoped, local

A **bundled skill**, not a built-in command `[verified: scheduled-tasks.md]`.

| What you provide | Example | Behavior |
|---|---|---|
| interval + prompt | `/loop 5m check the deploy` | fixed cron schedule |
| prompt only | `/loop check the deploy` | interval Claude chooses each iteration |
| interval only, or nothing | `/loop` | built-in maintenance prompt, or your `loop.md` |

`[verified: scheduled-tasks.md]`

Interval syntax: leading bare token (`30m`) or trailing clause (`every 2 hours`).
Units `s`, `m`, `h`, `d`. Seconds round up to the minute; awkward intervals like
`7m` or `90m` are rounded to a clean cron step and Claude tells you which
`[verified: scheduled-tasks.md]`.

You can pass a skill as the prompt — `/loop 20m /review-pr 1234`. **As of v2.1.196
a scheduled fire only runs skills Claude is allowed to invoke on its own.** These
arrive as plain text instead of executing: built-in commands like `/permissions`,
`/model`, `/clear`; skills with `disable-model-invocation: true`; skills withheld
by `skillOverrides` or a `Skill` deny rule; MCP prompts like
`/mcp__github__list_prs` `[verified: scheduled-tasks.md]`.

> This is the single most likely build failure for a time-based loop. The habit of
> marking workflow skills `disable-model-invocation: true` — which every stage
> skill in this repo does `[observed: .claude/skills/*/SKILL.md]` — makes them
> silently un-loopable.

**Stop condition.** Weakest of the four. `Esc` while waiting clears the pending
wakeup. In self-paced mode Claude can end it by calling `ScheduleWakeup` with
`stop: true` — a real tool, present in this session `[observed: tool list]`. If an
iteration neither reschedules nor stops, one fallback wakeup fires ~20 minutes
later and the loop ends if that iteration also doesn't reschedule (v2.1.202+).
Fixed-interval loops run until stopped or **seven days elapse** `[verified:
scheduled-tasks.md]`.

**Default prompt.** `.claude/loop.md` (project, wins) or `~/.claude/loop.md`
(user). Plain Markdown, no required structure, **truncated past 25,000 bytes**,
edits take effect on the next iteration, ignored whenever you supply a prompt
`[verified: scheduled-tasks.md]`.

**Underlying tools.** `CronCreate` (5-field expression, prompt, recurring or
one-shot), `CronList`, `CronDelete`. 8-character task IDs; **max 50 scheduled tasks
per session** `[verified: scheduled-tasks.md]`. Cron accepts `*`, single values,
`*/15` steps, `1-5` ranges, `1,15,30` lists; `L`, `W`, `?`, and name aliases like
`MON` are **not** supported. Day-of-week `0` or `7` = Sunday. When both
day-of-month and day-of-week are constrained, a date matches if *either* does
(vixie-cron semantics). All times are local, not UTC `[verified:
scheduled-tasks.md]`.

**Jitter, and why it matters for polling.** Recurring tasks fire up to 30 minutes
*after* the scheduled time (or up to half the interval, for sub-hourly tasks) —
"an hourly job scheduled for `:00` may fire anywhere up to `:30`." One-shot tasks
at the top or bottom of the hour fire up to 90 seconds *early*. The offset derives
from the task ID, so it's stable per task. To dodge one-shot jitter, schedule at a
minute that isn't `:00` or `:30` — `3 9 * * *` rather than `0 9 * * *` `[verified:
scheduled-tasks.md]`.

**State and survival.** The framing says `/loop` "dies when the session closes."
More precisely `[verified: scheduled-tasks.md]`:

- Tasks fire only while Claude Code is running **and idle**; a task due mid-turn
  waits for the turn to end.
- No catch-up for missed fires — one fire when idle, not one per missed interval.
- Starting a fresh conversation clears all session-scoped tasks.
- `--resume`/`--continue` **restores** unexpired recurring tasks and one-shots whose
  time hasn't passed. Background Bash and Monitor tasks are never restored.
- `/bg` carries `/loop` tasks into a background session, which keeps running with no
  terminal.
- Recurring tasks hard-expire 7 days after creation, firing once more then deleting
  themselves.
- The task list is stored **in the project's `.claude` directory**, and scheduling
  fails if that directory or the task file is a symlink (before v2.1.216 it wrote
  through the link).

*The exact filename of that task file is **Not determined**.* No `/loop` has run in
this workspace, so nothing exists to inspect `[observed: .claude/ contains only
agent-memory, agents, hooks, rules, scripts, settings.json, skills]`. Running one
`/loop` and diffing `.claude/` would settle it, as would grepping the CLI bundle at
`/opt/claude-code/` `[observed: readlink of $(which claude)]`.

**Kill switch.** `CLAUDE_CODE_DISABLE_CRON=1` disables the scheduler entirely — the
cron tools and `/loop` become unavailable and scheduled tasks stop firing
`[verified: scheduled-tasks.md]`.

### `/schedule` — cloud Routines

Real, and documented on `routines.md` rather than `commands.md` — a fetch summary
of `commands.md` reported `/schedule` as nonexistent, which is wrong; the
`scheduled-tasks.md` comparison table also lists "Customizable schedule: Via
`/schedule` in the CLI" for the cloud column `[verified: routines.md +
scheduled-tasks.md; contradicts the commands.md summary]`. Alias: `/routines`.
Subcommands: `/schedule list`, `/schedule update`, `/schedule run`; plus natural
language, e.g. `/schedule daily PR review at 9am`, `/schedule tomorrow at 9am,
summarize yesterday's merged PRs` `[verified: routines.md]`.

Routines are in **research preview** `[verified: routines.md]`.

Three trigger types on one routine: **Schedule** (presets hourly/daily/weekdays/
weekly; custom cron via `/schedule update`, **minimum interval one hour**, faster
expressions rejected), **API** (POST to a per-routine `/fire` endpoint with a
bearer token), **GitHub** (`pull_request` and `release` event categories, with
filters on author, title, body, base/head branch, labels, is-draft, is-merged)
`[verified: routines.md]`.

What this costs you architecturally: a routine runs on Anthropic-managed cloud
infrastructure with **no local file access — each repository is cloned fresh every
run** `[verified: routines.md + scheduled-tasks.md comparison table]`. "The session
can run shell commands, use skills committed to the cloned repository, and call any
connectors you include" `[verified: routines.md]` — so `.claude/skills/` travels if
it's checked in. **Whether `.claude/settings.json` hooks fire in a routine run is
Not determined**; routines.md names skills and connectors but never mentions hooks,
and I found no page that states it either way. A routine whose prompt writes a
sentinel file from a `SessionStart` hook would settle it.

Routines "run autonomously as full Claude Code cloud sessions: there is no
permission-mode picker and no approval prompts during a run" `[verified:
routines.md]` — the blast radius is bounded by repository selection, the cloud
environment's network policy and variables, and which connectors you attach, not
by permission rules.

Fire-text safety, worth knowing before wiring alerting to it: the optional `text`
field arrives wrapped in a `<routine-fire-payload>` block labeled untrusted, and
**the routine's saved prompt must explicitly opt in to acting on it** — otherwise
it's inert context. Anyone holding the bearer token can send `text` `[verified:
routines.md]`.

`/schedule` is hidden or rejected under Console API keys, Anthropic profiles,
Bedrock/Vertex/Foundry logins, when `DISABLE_TELEMETRY` / `DO_NOT_TRACK` /
`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` / `DISABLE_GROWTHBOOK` is set, inside a
Claude Code on the web session, or when an org disables routines `[verified:
routines.md troubleshooting]`. It requires a claude.ai subscription login.

**Cost controls.** Routines have a **daily cap on runs per account** on top of
normal subscription limits; one-off runs don't count against it. GitHub webhook
events are subject to per-routine and per-account hourly caps during the preview,
and events beyond the limit are dropped `[verified: routines.md]`.

---

## 4. Proactive

Not a distinct primitive — a composition, exactly as the framing says. The
composition has a specific shape once you name the parts.

**Trigger.** Something outside the session. In practice: a GitHub trigger or API
`/fire` on a Routine `[verified: routines.md]`; a repository event delivered into a
session as `<github-webhook-activity>` via PR-activity subscription `[observed:
this session's tool surface]`; or a schedule.

**Stop condition.** Whatever the composed inner loop uses. The honest version: the
outer trigger has no stop condition at all — it fires forever until you delete it —
so the *inner* run must terminate on its own. That is what the caps are for: the
7-day `/loop` expiry, the routine daily cap, `maxTurns` on subagents, `--max-turns`
in `-p`.

**Driving primitives.** Routine (outer trigger) + a committed skill (the procedure)
+ subagents (the fan-out) + hooks (the guards). Two supporting mechanisms:

- **Auto mode** — a permission mode, `auto`, in which a background classifier
  reviews each action rather than prompting you. `/goal` + auto mode is the
  documented pairing for unattended turns: "auto mode removes per-tool prompts, and
  `/goal` removes per-turn prompts" `[verified: goal.md]`. Full mode list from the
  docs sweep: `default` (alias `manual`, v2.1.200+), `acceptEdits`, `plan`, `auto`,
  `dontAsk`, `bypassPermissions` `[verified: permission-modes.md]` — matching the
  `permissionMode` values in subagent frontmatter `[verified: sub-agents.md]` and
  the `permission_mode` values in hook input `[verified: hooks reference]`.
  > **Conflict, recorded not resolved.** A summary of `settings.md` reported
  > `permissions.defaultMode` accepting `"ask"`, `"auto"`, `"skip"`, which matches
  > none of the six mode names above. I did not open a page that states
  > `defaultMode`'s accepted values directly. Test `defaultMode` before relying on
  > it; treat the six-name list as authoritative for `--permission-mode` and
  > frontmatter `permissionMode` only.
- **Dynamic workflows** — a JavaScript orchestration script Claude writes and the
  runtime executes in the background, with intermediate results in script variables
  rather than context. Gated behind the `ultracode` keyword or `/effort ultracode`,
  and **`ultracode` works only in human-typed prompts — it does not trigger from
  `-p`, the API, scheduled tasks, or webhooks** `[verified: workflows.md]`. That
  exclusion is precisely the proactive case, so a routine cannot opt itself into
  workflows via the keyword. Size guideline via `/config` or `workflowSizeGuideline`
  in settings: `unrestricted` / `small` (<5) / `medium` (<15, default) / `large`
  (<50); up to 16 concurrent and 1,000 total agents per run `[verified:
  workflows.md]`.

**Fitting tasks.** Recurring streams of well-defined work: PR triage, CI babysitting,
alert investigation, backlog grooming, docs drift.

**Files.** The buildable part is entirely ordinary:

```
.claude/skills/triage-pr/SKILL.md   # the procedure — must be committed
.claude/agents/fresh-reviewer.md    # the second opinion
.claude/settings.json               # guards that survive unattended runs
```

with the routine itself living in your claude.ai account, not the repo. Note that
`disable-model-invocation: true` on `triage-pr` would break a `/loop`-driven
version of the same thing (see §3) `[verified: scheduled-tasks.md]`.

**State.** Nothing survives a routine run except what's pushed. Claude pushes to
`claude/`-prefixed branches, which are always accepted; pushes to other branches are
rejected if the branch is protected, someone else has an open PR from it, or it
carries commits authored by someone other than you `[verified: routines.md]`. For
in-session proactive loops, durable state is files plus subagent memory (below).

**Blast radius.** A run status of green "means the session started and exited
without an infrastructure error. It does not mean the task in your prompt
succeeded" `[verified: routines.md]`. Anything you build here needs its own
success signal written into an artifact, not inferred from run status.

---

## Cross-cutting: the surrounding system

The framing's claim — quality depends on a clean codebase, reachable docs, and a
fresh-context reviewer — maps onto specific fields rather than general hygiene.

**Fresh context is a frontmatter field, not an orchestration.** `context: fork` runs
a skill in a subagent that "won't have access to your conversation history"
`[verified: skills.md]`; `agent:` picks the type; `background: false` (v2.1.218+)
waits for the result in the invoking turn. A subagent likewise "runs in its own
context window" and the main conversation's auto memory **is not loaded** into it
`[verified: sub-agents.md]`. That last point is what makes the reviewer unbiased —
and also what makes it uninformed, which is why the docs warn that `context: fork`
"only makes sense for skills with explicit instructions"; a forked skill that is
just guidelines "receives the guidelines but no actionable prompt, and returns
without meaningful output" `[verified: skills.md]`.

**The filesystem is the only reliable bus between isolated contexts.** This repo
demonstrates the pattern at full scale: subagents never see each other, every stage
reads and writes exact paths under `workspace/runs/<run-id>/`, and
`workspace/runs/ACTIVE_RUN` holds the pointer `[observed: CLAUDE.md +
.claude/rules/workspace-protocol.md]`. Each agent ends with one line of JSON —
`{"ok": ..., "outputs": [...], "notes": ...}` — so the orchestrator gets a parseable
result rather than prose `[observed: .claude/rules/workspace-protocol.md]`. Any loop
that must survive a context window ending needs this shape.

**What actually survives.** In order of durability:

| Mechanism | Survives compaction | Survives session close | Path |
|---|---|---|---|
| Files you write | yes | yes | anywhere |
| Subagent `memory:` | yes | yes | `.claude/agent-memory/<name>/` (project), `~/.claude/agent-memory/<name>/` (user), `.claude/agent-memory-local/<name>/` (local) |
| `SessionStart` hook output | n/a | yes — re-injected | `.claude/settings.json` |
| Skill content in context | no | no | — |
| `/goal` condition | yes | yes on `--resume`, but counters reset | session |
| `/loop` tasks | yes | on `--resume` within 7 days | project `.claude/` (filename undetermined) |

Subagent memory injects the first 200 lines or 25KB of `MEMORY.md`, whichever comes
first, and auto-enables Read/Write/Edit so the agent can curate it; it is disabled
wholesale by `autoMemoryEnabled: false` or `CLAUDE_CODE_DISABLE_AUTO_MEMORY`
`[verified: sub-agents.md]`. Both memory-enabled agents here use `memory: project`
`[observed: .claude/agents/{ideator,problem-investigator}.md → .claude/agent-memory/]`.

The `SessionStart` hook is the underrated one: it re-derives loop state on every
session and prints it into context. This repo's reads `ACTIVE_RUN`, runs
`ledger.py status`, and prints an explicit "Suggested next step: /discover"
`[observed: .claude/hooks/session_start.py]` — which fired at the top of this very
session `[observed: SessionStart hook output]`. It also swallows every exception and
exits 0, with the comment "a broken hook must never block a session" — the right
default for `SessionStart`, which doesn't block on exit 2 anyway `[verified: hooks
exit-code-2 table]`.

## Cross-cutting: cost and blast radius

**Right-size the primitive.** Per-component knobs, in the order they bite:

| Knob | Where | Effect |
|---|---|---|
| `maxTurns` | subagent frontmatter | hard cap on agentic turns |
| `--max-turns N` | CLI, **print mode only** | hard cap; errors on limit |
| `PostToolBatch` hook exit 2 | settings | "Stops agentic loop before next model call" |
| `model` | skill / subagent frontmatter | route cheap work to `haiku`, expensive to `opus` |
| `effort` | skill / subagent frontmatter | `low`…`max` |
| `tools` / `disallowedTools` | subagent | constrain the reachable surface |
| `allowed-tools` / `disallowed-tools` | skill | per-turn grant / removal |
| `permissions.allow` / `deny` / `ask` | settings | session-wide |
| `permissionMode` | subagent frontmatter | per-agent mode |
| `isolation: worktree` | subagent | isolated repo copy |
| `workflowSizeGuideline` | settings | `small`/`medium`/`large`/`unrestricted` |
| `autoCompactWindow` | settings | 100k–1M tokens before compacting |

This repo already differentiates: `effort: high` for ideator, solver, auditor,
paper-writer; `effort: medium` for evaluator and refiner; `maxTurns: 40` on solver
alone — the only agent that iterates `[observed: .claude/agents/*.md]`. No agent
sets `model`, so all inherit `[observed: same]`. That's the pattern: cap the one
that loops, downgrade effort on transcription-shaped work.

**Deny beats allow for blast radius.** The project settings here deny
`Bash(pip install*)`, `Bash(pip3 install*)`, `Bash(rm -rf*)` while allowing only
scoped script paths `[observed: .claude/settings.json]`. Deny rules and
`disallowedTools` are the controls that hold under auto mode, where per-tool prompts
are gone by design.

**Scripts over reasoning, concretely.** The line to draw: if the answer is a
function of an artifact, it's a script. This repo's split is a usable model —
`ground_check.py`, `extract_claims.py`, `verify_claims.py`, `bib_validate.py`, and
`chain_of_evidence.py` compute verdicts; agents are only asked to judge what a
script cannot, like citation entailment and method-code alignment `[observed:
.claude/scripts/ + .claude/agents/claim-verifier.md]`. The reusable move: pre-approve
the script path in `permissions.allow` or skill `allowed-tools` so it runs with no
prompt `[observed: `"Bash(python3 .claude/scripts/*)"` in settings.json]`, and let
the hook or skill call it rather than reasoning the steps each iteration.

**Pilot before the full run.** `--max-turns` plus `--output-format json` gives you
per-run cost in the result `[verified: headless.md, via docs sweep]`. For a
branch-fanout loop, the equivalent is running one branch before B.

**Two guards specific to unattended loops.** (1) Always honor `stop_hook_active` in
a Stop hook or you will loop forever `[observed: verifier_stop_gate.py, and the
field is documented in the hooks reference]`. (2) `continue: false` in hook JSON
"stops Claude entirely" and "takes precedence over event-specific decisions"
`[verified: hooks reference]` — that's the emergency brake for a loop that has gone
wrong, and it works on any event.
