# Seed note: Nearest Neighbor Pattern Classification

- **Title**: Nearest Neighbor Pattern Classification
- **Authors**: T. M. Cover, P. E. Hart
- **Year**: 1967
- **Venue**: IEEE Transactions on Information Theory

## Summary
Establishes the theoretical foundation of the k-nearest-neighbor (kNN)
decision rule. Key result: as the number of samples grows, the error rate of
the 1-NN rule is bounded above by twice the Bayes (optimal) error rate. kNN
requires no training phase; classification cost grows with the dataset size.

## Relevance notes
For small, low-dimensional image datasets like 8x8 digit bitmaps, kNN with a
suitable distance metric is a strong classical baseline. Sensitive to feature
scaling; k is typically chosen odd and small (3–7). Distance weighting can
improve accuracy at negligible cost.
