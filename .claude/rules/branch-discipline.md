---
paths:
  - "workspace/runs/**/branches/**"
---

# Branch discipline (PEE execution)

- You own exactly ONE branch directory `iterations/iN/branches/bK/`. Never
  read or write sibling branches — branch independence is what makes the
  explore-exploit comparison valid.
- Allowed dependencies in `solution.py`: `numpy`, `sklearn`, and stdlib
  (`math`, `random`, `statistics`, `collections`, `itertools`, `functools`,
  `json`, `time`, `sys`). No network. No file I/O outside your branch dir.
- Determinism: fix every random seed (`random_state=0` or equivalent).
- Capture your runs: append command output to `solve.log` (e.g.
  `python3 solution.py >> solve.log 2>&1`). An undocumented experiment
  never happened.
- The ONLY official score is `eval.json` written by the evaluator from
  `task/evaluate.py` output. Your own sanity-check numbers are provisional
  and must be marked as such in `plan.md`.
- Never touch `paper/`, `final/`, `brief.md`, `bibliography.jsonl`,
  `investigation/` (a hook blocks this).
