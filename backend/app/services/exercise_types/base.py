"""Base abstraction for a pluggable exercise type.

An `ExerciseType` has exactly two responsibilities and nothing else:

  * `serialize_for_child(exercise) -> dict` — the payload the child-facing
    API returns for this exercise, with every answer-bearing key stripped,
    so correctness can never be read off the response. For `choice` the
    options are the candidates and `correct_option_id` is simply never
    serialized; for the newer types the hidden key is the pairing / order /
    any other server-side truth.
  * `validate(exercise, payload) -> bool` — decide whether a submitted
    `AnswerIn` is correct. The validator never knows or cares how the
    attempt is recorded: the adaptive engine, mastery, goals, rewards and the
    ML struggle predictor only consume its boolean result, so they stay
    untouched by new types.

Adding a new type means writing one subclass in this package and registering
it in `__init__.py` — no route, no engine, no schema change. The `options`
JSON column on `Exercise` stores whatever type-specific data the type needs
(pairs, items, a guide path, ...). `correct_option_id` is only meaningful for
`choice`; the other types store an "n/a" sentinel because that column
predates the pluggable system and is non-nullable (changing its nullability
would be a migration, which this project deliberately avoids).
"""


class ExerciseType:
    key: str = ""

    def serialize_for_child(self, exercise) -> dict:
        raise NotImplementedError(f"{type(self).__name__} must implement serialize_for_child")

    def validate(self, exercise, payload) -> bool:
        raise NotImplementedError(f"{type(self).__name__} must implement validate")
