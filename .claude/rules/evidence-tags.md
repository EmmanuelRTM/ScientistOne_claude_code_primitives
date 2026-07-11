---
paths:
  - "workspace/runs/**/paper/**"
  - "workspace/runs/**/final/**"
---

# Evidence-tag rules (paper artifacts)

Grammar (validated by `.claude/scripts/ground_check.py`):

```
[EV:score:<path.json>#<dotted.key>]   e.g. [EV:score:best/eval.json#score]
[EV:log:<path>:L<n>[-L<m>]]           e.g. [EV:log:best/solve.log:L12]
[EV:cite:<bibkey>]                    key must exist in bibliography.jsonl
[EV:artifact:<path>]                  artifact existence
[EV:config:<path.json>#<dotted.key>]  e.g. [EV:config:run-config.json#branches]
```

- Every sentence stating a number, comparison, method property, or prior work
  MUST carry at least one tag. Place the tag at the end of the sentence,
  before the period is acceptable.
- Numbers must restate the artifact value exactly (or an explicitly rounded
  form within 0.5%). Percent and fraction forms are both accepted
  (96.7% ≙ 0.967).
- Statements that cannot be tied to an artifact go under a `## Assumptions`
  header — they are exempt from tagging but must be honest assumptions, not
  smuggled results.
- Baselines: label each as **VERIFIED** (traceable to a `[EV:cite:]` source or
  an executed artifact) or **ESTIMATED** (anything else). Never present an
  ESTIMATED number as a measured result.
- The Bibliography section is rendered ONLY from `bibliography.jsonl` entries.
