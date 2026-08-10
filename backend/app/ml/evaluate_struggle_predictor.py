"""Evaluate the saved struggle predictor against a FRESH synthetic dataset —
a different random seed from training, so this is data the model has never
seen in any form (not even via the train/test split inside the training
script).

    python -m app.ml.evaluate_struggle_predictor

Still synthetic end to end (see synthetic_data.py's module docstring): this
checks the pipeline generalizes to a new random draw of simulated children,
not that it works on real ones. Precision/recall matter more than accuracy
here because the classes are imbalanced (~1 in 5 "struggling") and a
missed struggle (false negative) costs a child a harder few minutes, while
a false positive just serves an easy warm-up rep — so recall on the
"struggling" class is the number to watch.
"""

from __future__ import annotations

import sys

import joblib
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_score,
    recall_score,
)

from app.ml.struggle_predictor import ARTIFACT_PATH
from app.ml.synthetic_data import generate_dataset


def main() -> None:
    if not ARTIFACT_PATH.exists():
        print(f"No model at {ARTIFACT_PATH}. Run `python -m app.ml.train_struggle_predictor` first.")
        sys.exit(1)

    model = joblib.load(ARTIFACT_PATH)
    print("Generating a FRESH synthetic evaluation set (seed=999, unseen by training)...")
    X, y = generate_dataset(n_trajectories=200, seed=999)
    print(f"{len(y)} samples | struggling={y.mean():.1%} of samples\n")

    y_pred = model.predict(X)
    print(f"Accuracy:  {accuracy_score(y, y_pred):.3f}")
    print(f"Precision: {precision_score(y, y_pred):.3f}  (of predicted-struggling, how many really were)")
    print(f"Recall:    {recall_score(y, y_pred):.3f}  (of actually-struggling, how many were caught)")
    print()
    print(classification_report(y, y_pred, target_names=["not_struggling", "struggling"], digits=3))
    print("Confusion matrix [rows=true, cols=pred]:")
    print(confusion_matrix(y, y_pred))


if __name__ == "__main__":
    main()
