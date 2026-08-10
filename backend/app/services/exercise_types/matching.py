"""Matching type (توصيل): connect 2-3 pairs — e.g. animal↔sound, color
word↔color swatch, number↔quantity.

Data in `options`:
  {
    "pairs": [
      {"id": "p1", "left": {id,label_ar,label_en,visual},
                  "right": {id,label_ar,label_en,visual}},
      ...
    ],
    "answer": {"<left_id>": "<right_id>", ...}   # server-side pairing truth
  }

`serialize_for_child` ships the pairs (both columns) but NOT the `answer`
map — the correspondence between left and right is the thing the child has
to work out, and the frontend shuffles the right column so the raw order
never leaks it.

Answer contract: `{"answer": {"pairings": {"<left_id>": "<right_id>", ...}}}`.
Correct only when every pair in the submitted mapping matches the stored one
(a partially-right answer is still a wrong answer — try again).
"""

from app.services.exercise_types.base import ExerciseType


def _pairings(payload) -> dict | None:
    if payload.answer is None:
        return None
    if isinstance(payload.answer, dict):
        pairings = payload.answer.get("pairings")
    else:
        pairings = payload.answer
    if isinstance(pairings, dict):
        return pairings
    # Also accept an explicit list of [left_id, right_id] pairs.
    if isinstance(pairings, list):
        result = {}
        for entry in pairings:
            if not (isinstance(entry, (list, tuple)) and len(entry) == 2):
                return None
            result[entry[0]] = entry[1]
        return result
    return None


class MatchingType(ExerciseType):
    key = "matching"

    def serialize_for_child(self, exercise) -> dict:
        return {"pairs": exercise.options["pairs"]}

    def validate(self, exercise, payload) -> bool:
        submitted = _pairings(payload)
        if not submitted:
            return False
        expected = exercise.options["answer"]
        if len(submitted) != len(expected):
            return False
        return all(submitted.get(k) == v for k, v in expected.items())
