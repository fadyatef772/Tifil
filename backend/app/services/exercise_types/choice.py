"""The original exercise type: pick one option out of a few.

Reference implementation for the pluggable system, kept byte-for-byte
backward compatible: the API still accepts the legacy `option_id` field
(the tapped option's id compared against `correct_option_id`), and ALSO
accepts the same id nested inside the generic `answer` payload
(`{"answer": {"option_id": "..."}}`). Both paths are identical from the
validator's point of view.
"""

from app.services.exercise_types.base import ExerciseType


class ChoiceType(ExerciseType):
    key = "choice"

    def serialize_for_child(self, exercise) -> dict:
        # The options are the candidates; `correct_option_id` is never
        # shipped. Nothing else needs stripping for this type.
        return {"options": exercise.options}

    def validate(self, exercise, payload) -> bool:
        picked = None
        if payload.answer is not None and isinstance(payload.answer, dict):
            nested = payload.answer.get("option_id")
            if isinstance(nested, str):
                picked = nested
        if picked is None:
            picked = payload.option_id
        return picked == exercise.correct_option_id
