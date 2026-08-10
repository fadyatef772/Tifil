"""Synthetic training-data generator for the struggle predictor.

*** THIS GENERATES FAKE, SIMULATED DATA — NOT REAL CHILDREN. ***

The app has no deployed users yet, so there is no real attempt history to
learn a struggle predictor from. This module hand-authors four plausible
archetypes of how a child's per-level accuracy might evolve over a session
(fast learner, average, struggler, inconsistent) and simulates attempt-by-
attempt sequences from them. `train_struggle_predictor.py` fits a classifier
on this simulated data as a proof-of-concept of the pipeline
(features -> model -> serving decision) — NOT as a clinically validated
model. See app/ml/struggle_predictor.py's module docstring for how this
should be treated once real, consented attempt logs exist.

Label definition: for a snapshot after attempt i at a level, look ahead at
the next `settings.struggle_window` attempts at that same level. If at most
`settings.struggle_correct` of them are correct, label it "struggling" (1).
This deliberately mirrors the rule-based engine's own demotion rule
(adaptive_engine.record_answer) — the ML model's job is to raise the same
flag *earlier*, before the rule engine's window has even filled, not to
invent a different definition of struggle.
"""

import random

import numpy as np

from app.core.config import settings
from app.ml.features import AttemptRecord, extract_features

ARCHETYPES = ("fast_learner", "average", "struggler", "inconsistent")

# Tuned by hand to produce plausible, non-trivially-separable synthetic
# trajectories — not fit to any real data (there isn't any yet).
_ARCHETYPE_PARAMS = {
    "fast_learner": dict(base_p=0.90, drift=0.004, volatility=0.05, tries_lambda=0.1),
    "average": dict(base_p=0.68, drift=0.0, volatility=0.08, tries_lambda=0.6),
    "struggler": dict(base_p=0.38, drift=-0.004, volatility=0.08, tries_lambda=1.4),
    "inconsistent": dict(base_p=0.60, drift=0.0, volatility=0.22, tries_lambda=0.9),
}

LOOKAHEAD = settings.struggle_window
STRUGGLE_LABEL_THRESHOLD = settings.struggle_correct


def _sample_tries(rng: random.Random, correct: bool, lam: float) -> int:
    if correct:
        return 1 if rng.random() > 0.2 else 2
    # Wrong answers take more taps before moving on; the tail gets heavier
    # for higher-lambda (more struggling) archetypes.
    return 1 + rng.choices([0, 1, 2, 3], weights=[3, 3 + lam, 2 + lam, 1 + lam])[0]


def _simulate_level_sequence(
    rng: random.Random, archetype: str, length: int
) -> list[AttemptRecord]:
    params = _ARCHETYPE_PARAMS[archetype]
    p = params["base_p"]
    seq: list[AttemptRecord] = []
    for _ in range(length):
        p += params["drift"] + rng.gauss(0, params["volatility"]) * 0.15
        p = min(0.98, max(0.05, p))
        correct = rng.random() < p
        tries = _sample_tries(rng, correct, params["tries_lambda"])
        seq.append(AttemptRecord(is_correct=correct, tries=tries, level=1))
    return seq


def generate_dataset(
    n_trajectories: int = 500, level_length: int = 40, seed: int = 42
) -> tuple[np.ndarray, np.ndarray]:
    """Simulate `n_trajectories` per-level attempt sequences and slide a
    window over each to produce (features, label) pairs. `current_level` is
    always 1 in the simulation — extract_features only cares about attempts
    *at* the current level, and the sequence already represents exactly
    that, so the level number itself is an implementation detail here."""
    rng = random.Random(seed)
    X: list[np.ndarray] = []
    y: list[int] = []

    for _ in range(n_trajectories):
        archetype = rng.choice(ARCHETYPES)
        length = max(LOOKAHEAD + 5, level_length + rng.randint(-10, 15))
        seq = _simulate_level_sequence(rng, archetype, length)

        for i in range(2, len(seq) - LOOKAHEAD):
            history_so_far = seq[: i + 1]
            features = extract_features(history_so_far, current_level=1)
            lookahead = seq[i + 1 : i + 1 + LOOKAHEAD]
            correct_ahead = sum(1 for a in lookahead if a.is_correct)
            label = 1 if correct_ahead <= STRUGGLE_LABEL_THRESHOLD else 0
            X.append(features)
            y.append(label)

    return np.array(X), np.array(y)
