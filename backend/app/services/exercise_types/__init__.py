"""Pluggable exercise-type registry.

This is the dispatch map that makes exercise types extensible. The API layer
only ever calls `serialize_for_child` (to build what the child sees) and
`validate_answer` (to decide correctness); neither the routes nor the
adaptive engine / goals / rewards / ML layers know what a type looks like —
they only consume the boolean `is_correct` the way they always have.

HOW TO ADD A NEW TYPE:
  1. Write `app/services/exercise_types/<name>.py` with a subclass of
     `ExerciseType` implementing `serialize_for_child(exercise)` and
     `validate(exercise, payload)`.
  2. Register it here: import it and add it to `_REGISTRY` below.
That is the entire change — no route, no engine, no schema edit. The child-
facing frontend mirrors this with a renderer registry keyed by the same
`exercise.type` string (see frontend/src/child/exercises/registry.tsx).
"""

from app.services.exercise_types.base import ExerciseType
from app.services.exercise_types.choice import ChoiceType
from app.services.exercise_types.matching import MatchingType
from app.services.exercise_types.sequencing import SequencingType
from app.services.exercise_types.tracing import TracingType

# Dispatch map keyed by exercise.type. Adding a type = one module + one
# entry here (see the docstring above).
_REGISTRY: dict[str, ExerciseType] = {
    t.key: t for t in (ChoiceType(), MatchingType(), SequencingType(), TracingType())
}


def get_type(key: str) -> ExerciseType:
    try:
        return _REGISTRY[key]
    except KeyError:
        raise ValueError(f"unknown exercise type: {key!r}") from None


def known_types() -> list[str]:
    return sorted(_REGISTRY)


def serialize_for_child(exercise) -> dict:
    """The child-facing payload for an exercise, answer keys stripped."""
    return get_type(exercise.type).serialize_for_child(exercise)


def validate_answer(exercise, payload) -> bool:
    """Decide whether a submitted AnswerIn is correct for this exercise."""
    return get_type(exercise.type).validate(exercise, payload)
