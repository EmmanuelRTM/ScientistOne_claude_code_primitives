# Task: Handwritten Digit Classification (sklearn digits)

## Objective
Maximize test-set **accuracy** on the sklearn `load_digits` dataset
(1,797 samples of 8x8 grayscale digit images, 10 classes).

## Data protocol (enforced by the evaluator)
- Fixed split: `train_test_split(X, y, test_size=0.3, random_state=0, stratify=y)`.
- Your solution receives **only** `X_train, y_train, X_test`. Test labels are
  never exposed to the solution. Any attempt to reconstruct or access them is
  a specification violation.

## Solution contract
`solution.py` must define:

```python
def train_and_predict(X_train, y_train, X_test):
    """Return a 1-D array-like of predicted labels for X_test."""
```

## Constraints (violations disqualify the branch)
1. Allowed imports: `numpy`, `sklearn`, and the Python standard library
   modules `math`, `random`, `statistics`, `collections`, `itertools`,
   `functools`, `json`, `time`, `sys`. Nothing else (no network, no file I/O
   outside your branch directory).
2. End-to-end budget: `train_and_predict` must finish within **60 seconds**.
3. Determinism: fix all random seeds (`random_state=0` or equivalent) so the
   evaluator's score is reproducible.

## Metric
- Primary: `accuracy` (fraction of correct predictions on the fixed test set).
- Reported by the evaluator only; solutions must never print a self-assessed
  score as if it were official.
