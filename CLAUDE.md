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
| `paper/verification-report.md` | claim-verifier |
| `final/paper.md` | refiner / main agent |

All paths inside artifacts are run-directory-relative.

## Evidence tags (Chain-of-Evidence)

Every factual claim in paper artifacts carries an inline tag binding it to an
artifact:

- `[EV:score:iterations/i2/branches/b3/eval.json#accuracy]` — number in a JSON artifact
- `[EV:log:best/solve.log:L42]` — log line(s)
- `[EV:cite:lecun1998gradient]` — key that EXISTS in `bibliography.jsonl`
- `[EV:artifact:best/solution.py]` — artifact existence
- `[EV:config:run-config.json#branches]` — run configuration value

A citation key must exist in `bibliography.jsonl` BEFORE it is used — a
PreToolUse hook blocks writes of unknown keys to paper files. Statements that
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

## Agent roster

`problem-investigator`, `ideator`, `solver`, `evaluator`, `auditor`,
`paper-writer`, `paper-critic`, `claim-verifier`, `refiner` — see
`.claude/agents/`. Subagents finish by replying with one line of JSON:
`{"ok": true|false, "outputs": [paths], "notes": "..."}`.

**Parallel fan-out**: when a stage calls for B solver (or evaluator, or
auditor) runs, launch ALL B subagent tasks in a SINGLE message so they run
concurrently. Never launch branch agents sequentially.

## Offline mode

If `run-config.json` has `"offline": true` (or web tools fail), the
investigator works from `workspace/seeds/` only and records provenance as
`seed`/`user-provided`. The demo task `digits` runs fully offline
(requires `python3` with `scikit-learn` installed).
