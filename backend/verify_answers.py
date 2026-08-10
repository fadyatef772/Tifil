"""Shared helpers for the verify scripts: build a correct/wrong answer body
for ANY exercise type by reading the server-side truth (correct_option_id /
the `options` payload) straight from the database.

The verify scripts post through the real API, but they need to know the
correct answer for the exercise the engine just served — which used to mean
reading `correct_option_id`. With pluggable exercise types that truth now
lives in different places per type, so it's kept here once instead of being
re-implemented in every script. The child-facing API never ships any of this
(see app/services/exercise_types/).
"""

from app.domain.models import Exercise


def correct_body(exercise: Exercise) -> dict:
    """A POST /api/answers body that is correct for this exercise."""
    t = exercise.type
    if t == "choice":
        return {"option_id": exercise.correct_option_id}
    if t == "matching":
        return {"answer": {"pairings": dict(exercise.options["answer"])}}
    if t == "sequencing":
        return {"answer": {"order": list(exercise.options["answer"])}}
    if t == "tracing":
        # A perfect trace: every guide point submitted, so coverage is 1.0.
        return {"answer": {"points": [dict(p) for p in exercise.options["guide"]]}}
    raise ValueError(f"unknown exercise type: {t!r}")


def wrong_body(exercise: Exercise) -> dict:
    """A POST /api/answers body that is wrong for this exercise."""
    t = exercise.type
    if t == "choice":
        return {"option_id": "__definitely_wrong__"}
    if t == "matching":
        expected = exercise.options["answer"]
        keys = list(expected.keys())
        values = list(expected.values())
        rotated = {keys[i]: values[(i + 1) % len(values)] for i in range(len(keys))}
        return {"answer": {"pairings": rotated}}
    if t == "sequencing":
        return {"answer": {"order": list(reversed(exercise.options["answer"]))}}
    if t == "tracing":
        # Two points tucked in a corner of the 0..100 space: covers none of
        # the guide, so coverage is ~0.0 and the answer is wrong.
        return {"answer": {"points": [{"x": 3.0, "y": 3.0}, {"x": 8.0, "y": 8.0}]}}
    raise ValueError(f"unknown exercise type: {t!r}")
