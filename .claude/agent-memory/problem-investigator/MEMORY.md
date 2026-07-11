# problem-investigator memory

## Durable lessons
- Offline runs: count seed files FIRST. The relevance gate needs >=5
  core+adjacent sources; the repo's three bundled `example-*.md` seeds alone
  can never pass it, so an offline run with only the demo seeds is a
  guaranteed abort — check before doing any other work.
- Seed notes often mention adjacent papers (e.g., LeNet/MNIST details, PCA,
  RBF networks) but offline mode gives no way to retrieve them; do not add
  such mentions as graph nodes or pool entries.
- For the sklearn-digits / small-image-classification domain, the seed gaps
  worth asking the operator to fill: tree ensembles (random forest / gradient
  boosting), stacking/ensembling, budgeted hyperparameter search, PCA-style
  dimensionality reduction, small-image augmentation.
- Gate-abort remediation works: after an abort, listing concrete seed gaps in
  round2.md got the operator to add exactly those notes (random forests,
  stacking), and the re-run passed 5/5. On re-runs, supersede — don't append
  to — the old round1/round2 artifacts, and note the abort ledger timestamp.
- Canonical 5-source offline set for digits-under-budget topics:
  cover1967nearest, cortes1995support, lecun1998gradient, breiman2001random,
  wolpert1992stacked. Together they ground three diverse model families plus
  scaling/PCA and voting/stacking — enough for a concrete brief.
- `bib_validate.py` requires local_note paths to exist and provenance in
  {websearch,webfetch,seed,user-provided}; run it from the PROJECT ROOT (it
  resolves `.claude/scripts` relative to itself, but a bare relative
  invocation from the run dir fails).
