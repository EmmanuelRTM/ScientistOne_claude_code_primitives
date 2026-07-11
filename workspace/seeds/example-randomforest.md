# Seed note: Random Forests

- **Title**: Random Forests
- **Authors**: L. Breiman
- **Year**: 2001
- **Venue**: Machine Learning (journal)

## Summary
Introduces random forests: ensembles of decision trees where each tree is
grown on a bootstrap sample and each split considers a random subset of
features. Shows that forest generalization error converges as trees are
added (no overfitting from more trees) and depends on individual tree
strength and inter-tree correlation. Reports strong, robust accuracy across
tabular benchmarks with little tuning.

## Relevance notes
For 64-feature digit bitmaps, random forests are a fast, nearly
tuning-free baseline that trains in seconds at a few hundred trees. Key
knobs: n_estimators (accuracy saturates), max_features (decorrelation).
Also useful as a feature-importance probe and as a diverse member of a
voting/stacking ensemble alongside kNN and SVM.
