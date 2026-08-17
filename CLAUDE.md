# Researcher Team — an autonomous research pipeline (ScientistOne recreation)

This project recreates Google's **ScientistOne** (arXiv 2605.26340) end-to-end
autonomous research system using only Claude Code primitives. Claude Code IS
the runtime: subagents are the researchers, skills are the stages, hooks are
the integrity guards, and the filesystem is the message bus.

## Pipeline

```
Task + Seeds → [Problem Investigator] → brief.md
            → [Discovery: Ideator → B parallel branches × (Solve → Evaluate → Audit)
               → Rank+Select → distilled feedback → next iteration] × I
            → best solution + logs
            → [Paper Writer: CONCEIVE → GROUND(script) → CRITIC → RESOLVE+COMPOSE] → draft.md
            → [Claim Verifier: extract(script) → verify → Refiner] → final/paper.md
            → chain_of_evidence.py audit
```

Stages are driven by slash commands: `/research` (end-to-end), `/investigate`,
`/discover`, `/write-paper`, `/verify-claims`, `/run-status`, `/paper-to-latex`.

## Run protocol — the filesystem is the message bus

Subagents never see each other's context. ALL stage input/output flows through
the run directory `workspace/runs/<run-id>/`; `workspace/runs/ACTIVE_RUN`
holds the current run id. Layout:

| Path | Written by |
|---|---|
| `run-config.json`, `ledger.jsonl` | scripts/hooks |
| `literature/<key>.md`, `bibliography.jsonl`, `investigation/`, `brief.md` | problem-investigator |
| `iterations/iN/ideas.md`, `proposals/pK.md` | ideator |
| `iterations/iN/branches/bK/{plan.md,solution.py,solve.log}` | solver K |
| `iterations/iN/branches/bK/eval.json` | evaluator |
| `iterations/iN/branches/bK/audit.md` | auditor |
| `iterations/iN/{ranking.md,distilled-feedback.md}` | main agent |
| `best/` (SELECTED.json + copies of winner) | main agent |
| `paper/research-representation.md` | paper-writer (conceive) |
| `paper/ground-report.json` | ground_check.py |
| `paper/critic-report.md` | paper-critic |
| `paper/draft.md` | paper-writer (resolve-compose) |
| `paper/claims.jsonl` | extract_claims.py / verify_claims.py / claim-verifier |
| `paper/votes/` (best-of-N verdict votes) | verdict_votes.py |
| `paper/verification-report.md` | claim-verifier |
| `final/paper.md` | refiner / main agent |

All paths inside artifacts are run-directory-relative.

## Autopilot (optional) — the pipeline as an enforced loop

`.claude/hooks/run_stop_gate.py` can hold the main session on the pipeline
instead of relying on the orchestrator to remember all five stages across
compaction. It is **inert unless armed**, and armed per run:

```
python3 .claude/scripts/autopilot.py arm [--max N]   # default 12 continuations
python3 .claude/scripts/autopilot.py status
python3 .claude/scripts/autopilot.py disarm
```

Arming writes `workspace/runs/<id>/AUTOPILOT`. The first session to finish a
turn claims the run; other sessions in this repo are unaffected. On each stop
the gate reads the artifact ladder (`final/paper.md` → `paper/draft.md` →
`best/SELECTED.json` → `brief.md`), and while a stage is outstanding it exits
2 with the next stage as the instruction. It disarms itself on completion or
when the continuation budget is spent, and reports either through a user-
visible message.

The same hook runs on `PreToolUse` and denies `AskUserQuestion` while the loop
is being driven by the owning session: nobody is watching, so a question would
stall the run indefinitely rather than end the turn and let the stop gate push
it forward. It is inert for every other tool, for unarmed runs, and for a run
this session does not own. Every fire is logged to `ledger.jsonl` as
`autopilot_continue` / `autopilot_budget_exhausted` / `autopilot_complete` /
`autopilot_blocked_question`.

The budget lives in the `AUTOPILOT` file rather than in session state, so it
survives `--resume` and cannot be silently rearmed. Kill switches:
`python3 .claude/scripts/autopilot.py disarm`, deleting the `AUTOPILOT` file,
or `RESEARCH_AUTOPILOT_OFF=1`.

Note for the continued agent: stage skills set `disable-model-invocation:
true`, so `/discover` and friends are not yours to invoke. Read
`.claude/skills/<stage>/SKILL.md` and carry the stage out directly. If a
stage's required input artifact is missing, disarm and report — never
fabricate a stand-in.

## Evidence tags (Chain-of-Evidence)

Every factual claim in paper artifacts carries an inline tag binding it to an
artifact:

- `[EV:score:iterations/i2/branches/b3/eval.json#accuracy]` — number in a JSON artifact
- `[EV:log:best/solve.log:L42]` — log line(s)
- `[EV:cite:lecun1998gradient]` — key that EXISTS in `bibliography.jsonl`
- `[EV:artifact:best/solution.py]` — artifact existence
- `[EV:config:run-config.json#branches]` — run configuration value

A citation key must exist in `bibliography.jsonl` BEFORE it is used — a
PreToolUse hook blocks writes of unknown keys to paper files, whether the
write arrives as Write, Edit, or a shell command (redirect, `tee`, `sed -i`,
interpreter one-liner). Reading is never blocked. Statements that
cannot be tagged go in an explicit `## Assumptions` section.

## Hard rules

1. **Scores come only from execution.** The only legitimate score is the one
   in `eval.json`, produced by running `task/evaluate.py`. Never estimate,
   never round up, never quote a metric that has no artifact.
2. **A paper you did not retrieve and read does not exist.** No citation
   without a `bibliography.jsonl` entry with provenance.
3. **Branches are isolated.** A solver owns exactly one
   `iterations/iN/branches/bK/` directory and never reads sibling branches.
4. **FAIL audit = disqualified**, regardless of score.
5. **Unsupported claims get dropped or softened, not defended.**
6. **Verification and repair are separate.** The claim-verifier never edits
   the draft; the refiner never issues verdicts.
7. **A judgment without a quote does not count.** Every LLM PASS/PARTIAL
   verdict on a citation or methodological claim carries a `quote` that
   appears verbatim in the evidence source; `verify_claims.py` discards
   ungrounded verdicts (QUOTE-CHECK → FAIL). When `verifier_votes` ≥ 2,
   LLM verdicts are sampled in independent contexts and disagreements
   resolve to the weakest verdict.

## Agent roster

`problem-investigator`, `ideator`, `solver`, `evaluator`, `auditor`,
`paper-writer`, `paper-critic`, `claim-verifier`, `refiner` — see
`.claude/agents/`. Subagents finish by replying with one line of JSON:
`{"ok": true|false, "outputs": [paths], "notes": "..."}`.

**Protocol-skill wiring** — a subagent never sees the orchestrator's context,
so every protocol it is judged against is preloaded into it via `skills:`
(these skills must therefore never set `disable-model-invocation`, which
would block preloading):

| skill | preloaded into | orchestrator use |
|---|---|---|
| `citation-provenance` | problem-investigator | — |
| `evaluation-protocol` | ideator, solver, evaluator, auditor | Rank+Select reads eval.json/audit.md |
| `evidence-tagging` | paper-writer, paper-critic, claim-verifier, refiner | — |
| `distill-feedback` | — (main agent only) | invoked at step 6 of each iteration |

**Hook coverage** — three hooks are session-level (`settings.json`) and two are
agent-scoped (agent frontmatter). Nothing is orphaned; the agent-scoped pair is
deliberately narrow:

| hook | wired in | reaches |
|---|---|---|
| `session_start.py` | settings `SessionStart` | main session (subagents get no SessionStart) |
| `run_stop_gate.py` | settings `Stop` + `PreToolUse:AskUserQuestion` | main session — the autopilot loop |
| `ledger_log.py` | settings `SubagentStart`/`SubagentStop` | all 9 agents |
| `citation_guard.py` | settings `PreToolUse:Write\|Edit\|Bash` | every agent that writes |
| `paper_area_guard.py` | frontmatter | ideator, solver, evaluator, auditor |
| `verifier_stop_gate.py` | frontmatter `Stop` (registers as SubagentStop) | claim-verifier |

`paper_area_guard` is intentionally NOT on paper-writer, paper-critic,
claim-verifier, refiner or problem-investigator — writing the narrative record
is their job.

**Rule coverage** — `.claude/rules/workspace-protocol.md` has no `paths:`, so
every agent always carries it. The other three activate on touching their
files: `evidence-tags.md` (`paper/**`, `final/**`), `bibliography.md`
(`literature/**`, `bibliography.jsonl`), `branch-discipline.md`
(`branches/**`). They intentionally restate what the protocol skills preload —
a second delivery path that also reaches the orchestrator, which preloads no
skills.

**Parallel fan-out**: when a stage calls for B solver (or evaluator, or
auditor) runs, launch ALL B subagent tasks in a SINGLE message so they run
concurrently. Never launch branch agents sequentially.

## Offline mode

If `run-config.json` has `"offline": true` (or web tools fail), the
investigator works from `workspace/seeds/` only and records provenance as
`seed`/`user-provided`. The demo task `digits` runs fully offline
(requires `python3` with `scikit-learn` installed).
