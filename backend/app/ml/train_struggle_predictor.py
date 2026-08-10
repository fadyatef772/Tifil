"""Train the struggle predictor on SYNTHETIC data and save it.

    python -m app.ml.train_struggle_predictor

This is a proof-of-concept training run: there is no real attempt history
yet (see synthetic_data.py's module docstring), so this fits a
RandomForestClassifier purely on simulated child archetypes. The printed
metrics show the pipeline (features -> model -> artifact) works — they are
NOT evidence of clinical validity. `evaluate_struggle_predictor.py` re-checks
the saved artifact against a second, differently-seeded synthetic dataset
for a more honest held-out number.
"""

from __future__ import annotations

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split

from app.ml.features import FEATURE_NAMES
from app.ml.struggle_predictor import ARTIFACT_PATH
from app.ml.synthetic_data import generate_dataset


def main() -> None:
    print("Generating synthetic training data (simulated archetypes, NOT real children)...")
    X, y = generate_dataset(n_trajectories=500, seed=42)
    print(f"{len(y)} samples | struggling={y.mean():.1%} of samples | features={FEATURE_NAMES}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=6,
        min_samples_leaf=5,
        class_weight="balanced",
        random_state=42,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    print("\n--- Held-out test split (25% of the same synthetic run) ---")
    print(
        classification_report(
            y_test, y_pred, target_names=["not_struggling", "struggling"], digits=3
        )
    )
    print("Confusion matrix [rows=true, cols=pred]:")
    print(confusion_matrix(y_test, y_pred))

    print("\nFeature importances:")
    for name, imp in sorted(
        zip(FEATURE_NAMES, model.feature_importances_), key=lambda x: -x[1]
    ):
        print(f"  {name:28} {imp:.3f}")

    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, ARTIFACT_PATH)
    print(f"\nSaved model to {ARTIFACT_PATH}")


if __name__ == "__main__":
    main()
