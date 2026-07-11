# Ideator memory — idea archetype outcomes

Purpose: track which idea archetypes won or lost branches across runs, so
future iterations exploit winners and avoid losers. Updated each iteration
after reading distilled feedback.

## Archetype ledger

### Run 20260711-1951-digits-eval (digits, 60 s budget, B=5)

**i1 — outcomes (from i1 distilled-feedback + ranking):**
- p3/b3 `invariance-augmentation-tta` — **WON** (0.9963). But split verdict
  inside the archetype: train-side pixel-shift augmentation was the entire
  gain (+0.0056); TTA half collapsed in CV (~0.83 at 8x8) and was rightly
  gated off. Lesson: augmentation = winner archetype; classifier-level TTA
  at tiny resolution = loser archetype.
- p4/b4 `transductive-pseudolabel` — **LOST-as-mechanism** (0.9944, rank 2,
  but the transductive gate changed 0/540 predictions; score was the bare
  tuned SVM's). Deceptive-headline hazard: rank ≠ mechanism validation.
  Side-discovery: the tuned backbone (C=5, gamma='scale', X/16) runs in
  1.89s — cheapest strong recipe.
- p5/b5 `soft-voting-weighted` — **LOST** (0.9926 < best single). Cause:
  SVM-dominated members, correlated errors.
- p1/b1 `tuned-single-kernel` — **COMPETITIVE floor** (0.9907); PCA arm won
  its internal CV, worth keeping as a free ablation arm.
- p2/b2 `stacking-heterogeneous` — **LOST, last place** (0.9889). Meta-learner
  cannot fix member redundancy.

**i2 — proposed (outcomes pending; final iteration of this run):**
- p1 `augmentation-extended` (full-8 shifts + grid retuned on augmented dist) — Conservative
- p2 `ensemble-of-augmentation-views` (diversify inputs not model families) — Conservative
- p3 `confusion-pair-experts-cascade` (triage low-margin → binary duel) — Unconventional (was reserve U5 in i1)
- p4 `subpixel-interpolation-augmentation` (bilinear ±0.5px shifts) — Unconventional
- p5 `invariant-metric-arbitration` (shift-min distance kNN on triaged points) — Unconventional
Still unraced reserves: deskew/mini-HOG features, NCA metric learning,
random-features linear committee, center-of-mass canonicalization (scored
worst risk at 8x8).

## Cross-run lessons (accumulating)
- **Train-side invariance augmentation beats architecture cleverness** on
  small image data; test-time augmentation of the classifier is toxic at
  very low resolution (8x8).
- **Ensembles need genuinely decorrelated members**; mixing model families
  around one dominant family (SVM+kNN+RF) produced correlated errors and
  lost to the best single model — twice (voting and stacking). Untested fix:
  vary the DATA/view per member, not the family.
- **Always gate risky add-ons by OOF net-delta with fallback to the strong
  backbone** — b3's gate saved it from TTA; b4's gate degraded gracefully to
  a no-op. Gated proposals never ranked below their backbone.
- **Verify the mechanism moved predictions** (b4 changed 0/540): require
  solvers to log flip counts, or a "winning" archetype teaches nothing.
- **Per-fold leakage-free CV selection was perfectly predictive** in i1
  (official scores matched smoke tests on all 5 branches) — trust internal
  CV for arm selection.
- At near-ceiling accuracy (residual = 2/540), average-accuracy levers
  saturate; propose residual-targeted mechanisms (triage/cascade/invariant
  metric). i2 tests this hypothesis — check outcome next update.
