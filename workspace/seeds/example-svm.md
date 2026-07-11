# Seed note: Support-Vector Networks

- **Title**: Support-Vector Networks
- **Authors**: C. Cortes, V. Vapnik
- **Year**: 1995
- **Venue**: Machine Learning (journal)

## Summary
Introduces the soft-margin support vector machine: maps inputs into a
high-dimensional feature space (via kernels) and finds the maximum-margin
separating hyperplane with slack variables for non-separable data. Reports
strong results on handwritten digit recognition benchmarks of the era.

## Relevance notes
RBF-kernel SVMs are historically among the best classical models for digit
recognition. Two hyperparameters dominate: C (margin softness) and gamma
(kernel width). Benefits from feature scaling to a common range. Training on
~1,300 samples of 64 features is well within a seconds-scale budget.
