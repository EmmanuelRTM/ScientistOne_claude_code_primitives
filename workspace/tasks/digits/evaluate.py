#!/usr/bin/env python3
"""Official evaluator for the `digits` task.

Usage: python3 evaluate.py path/to/solution.py

Prints a single JSON object to stdout:
  {"task": "digits", "metric": "accuracy", "score": 0.9673,
   "all_metrics": {...}, "constraint_ok": true, "violations": [...],
   "runtime_sec": 3.21, "exit_code": 0}

Exit code 0 even for scoring failures (score=null + error) so the evaluator
agent can transcribe the result; non-JSON output means the evaluator crashed.
"""
import ast
import importlib.util
import json
import signal
import sys
import time
from pathlib import Path

ALLOWED_IMPORTS = {
    "numpy", "sklearn", "math", "random", "statistics", "collections",
    "itertools", "functools", "json", "time", "sys",
}
TIME_LIMIT_SEC = 60


def check_imports(path: Path):
    violations = []
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            root = name.split(".")[0]
            if root not in ALLOWED_IMPORTS:
                violations.append(f"disallowed import: {name}")
    return violations


class Timeout(Exception):
    pass


def _alarm(signum, frame):
    raise Timeout()


def main() -> int:
    result = {"task": "digits", "metric": "accuracy", "score": None,
              "all_metrics": {}, "constraint_ok": False, "violations": [],
              "runtime_sec": None, "exit_code": 0}
    if len(sys.argv) != 2:
        result["error"] = "usage: evaluate.py path/to/solution.py"
        print(json.dumps(result))
        return 0
    sol_path = Path(sys.argv[1])
    if not sol_path.is_file():
        result["error"] = f"solution not found: {sol_path}"
        print(json.dumps(result))
        return 0

    try:
        result["violations"] = check_imports(sol_path)
    except SyntaxError as exc:
        result["error"] = f"syntax error in solution: {exc}"
        print(json.dumps(result))
        return 0

    from sklearn.datasets import load_digits
    from sklearn.metrics import accuracy_score, f1_score
    from sklearn.model_selection import train_test_split

    X, y = load_digits(return_X_y=True)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=0, stratify=y)

    spec = importlib.util.spec_from_file_location("solution", sol_path)
    module = importlib.util.module_from_spec(spec)
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(TIME_LIMIT_SEC + 30)  # module import + call, generous outer cap
    start = time.time()
    try:
        spec.loader.exec_module(module)
        if not hasattr(module, "train_and_predict"):
            raise AttributeError("solution.py does not define train_and_predict()")
        preds = module.train_and_predict(X_train, y_train, X_test)
        runtime = time.time() - start
        result["runtime_sec"] = round(runtime, 2)
        if runtime > TIME_LIMIT_SEC:
            result["violations"].append(
                f"time limit exceeded: {runtime:.1f}s > {TIME_LIMIT_SEC}s")
        acc = float(accuracy_score(y_test, list(preds)))
        result["score"] = round(acc, 4)
        result["all_metrics"] = {
            "accuracy": round(acc, 4),
            "macro_f1": round(float(f1_score(y_test, list(preds), average="macro")), 4),
            "n_test": int(len(y_test)),
        }
    except Timeout:
        result["error"] = f"hard timeout after {TIME_LIMIT_SEC + 30}s"
        result["violations"].append("hard timeout")
    except Exception as exc:  # scoring must never crash the pipeline
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        signal.alarm(0)

    result["constraint_ok"] = not result["violations"]
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    main()
