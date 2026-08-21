# Contributing to Researcher Team

Thank you for your interest in contributing to **Researcher Team**! We're excited to collaborate with you. This guide will help you get started, whether you're fixing a bug, adding a research task, improving an agent or skill, or clarifying the documentation.

---

## Table of Contents
1. [Code of Conduct](#code-of-conduct)
2. [How Can You Contribute?](#how-can-you-contribute)
3. [Getting Started](#getting-started)
4. [Project Layout](#project-layout)
5. [Development Workflow](#development-workflow)
6. [Issue Reporting Guidelines](#issue-reporting-guidelines)
7. [Pull Request Guidelines](#pull-request-guidelines)
8. [Code Style and Standards](#code-style-and-standards)
9. [Community Support](#community-support)

---

## Code of Conduct
To maintain a welcoming and inclusive environment, all contributors are expected to adhere to our [Code of Conduct](CODE_OF_CONDUCT.md). Please take a moment to review it.

---

## How Can You Contribute?

There are many ways to contribute:
- **Reporting bugs**: A hook that blocks a legitimate write, a stage that produces a malformed artifact, a script that mis-verifies a claim.
- **Suggesting features**: New pipeline stages, better ranking/selection, additional integrity checks.
- **Adding research tasks**: New `workspace/tasks/<name>/` directories with a `task.md` and an executable `evaluate.py`.
- **Improving agents, skills, rules, or hooks**: Sharper prompts, tighter guards, better protocol coverage.
- **Improving documentation**: `README.md`, `CLAUDE.md`, `docs/`, and `research/` notes.
- **Testing**: Run the offline smoke test and the hook self-test on your platform and report what breaks.

---

## Getting Started

### 1. Fork and Clone the Repository
1. Fork the repository by clicking the "Fork" button on the top-right of this page.
2. Clone your fork to your local machine:
   ```bash
   git clone https://github.com/<your-username>/researcher_team.git
   ```
3. Navigate to the project directory:
   ```bash
   cd researcher_team
   ```

### 2. Requirements
- [Claude Code](https://code.claude.com) — it is the runtime for the whole pipeline.
- `python3` (3.10+). The pipeline scripts in `.claude/scripts/` are **stdlib-only**.
- `scikit-learn` for the bundled demo task: `pip install scikit-learn`.

No API keys beyond your Claude Code login are required; the demo task runs fully offline.

### 3. Run the Offline Smoke Test
Start Claude Code in the repo — the `SessionStart` hook should print "no active run":
```bash
claude
```
Then, inside Claude Code:
```
/research "Improve classification accuracy on sklearn digits within a 60-second training budget" --task digits --branches 2 --iterations 1 --offline
```
When it finishes, check the artifacts listed under **Smoke test** in the [README](README.md#smoke-test-fully-offline) and run the integrity audits:
```bash
python3 .claude/scripts/bib_validate.py <run-id>
python3 .claude/scripts/chain_of_evidence.py <run-id>
```

### 4. Run the Hook Self-Test
Before and after touching anything in `.claude/hooks/` or `.claude/scripts/`:
```bash
python3 .claude/scripts/selftest_hooks.py
```

---

## Project Layout

```
CLAUDE.md                  # pipeline constitution (loaded by every agent)
.claude/agents/            # researcher subagents
.claude/skills/            # stage commands + internal protocol skills
.claude/rules/             # workspace protocol + path-scoped rules
.claude/hooks/             # deterministic integrity guards
.claude/scripts/           # stdlib-only pipeline scripts (GROUND, claims, CoE audit)
docs/                      # guardrails mapping, evaluation report
research/                  # design notes on the loop primitives
workspace/tasks/           # research tasks (task.md + evaluate.py)
workspace/seeds/           # seed literature for offline runs
workspace/runs/            # run artifacts (gitignored)
```

Read [`CLAUDE.md`](CLAUDE.md) first: it defines the run protocol, the evidence-tag format, the hard rules, and how agents, skills, rules, and hooks are wired together. Changes to any of those must keep that document accurate.

---

## Development Workflow

### 1. Create a Branch
Create a new branch for your feature or bugfix:
```bash
git checkout -b feature/your-feature-name
```

### 2. Make Your Changes
- Follow the [Code Style and Standards](#code-style-and-standards).
- If you add or modify an agent, make sure every protocol skill it is judged against is listed in its `skills:` frontmatter (see the **Protocol-skill wiring** table in `CLAUDE.md`).
- If you add or modify a hook, add or update a case in `.claude/scripts/selftest_hooks.py`.
- If you add a task, make sure `evaluate.py` prints exactly one JSON object to stdout and is the only source of the official score.
- Never commit anything under `workspace/runs/` — it is gitignored on purpose.

### 3. Commit Your Changes
Write a meaningful commit message describing your changes:
```bash
git add .
git commit -m "Fix: [Short description of fix or feature]"
```

### 4. Push Your Branch
Push your branch to your fork:
```bash
git push origin feature/your-feature-name
```

### 5. Open a Pull Request
Go to the original repository and open a Pull Request (PR) from your branch to the default branch. Ensure your PR includes:
- A clear title and description.
- References to relevant issues (e.g., `Fixes #123`).
- The output of `selftest_hooks.py` and, where relevant, the `chain_of_evidence.py` audit of a smoke-test run.

### 6. Add Yourself as a Contributor
Once your Pull Request is reviewed and accepted, please follow the [CONTRIBUTORS](CONTRIBUTORS.md) file.

---

## Issue Reporting Guidelines

When reporting a bug:
1. **Search for duplicates**: Check the [issues](https://github.com/EmmanuelRTM/researcher_team/issues) to see if it is already reported.
2. **Provide details**: Include:
   - The exact slash command and flags you ran.
   - Expected and actual behavior.
   - The relevant lines from `workspace/runs/<run-id>/ledger.jsonl` and any hook message (e.g., a citation-guard block).
3. **Environment details**:
   - Operating system.
   - Claude Code version (`claude --version`) and Python version.
   - Whether the run was `--offline`.

For feature requests, clearly explain:
- The problem you're solving.
- Why the feature is valuable.
- Any ideas for implementation, and which stage/agent/hook it touches.

---

## Pull Request Guidelines

- Ensure `python3 .claude/scripts/selftest_hooks.py` passes.
- Keep PRs focused and concise. Avoid bundling unrelated changes.
- Update `README.md` and `CLAUDE.md` if your changes affect commands, artifacts, hook coverage, or the agent roster.
- Be responsive to feedback during the review process.

---

## Code Style and Standards

To maintain consistency, follow these standards:
- **Python, standard library only** for everything in `.claude/scripts/` and `.claude/hooks/`. Task evaluators may import task-specific libraries (e.g., `scikit-learn`).
- Respect the **hard rules** in `CLAUDE.md`: scores only from execution, no citation without a `bibliography.jsonl` entry, isolated branches, verification separate from repair.
- Agents and skills are Markdown with YAML frontmatter; keep prompts specific and keep the frontmatter (`skills:`, `hooks:`, `disable-model-invocation`) consistent with the wiring tables in `CLAUDE.md`.
- Add comments to explain non-obvious logic, and use meaningful names.
- Test your changes with the offline smoke test.

---

## Community Support

If you have questions or need help:
- Check the [discussions board](https://github.com/EmmanuelRTM/researcher_team/discussions).
- Reach out by opening a general inquiry issue.

---

Thank you for contributing to **Researcher Team**! Together, we can make this project better for everyone. 💻✨
