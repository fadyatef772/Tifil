"""Sequencing type (ترتيب): put 3 steps in the correct order — ideal for
life-skill routines (handwashing, dressing, morning routine).

Data in `options`:
  {
    "items": [
      {"id": "s1", "label_ar", "label_en", "visual", "step": 1},
      ...
    ],
    "answer": ["s2", "s1", "s3"]   # correct order of item ids
  }

`serialize_for_child` strips each item's `step` (it would reveal the order)
and never ships `answer`. The frontend presents the items shuffled and the
child taps them in order.

Answer contract: `{"answer": {"order": ["s2", "s1", "s3"]}}` (a bare list
is also accepted). Correct only when the order matches exactly.
"""

from app.services.exercise_types.base import ExerciseType


class SequencingType(ExerciseType):
    key = "sequencing"

    def serialize_for_child(self, exercise) -> dict:
        items = [
            {k: v for k, v in item.items() if k != "step"}
            for item in exercise.options["items"]
        ]
        return {"items": items}

    def validate(self, exercise, payload) -> bool:
        if payload.answer is None:
            return False
        if isinstance(payload.answer, dict):
            order = payload.answer.get("order")
        else:
            order = payload.answer
        if not isinstance(order, list):
            return False
        return list(order) == exercise.options["answer"]
