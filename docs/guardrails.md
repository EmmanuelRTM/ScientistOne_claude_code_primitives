# Guardrails — how this pipeline implements Anthropic's anti-hallucination and consistency guidance

This project's integrity mechanisms map directly onto Anthropic's published
guardrail guidance:

- [Reduce hallucinations](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations)
- [Increase output consistency](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/increase-consistency)

The design principle throughout: **escalate prompt-level techniques into
mechanical enforcement wherever possible**. Instructions ask the model to be
honest; hooks and deterministic scripts make the dishonest path fail. LLM
judgment is reserved for the checks that genuinely need it (citation
entailment, method-code alignment), and even those judgments must leave a
machine-checkable trace.

## Reduce hallucinations

| Docs technique | Implementation | Enforcement point |
|---|---|---|
| Verify with citations; retract claims without support | Chain-of-Evidence: every factual sentence carries an `[EV:...]` tag resolving to a real artifact | `ground_check.py` (exit 1 below 0.85 grounding), `chain_of_evidence.py` final audit |
| Use direct quotes for factual grounding | Every LLM PASS/PARTIAL verdict must carry a `quote` field that is a verbatim excerpt of the evidence source; fabricated or missing quotes discard the verdict | `verify_claims.py` QUOTE-CHECK, `verifier_stop_gate.py` |
| Allow "I don't know" | Untaggable statements go under `## Assumptions` or get cut; agents report `ok: false` on missing inputs instead of fabricating stand-ins | `evidence-tagging` skill, `workspace-protocol` rule, GROUND flags untagged body sentences |
| External knowledge restriction | "A paper you did not retrieve and read does not exist"; unknown citation keys are blocked at write time; offline mode restricts sources to `workspace/seeds/` | `citation_guard.py` PreToolUse hook (blocks the Write/Edit call) |
| Best-of-N verification | `verifier_votes: N` in `run-config.json` samples each LLM-only verdict N times in fresh contexts; disagreement resolves to the weakest verdict (FAIL < PARTIAL < PASS) | `verdict_votes.py` snapshot/merge, `verify-claims` skill protocol |
| Chain-of-thought verification | Fresh-context `paper-critic` audits the paper's reasoning (gap-approach alignment, contradictions, overclaims) with no shared context with the writer | `paper-critic` agent, `/write-paper` CRITIC stage |
| Iterative refinement | GROUND → CRITIC → RESOLVE loop for the draft; verify → refine → re-verify loop (max 2 rounds, residual failures reported honestly, never hidden) | `/write-paper`, `/verify-claims` stage protocols |

Beyond the docs, two failure modes get fully non-LLM defenses:

- **Scores**: the only legitimate score is `eval.json` produced by executing
  `task/evaluate.py`; the evaluator agent transcribes verbatim and cannot
  edit solutions (Edit disabled).
- **Citations**: a hallucinated reference is mechanically impossible — the
  citation guard rejects the write before it reaches disk.

## Increase output consistency

| Docs technique | Implementation |
|---|---|
| Specify the desired output format | Fixed schemas for `eval.json`, `claims.jsonl`, `ground-report.json`; every agent ends with one line of JSON `{"ok", "outputs", "notes"}`; exact required report lines (`Method-Code Alignment: PASS|FAIL`) |
| Constrain with examples | Evidence-tag grammar table with a worked example per tag type; worked `claims.jsonl` verdict example (with quote) in the claim-verifier prompt; `distill-feedback` template |
| Use retrieval for contextual consistency | All judgments are made against retrieved, on-disk sources: `literature/<key>.md` notes, `best/solution.py`, `best/solve.log` — never from model memory |
| Chain prompts for complex tasks | The pipeline itself: each stage is a separate subagent with a narrow role and fresh context; the filesystem is the only channel between them |
| Keep Claude in character | Role prompts backed by tool restrictions: the evaluator and claim-verifier cannot Edit (scorekeeper/judge, not coach/repairer); the auditor cannot fix what it audits |
| Prefill the response | Not used — unsupported on current models; per the docs, schema-per-artifact plus deterministic validation is the replacement |

## Verdict lifecycle (Stage 4)

```
extract_claims.py            every tagged/numeric sentence → claims.jsonl (PENDING)
verify_claims.py             deterministic: numbers ±5%, files, line ranges,
                             bib keys → PASS/FAIL, judgment calls → PENDING_LLM
claim-verifier (× N votes)   judges PENDING_LLM with verbatim quote per verdict;
                             stop gate blocks finishing ungrounded or unresolved
verify_claims.py (re-run)    QUOTE-CHECK: quote must appear verbatim in the
                             evidence source, else verdict discarded → FAIL
verdict_votes.py merge       (N ≥ 2) disagreements → weakest verdict wins
refiner                      repairs FAILs in the draft (verifier never edits;
                             refiner never issues verdicts)
chain_of_evidence.py         final four-check audit appended to the report
```
