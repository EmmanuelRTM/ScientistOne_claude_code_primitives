# Seed note: Gradient-Based Learning Applied to Document Recognition

- **Title**: Gradient-Based Learning Applied to Document Recognition
- **Authors**: Y. LeCun, L. Bottou, Y. Bengio, P. Haffner
- **Year**: 1998
- **Venue**: Proceedings of the IEEE

## Summary
The classic study of gradient-based learning for handwritten character
recognition (introduces LeNet-5 on MNIST). Systematically compares
convolutional networks against classical methods — kNN, PCA+quadratic
classifiers, RBF networks, SVMs — showing learned feature hierarchies beat
hand-crafted pipelines at scale, while classical methods remain competitive
on small datasets.

## Relevance notes
Two transferable lessons for tiny-image classification: (1) input
normalization matters for every model family; (2) on small datasets the gap
between well-tuned classical models and neural approaches narrows sharply —
ensembling and dimensionality reduction (PCA) are cheap accuracy levers.
