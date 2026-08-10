"""Feature extraction for the struggle predictor.

Four features, deliberately simple and inspectable so an adult (or a future
engineer) can read a prediction and understand roughly why it fired:

  0. recent_accuracy            share correct in the last FEATURE_WINDOW
                                 attempts at the child's *current* level
  1. avg_tries                  mean taps-to-correct over that same window
  2. trend                      recent-half accuracy minus older-half
                                 accuracy within the window (negative =
                                 getting worse, positive = improving)
  3. attempts_at_current_level  total attempts logged at this level (bounded
                                 by how much history is fetched — see
                                 struggle_predictor.HISTORY_QUERY_LIMIT)

`AttemptRecord` is a small duck-typed shape used identically for synthetic
training data (synthetic_data.py) and for live ORM-backed prediction
(struggle_predictor.py), so both paths run the exact same feature code.
"""

from dataclasses import dataclass

import numpy as np

FEATURE_WINDOW = 10
FEATURE_NAMES = (
    "recent_accuracy",
    "avg_tries",
    "trend",
    "attempts_at_current_level",
)


@dataclass(frozen=True)
class AttemptRecord:
    is_correct: bool
    tries: int
    level: int


def extract_features(
    history: list[AttemptRecord],
    current_level: int,
    window: int = FEATURE_WINDOW,
) -> np.ndarray:
    """`history` must be ordered oldest -> newest."""
    at_level = [a for a in history if a.level == current_level]
    recent = at_level[-window:]

    if not recent:
        # No data yet at this level: neutral prior, not "struggling".
        return np.array([0.5, 1.0, 0.0, 0.0], dtype=float)

    recent_accuracy = sum(a.is_correct for a in recent) / len(recent)
    avg_tries = sum(a.tries for a in recent) / len(recent)

    half = len(recent) // 2
    if half >= 1:
        older, newer = recent[:half], recent[half:]
        trend = (sum(a.is_correct for a in newer) / len(newer)) - (
            sum(a.is_correct for a in older) / len(older)
        )
    else:
        trend = 0.0

    attempts_at_current_level = float(len(at_level))

    return np.array(
        [recent_accuracy, avg_tries, trend, attempts_at_current_level],
        dtype=float,
    )
