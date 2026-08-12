# Researcher Team

An autonomous scientific-research pipeline built **entirely from Claude Code
primitives** — a working recreation of Google's
[ScientistOne](https://arxiv.org/abs/2605.26340) ("Towards Human-Level
Autonomous Research via Chain-of-Evidence", Google Cloud AI Research,
ICML 2026) where Claude Code itself is the runtime:

- **Subagents** (`.claude/agents/`) are the researchers — investigator,
  ideator, parallel solvers, evaluator, auditor, writers, verifiers.
- **Skills / slash commands** (`.claude/skills/`) are the pipeline stages.
- **Hooks** (`.claude/settings.json` + `.claude/hooks/`) are deterministic
  integrity guards — hallucinated citations are blocked at write time, and
  stop gates hold an agent on the job until its stage is genuinely finished.
- **Memory** (`CLAUDE.md`, `.claude/rules/`, per-agent project memory) is the
  shared constitution and cross-run learning.
- **The filesystem** (`workspace/runs/<run-id>/`) is the message bus between
  agents.

```
Task + Seeds → [Problem Investigator] → Research Brief
            → [Ideator → B parallel branches × (Solve → Evaluate → Audit)
               → Rank+Select → distilled feedback] × I iterations
            → [Paper Writer: CONCEIVE → GROUND → CRITIC → RESOLVE → COMPOSE]
            → [Claim Verifier: Extract → Verify → Refine]
            → final/paper.md  (+ Chain-of-Evidence audit)
```

## Quickstart

Requirements: [Claude Code](https://code.claude.com), `python3` with
`scikit-learn` (`pip install scikit-learn`) for the bundled demo task.

```bash
git clone <this repo> && cd researcher_team
claude
```

Then, inside Claude Code:

```
/research "Improve classification accuracy on sklearn digits within a 60-second training budget" --task digits --branches 5 --iterations 2
```

Add `--offline` to skip web literature search (the investigator then works
from `workspace/seeds/` — three example seed notes ship with the repo).

## Commands

| Command | Stage |
|---|---|
| `/research "<topic>" [--task T] [--branches B] [--iterations I] [--offline]` | Full pipeline, end to end |
| `/investigate` | Stage 1: citation graph → elite pool → Research Brief |
| `/discover` | Stage 2: Ideator + Parallel Explore-Exploit branches |
| `/write-paper` | Stage 3: CONCEIVE → GROUND → CRITIC → RESOLVE → COMPOSE |
| `/verify-claims` | Stage 4: claim extraction → verification → refine → CoE audit |
| `/run-status` | Inspect the active run (any time) |
| `/paper-to-latex` | Optional: render final/paper.md to .tex / PDF |

Every stage persists its artifacts, so any stage can be re-run independently
against the active run (`workspace/runs/ACTIVE_RUN`).

### Autopilot (optional)

By default the orchestrator has to remember to carry a run through all five
stages, which is fragile across a long run with context compaction. Arming
the autopilot makes that a loop the runtime enforces:

```bash
python3 .claude/scripts/autopilot.py arm [--max N]   # default 12 continuations
python3 .claude/scripts/autopilot.py status
python3 .claude/scripts/autopilot.py disarm
```

A `Stop` hook then checks the artifact ladder every time the session tries to
finish, and while a stage is outstanding it blocks the stop and hands the next
stage back as the instruction. It disarms itself on completion or when the
continuation budget is spent. While the loop is running it also declines
`AskUserQuestion` — nobody is watching, so a question would stall the run
rather than advance it.

The hook is **inert unless armed**, and armed per run: the first session to
finish a turn claims it, so other sessions in the repo are never held. The
budget lives in `workspace/runs/<id>/AUTOPILOT` rather than in session state,
so it survives `--resume` and cannot be silently rearmed. To stop a loop:
`autopilot.py disarm`, delete the `AUTOPILOT` file, or set
`RESEARCH_AUTOPILOT_OFF=1`.

## Chain-of-Evidence

Every factual sentence in the paper carries an inline evidence tag binding it
to a run artifact:

```
Accuracy reaches 0.9852 on the held-out split [EV:score:best/eval.json#score].
kNN error is bounded by twice the Bayes error [EV:cite:cover1967nearest].
```

Deterministic scripts enforce the chain (`.claude/scripts/`):

- `ground_check.py` — the GROUND stage: opens every tagged artifact and
  verifies the sentence against it (grounding ratio must reach 0.85).
- `verify_claims.py` — numerical claims within ±5% of their artifact,
  citation/artifact existence.
- `chain_of_evidence.py` — the paper's four integrity checks: Score
  Verification, Reference Verification, Specification Violation,
  Method-Code Alignment.
- `citation_guard.py` (PreToolUse hook) — writing a citation key that is not
  in `bibliography.jsonl` into a paper file is **blocked at tool level**;
  references must be retrieved and recorded by the investigator first.

Scores are never estimated: the only official metric is the one produced by
executing `workspace/tasks/<task>/evaluate.py`, and a separate auditor agent
disqualifies branches that game it.

## Adding your own task

Create `workspace/tasks/<name>/` with:

- `task.md` — objective, data protocol, solution contract, constraints, metric.
- `evaluate.py` — executable evaluator: takes `solution.py` path as argv[1],
  prints one JSON object (`{"task", "metric", "score", "constraint_ok",
  "violations", ...}`) to stdout. It is the single source of official scores.

Then: `/research "<topic>" --task <name>`.

## Smoke test (fully offline)

1. `claude` in the repo — the SessionStart hook should print
   "no active run".
2. `/research "Improve classification accuracy on sklearn digits within a 60-second training budget" --task digits --branches 2 --iterations 1 --offline`
3. When it finishes, verify in `workspace/runs/<run-id>/`:
   - `brief.md` cites only keys in `bibliography.jsonl`
     (`python3 .claude/scripts/bib_validate.py <run-id>` passes);
   - `iterations/i1/branches/b1,b2/` each hold `solution.py`, a real
     `eval.json` score, and an `audit.md` verdict;
   - `paper/ground-report.json` grounding ratio ≥ 0.85;
   - `paper/verification-report.md` has no unresolved claims;
   - `final/paper.md` exists and
     `python3 .claude/scripts/chain_of_evidence.py <run-id>` prints ALL PASS.
4. Negative checks: ask Claude to add a sentence citing `fake2020paper` to
   `final/paper.md` — the citation guard must block it. Inflate a score in
   `paper/draft.md` by 20% and re-run `/verify-claims` — the claim must FAIL
   and the refiner must correct it.

## Repository map

```
CLAUDE.md                  # pipeline constitution (loaded by every agent)
.claude/agents/            # 9 researcher subagents
.claude/skills/            # 7 stage commands + 4 internal protocol skills
.claude/rules/             # path-scoped rules (evidence tags, bibliography, branches)
.claude/hooks/             # 6 deterministic guards (citation, branch, ledger,
                           #   session brief, verifier stop-gate, pipeline autopilot)
.claude/scripts/           # stdlib-only pipeline scripts (GROUND, claims, CoE audit)
research/                  # design notes on the loop primitives behind the pipeline
workspace/tasks/digits/    # bundled offline demo task
workspace/seeds/           # seed literature for offline runs
workspace/runs/            # run artifacts (gitignored)
```
