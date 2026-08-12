# Seed note: Stacked Generalization

- **Title**: Stacked Generalization
- **Authors**: D. H. Wolpert
- **Year**: 1992
- **Venue**: Neural Networks (journal)

## Summary
Introduces stacked generalization (stacking): combine multiple base
learners by training a meta-learner on their out-of-fold predictions,
rather than picking a single winner or averaging naively. Frames stacking
as a principled way to estimate and correct the biases of individual
generalizers, subsuming model selection (winner-take-all) as a special
case.

## Relevance notes
Digit classifiers with different inductive biases (distance-based kNN,
margin-based SVM, tree-ensemble forests) make partially uncorrelated
errors — exactly the regime where stacking or soft-voting beats each
member. Cross-validated stacking on ~1,300 training samples costs only a
few multiples of base training time, comfortably inside a 60-second
budget. Simpler fallback with most of the benefit: probability-averaged
soft voting.
