---
paths:
  - "workspace/runs/**/literature/**"
  - "workspace/runs/**/bibliography.jsonl"
---

# Bibliography rules

One JSON object per line in `bibliography.jsonl`
(validated by `.claude/scripts/bib_validate.py`):

```json
{"key": "lecun1998gradient", "title": "...", "authors": ["Y. LeCun"],
 "year": 1998, "venue": "...", "source_url": "https://...",
 "retrieved_at": "2026-07-11T18:00:00Z",
 "provenance": "websearch|webfetch|seed|user-provided",
 "read_status": "full|abstract-only", "abstract": "...",
 "local_note": "literature/lecun1998gradient.md"}
```

- Key format: `<firstauthor><year><firstword>` lowercase.
- Every entry MUST have a matching note file `literature/<key>.md` containing:
  provenance frontmatter (source, retrieval date, how it was found), a factual
  summary of what the paper actually says, and the specific findings relevant
  to this run's topic. The note is what entailment checks run against.
- `read_status: abstract-only` entries may support Related Work context but
  never a load-bearing technical claim (they ground only PARTIAL).
- Never add an entry for a paper you could not retrieve. If a known-important
  paper is unreachable, record it in `investigation/` notes as unretrieved —
  it gets no key and no citations.
