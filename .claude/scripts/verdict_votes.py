#!/usr/bin/env python3
"""Best-of-N verification votes: self-consistency for the LLM-only verdicts.

Deterministic checks (numbers, files, line ranges) are already exact and are
never voted on. The two judgment calls — citation entailment and method-code
alignment — can vary between samples, so when run-config.json sets
"verifier_votes": N >= 2, the claim-verifier is launched N times in fresh
contexts and the disagreements are reconciled conservatively: the WEAKEST
verdict wins (FAIL < PARTIAL < PASS). Inconsistency across samples is treated
as evidence of an unreliable judgment, per the best-of-N verification
technique.

Votes are sequential by design: each verifier reuses paper/claims.jsonl and
paper/verification-report.md, and `snapshot` archives one vote and resets the
LLM-judged claims to PENDING_LLM so the next verifier judges blind.

Subcommands:
  snapshot <run> <k>   archive vote k: claims.jsonl -> paper/votes/claims.v<k>.jsonl,
                       move verification-report.md -> paper/votes/verification-report.v<k>.md,
                       then reset every LLM-judged claim in claims.jsonl to
                       PENDING_LLM (quote and detail cleared).
  merge <run>          reconcile claims.jsonl (the final vote) with every
                       archived vote. Agreement -> unchanged; disagreement ->
                       weakest verdict wins, detail records the split, and the
                       quote comes from the vote that carried the winning
                       verdict. Prints a summary to append to the report.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evtags import VERDICT_RANK

ROOT = Path(__file__).resolve().parents[2]


def resolve_run_dir(arg: str) -> Path:
    p = Path(arg)
    return p.resolve() if p.is_dir() else (ROOT / "workspace" / "runs" / arg).resolve()


def load_claims(fp: Path):
    return [json.loads(l) for l in fp.read_text().splitlines() if l.strip()]


def save_claims(fp: Path, claims):
    fp.write_text("".join(json.dumps(c) + "\n" for c in claims))


def is_llm_judged(claim: dict) -> bool:
    detail = str(claim.get("detail", ""))
    return detail.startswith("LLM:") or detail.startswith("QUOTE-CHECK:")


def snapshot(run_dir: Path, k: int) -> int:
    claims_file = run_dir / "paper" / "claims.jsonl"
    if not claims_file.is_file():
        print(f"ERROR: {claims_file} not found", file=sys.stderr)
        return 1
    votes_dir = run_dir / "paper" / "votes"
    votes_dir.mkdir(exist_ok=True)

    claims = load_claims(claims_file)
    judged = [c for c in claims if is_llm_judged(c)]
    save_claims(votes_dir / f"claims.v{k}.jsonl", claims)

    report = run_dir / "paper" / "verification-report.md"
    if report.is_file():
        report.rename(votes_dir / f"verification-report.v{k}.md")

    for c in claims:
        if is_llm_judged(c):
            c["status"], c["detail"] = "PENDING_LLM", ""
            c.pop("quote", None)
    save_claims(claims_file, claims)
    print(f"Vote {k} archived ({len(judged)} LLM-judged claims reset to "
          f"PENDING_LLM) -> {votes_dir / f'claims.v{k}.jsonl'}")
    return 0


def merge(run_dir: Path) -> int:
    claims_file = run_dir / "paper" / "claims.jsonl"
    votes_dir = run_dir / "paper" / "votes"
    vote_files = sorted(votes_dir.glob("claims.v*.jsonl")) if votes_dir.is_dir() else []
    if not claims_file.is_file() or not vote_files:
        print("ERROR: need paper/claims.jsonl plus >=1 archived vote in "
              "paper/votes/ (run snapshot between verifier launches)",
              file=sys.stderr)
        return 1

    final = load_claims(claims_file)
    votes = [{c["id"]: c for c in load_claims(fp)} for fp in vote_files]
    n_voted = n_split = 0
    split_lines = []
    for claim in final:
        samples = [v[claim["id"]] for v in votes
                   if claim["id"] in v and is_llm_judged(v[claim["id"]])]
        if is_llm_judged(claim):
            samples.append(claim)
        if len(samples) < 2:
            continue  # deterministic verdict, or judged in only one vote
        n_voted += 1
        # QUOTE-CHECK downgrades are FAILs already; rank by recorded status
        verdicts = [s["status"] for s in samples]
        weakest = min(verdicts, key=lambda v: VERDICT_RANK.get(v, 0))
        if len(set(verdicts)) > 1:
            n_split += 1
            carrier = next(s for s in samples if s["status"] == weakest)
            split = "/".join(verdicts)
            claim["status"] = weakest
            claim["detail"] = (f"LLM-VOTE {split} -> {weakest}; "
                               + str(carrier.get("detail", "")))
            if carrier.get("quote"):
                claim["quote"] = carrier["quote"]
            else:
                claim.pop("quote", None)
            split_lines.append(f"  {claim['id']}: {split} -> {weakest}")
    save_claims(claims_file, final)

    print(f"Reconciled {len(vote_files) + 1} votes over {n_voted} LLM-judged "
          f"claims: {n_voted - n_split} unanimous, {n_split} disagreement(s) "
          f"resolved to the weakest verdict.")
    for line in split_lines:
        print(line)
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot")
    s.add_argument("run")
    s.add_argument("k", type=int)
    m = sub.add_parser("merge")
    m.add_argument("run")
    args = p.parse_args()

    run_dir = resolve_run_dir(args.run)
    if not run_dir.is_dir():
        print(f"ERROR: run dir {run_dir} not found", file=sys.stderr)
        return 1
    return snapshot(run_dir, args.k) if args.cmd == "snapshot" else merge(run_dir)


if __name__ == "__main__":
    sys.exit(main())
