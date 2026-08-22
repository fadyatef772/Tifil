#!/usr/bin/env python3
"""Struggle-predictor verification (ML layer).

*** WHAT THIS PROVES — AND WHAT IT DOES NOT ***

This script validates the PIPELINE PLUMBING around the struggle predictor,
NOT its clinical accuracy:

  * the trained artifact (app/ml/artifacts/struggle_predictor.joblib) exists,
    loads, and has the shape the feature extractor produces;
  * app.ml.features.extract_features computes the expected values from small,
    hand-built attempt histories (level filtering, trend sign, windowing);
  * predictions are DIRECTIONALLY sensible on two clear-cut synthetic cases:
    a struggling pattern (low recent accuracy, many taps-to-correct, declining
    trend) scores a higher P(struggling) than a doing-well pattern, and each
    leans the right side of the coin-flip midpoint.

It does NOT prove the model identifies real struggling children. The model is
a proof-of-concept RandomForest trained purely on SIMULATED archetypes
(app/ml/synthetic_data.py — no real child has ever used this app), so these
checks say nothing about clinical validity. See the module docstring of
app/ml/struggle_predictor.py for what would have to change before real use.

Everything here is deterministic: no retraining, no randomness, no database —
the existing artifact is loaded as-is and fed hand-built feature vectors.
Run:  python verify_ml.py
"""

import os

os.environ["TIFL_SECRET_KEY"] = "test-only-dev-secret-not-for-production"

import joblib  # noqa: E402
import numpy as np  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.ml.features import (  # noqa: E402
    FEATURE_NAMES,
    FEATURE_WINDOW,
    AttemptRecord,
    extract_features,
)
from app.ml.struggle_predictor import ARTIFACT_PATH, predict  # noqa: E402

passed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global passed
    if not cond:
        raise AssertionError(f"{name}: FAILED {detail}")
    passed += 1
    print(f"  ok  {name}" + (f"  -- {detail}" if detail else ""))


print("1. Trained artifact loads (no retraining -- loading what ships)")
check("artifact file exists", ARTIFACT_PATH.exists(), str(ARTIFACT_PATH))
model = joblib.load(ARTIFACT_PATH)
check("artifact deserializes to an estimator", hasattr(model, "predict_proba"), f"type={type(model).__name__}")
check(
    "expects one feature per FEATURE_NAMES entry",
    getattr(model, "n_features_in_", None) == len(FEATURE_NAMES),
    f"n_features_in={getattr(model, 'n_features_in_', '?')} vs {len(FEATURE_NAMES)} named features",
)
check(
    "binary classes are {not_struggling=0, struggling=1}",
    list(getattr(model, "classes_", [])) == [0, 1],
    f"classes_={list(getattr(model, 'classes_', []))}",
)

print("2. Feature extraction on hand-built histories")
# --- Neutral prior when there is nothing at the current level yet ---
neutral = extract_features([], current_level=3)
check("empty history -> neutral prior", neutral.shape == (4,) and np.allclose(neutral, [0.5, 1.0, 0.0, 0.0]),
      f"{np.round(neutral, 4).tolist()}")
other_level_only = [
    AttemptRecord(is_correct=True, tries=1, level=1),
    AttemptRecord(is_correct=False, tries=4, level=1),
]
check("attempts only at OTHER levels -> neutral prior",
      np.allclose(extract_features(other_level_only, current_level=9), [0.5, 1.0, 0.0, 0.0]))

# --- Known small case: level filtering + averages ---
hist = [
    AttemptRecord(is_correct=True, tries=1, level=3),  # wrong level -> filtered out
    AttemptRecord(is_correct=True, tries=1, level=2),
    AttemptRecord(is_correct=False, tries=3, level=2),
    AttemptRecord(is_correct=True, tries=1, level=2),
    AttemptRecord(is_correct=False, tries=2, level=2),
]
feat = extract_features(hist, current_level=2)
# accuracy = 2/4 = 0.5 | avg_tries = (1+3+1+2)/4 = 1.75 | newer half 0.5 - older half 0.5 = 0.0 | 4 at-level
check("small mixed history -> exact expected vector", feat.shape == (4,) and np.allclose(feat, [0.5, 1.75, 0.0, 4.0]),
      f"{np.round(feat, 4).tolist()}")

# --- Trend sign ---
declining = [AttemptRecord(True, 1, 2)] * 2 + [AttemptRecord(False, 3, 2)] * 2
improving = declining[::-1]
check("getting worse -> negative trend", extract_features(declining, 2)[2] == -1.0)
check("getting better -> positive trend", extract_features(improving, 2)[2] == 1.0)

# --- Windowing: only the last FEATURE_WINDOW at-level attempts count ---
windowed = [AttemptRecord(False, 5, 2)] * 2 + [AttemptRecord(True, 1, 2)] * 10
feat_w = extract_features(windowed, current_level=2)
check(f"only last {FEATURE_WINDOW} at-level attempts feed the features",
      np.allclose(feat_w, [1.0, 1.0, 0.0, 12.0]),
      f"old bad warm-up ignored: {np.round(feat_w, 4).tolist()}")

print("3. Directional predictions through the serving entry point "
      "(ordering + coin-flip midpoint, NOT exact probabilities)")
STRUGGLING_HISTORY = (
    [AttemptRecord(True, 2, 2)] * 2
    + [AttemptRecord(False, 4, 2), AttemptRecord(False, 3, 2), AttemptRecord(True, 2, 2),
       AttemptRecord(False, 4, 2), AttemptRecord(False, 3, 2)]
    + [AttemptRecord(False, 4, 2)] * 5
)  # recent accuracy 0.1, avg tries 3.6, declining trend, long grind at this level
DOING_WELL_HISTORY = (
    [AttemptRecord(False, 3, 2)]
    + [AttemptRecord(True, 1, 2)] * 9
)  # recent accuracy 0.9, avg tries 1.2, improving trend

struggling_pred = predict(STRUGGLING_HISTORY, current_level=2)
doing_well_pred = predict(DOING_WELL_HISTORY, current_level=2)
check("struggling case predicted (model available)", struggling_pred.available,
      f"P(struggling)={struggling_pred.confidence:.4f}")
check("doing-well case predicted (model available)", doing_well_pred.available,
      f"P(struggling)={doing_well_pred.confidence:.4f}")
check("struggling pattern leans 'struggling' (P > 0.5)",
      struggling_pred.confidence > 0.5, f"P={struggling_pred.confidence:.4f}")
check("doing-well pattern leans 'not struggling' (P < 0.5)",
      doing_well_pred.confidence < 0.5, f"P={doing_well_pred.confidence:.4f}")
check("struggling case scores HIGHER than doing-well case (ordering, not exact numbers)",
      struggling_pred.confidence > doing_well_pred.confidence,
      f"gap={struggling_pred.confidence - doing_well_pred.confidence:.4f}")

# Plumbing consistency: the boolean flag must mirror the configured threshold
THRESHOLD = settings.struggle_confidence_threshold
for label, pred in [("struggling", struggling_pred), ("doing-well", doing_well_pred)]:
    check(f"is_struggling mirrors threshold ({label} case)",
          pred.is_struggling == (pred.confidence >= THRESHOLD),
          f"P={pred.confidence:.4f} vs threshold={THRESHOLD}")

# Serving pipeline agrees with the raw artifact on the same input
raw_proba = float(model.predict_proba(extract_features(STRUGGLING_HISTORY, 2).reshape(1, -1))[0][1])
check("predict() matches raw artifact on extracted features",
      abs(raw_proba - struggling_pred.confidence) < 1e-12,
      f"serving={struggling_pred.confidence:.6f} raw={raw_proba:.6f}")

# No data yet -> prediction still served honestly (no direction asserted: the
# neutral prior sits near the coin flip by design)
cold_start = predict([], current_level=2)
check("empty history still predicts without crashing",
      cold_start.available and 0.0 <= cold_start.confidence <= 1.0,
      f"P={cold_start.confidence:.4f} (neutral-prior input, direction deliberately unchecked)")

print(f"\n{passed} checks passed; confidence threshold = {THRESHOLD}; artifact = {ARTIFACT_PATH.name}")
print("ALL CHECKS PASSED")
