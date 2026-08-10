"""Struggle Predictor — Machine Learning layer (scikit-learn).

*** TRAINED ON SYNTHETIC DATA — PROOF OF CONCEPT, NOT CLINICALLY VALIDATED ***

No real child has used this app yet, so there is no real attempt history to
learn from. `app/ml/synthetic_data.py` simulates plausible archetypes
(fast learner / average / struggler / inconsistent) and
`train_struggle_predictor.py` fits a RandomForestClassifier on that
simulated data alone. Every prediction here demonstrates that the pipeline
(features -> model -> serving decision) works end to end — it is NOT
evidence that the model generalizes to real children. Retraining on real,
consented attempt logs is a prerequisite before this should be allowed to
influence a real child's session.

The rule-based adaptive engine (app/services/adaptive_engine.py) is
untouched by this module and remains the sole authority on mastery and
level progression:

* If no trained model artifact exists, or it fails to load, or feature
  extraction/inference raises for any reason, `predict()` /
  `predict_for_child_skill()` report `available=False` and the caller is
  expected to do nothing differently — the rule-based engine's own choice
  of exercise is always the safe fallback.
* Even when a struggle is predicted, this module never edits a Mastery row.
  It can only suggest an easier *rep* for a single turn
  (see app/ml/intervention.py) — level progression is decided exclusively
  by adaptive_engine.record_answer, exactly as before this layer existed.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import NamedTuple

import joblib
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.models import Attempt
from app.ml.features import AttemptRecord, extract_features

logger = logging.getLogger(__name__)

ARTIFACT_PATH = Path(__file__).parent / "artifacts" / "struggle_predictor.joblib"

# Per (child, skill), plenty for a FEATURE_WINDOW=10 feature and a sane cap
# on "attempts at current level" — bounded so a long-lived child never makes
# this query scan an unbounded table.
HISTORY_QUERY_LIMIT = 200


class StrugglePrediction(NamedTuple):
    is_struggling: bool
    confidence: float  # P(struggling), 0..1 — 0.0 when unavailable
    available: bool


_model = None
_load_failed = False


def _load_model():
    global _model, _load_failed
    if _model is not None or _load_failed:
        return _model
    if not ARTIFACT_PATH.exists():
        logger.warning(
            "No struggle-predictor artifact at %s -- run "
            "`python -m app.ml.train_struggle_predictor` to create one. "
            "Serving falls back to rule-based-only until then.",
            ARTIFACT_PATH,
        )
        _load_failed = True
        return None
    try:
        _model = joblib.load(ARTIFACT_PATH)
    except Exception:
        logger.exception(
            "Failed to load struggle-predictor artifact at %s; "
            "falling back to rule-based-only serving.",
            ARTIFACT_PATH,
        )
        _load_failed = True
        _model = None
    return _model


def predict(
    history: list[AttemptRecord],
    current_level: int,
    confidence_threshold: float | None = None,
) -> StrugglePrediction:
    model = _load_model()
    if model is None:
        return StrugglePrediction(is_struggling=False, confidence=0.0, available=False)

    threshold = (
        confidence_threshold
        if confidence_threshold is not None
        else settings.struggle_confidence_threshold
    )
    features = extract_features(history, current_level).reshape(1, -1)
    proba = float(model.predict_proba(features)[0][1])
    return StrugglePrediction(
        is_struggling=proba >= threshold, confidence=proba, available=True
    )


def predict_for_child_skill(
    db: Session, child_id: int, skill_id: int, current_level: int
) -> StrugglePrediction:
    """Fetch recent attempt history and predict. Never raises: any DB or
    model error is treated the same as "no model available" so a caller can
    always safely ignore this and fall back to the rule-based engine."""
    try:
        rows = db.execute(
            select(Attempt.is_correct, Attempt.tries, Attempt.level)
            .where(Attempt.child_id == child_id, Attempt.skill_id == skill_id)
            .order_by(Attempt.created_at.desc())
            .limit(HISTORY_QUERY_LIMIT)
        ).all()
        history = [
            AttemptRecord(is_correct=r[0], tries=r[1], level=r[2])
            for r in reversed(rows)
        ]
        return predict(history, current_level)
    except Exception:
        logger.exception("Struggle prediction failed; treating as unavailable.")
        return StrugglePrediction(is_struggling=False, confidence=0.0, available=False)
