# Ideator memory — idea archetype outcomes

Purpose: track which idea archetypes won or lost branches across runs, so
future iterations exploit winners and avoid losers. Updated each iteration
after reading distilled feedback.

## Archetype ledger

### Run 20260711-1951-digits-eval (digits, 60 s budget, B=5)

**i1 — proposed (outcomes pending; check i1 distilled-feedback in i2):**
- p1 `tuned-single-kernel` (RBF-SVM dense CV grid + optional PCA arm) — Conservative
- p2 `stacking-heterogeneous` (SVM+kNN+RF, logistic meta, OOF probs) — Conservative
- p3 `invariance-augmentation-tta` (pixel-shift augment + TTA score averaging) — Unconventional
- p4 `transductive-pseudolabel` (one-round confidence-gated self-training on X_test) — Unconventional
- p5 `soft-voting-weighted` (CV-weighted probability averaging of 3 families) — Conservative

Held in reserve for i2 (not yet raced): `deskew+mini-HOG feature engineering`
(U2), `NCA metric learning + kNN` (U4), `confidence-gated cascade with
pairwise experts` (U5), `random-features linear committee` (U6).

## Cross-run lessons (accumulating)
- None yet — first tracked iteration. Next update: mark each i1 archetype
  WON / COMPETITIVE / LOST / DISQUALIFIED from distilled feedback, and note
  whether the unconventional branches (p3, p4) justified their slots.
