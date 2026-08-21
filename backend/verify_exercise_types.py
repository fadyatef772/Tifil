"""End-to-end verification of the pluggable exercise-type system.

Proves, for EACH of the three new types (matching, sequencing, tracing):
  1. The child-facing serialized payload carries NO answer keys (the answer
     stays server-side — the serializer strips it).
  2. A correct structured answer is accepted through the real API
     (is_correct=True, feedback="correct").
  3. A wrong structured answer fails gently (is_correct=False,
     feedback="try_again") and never costs a star (no punishment).
  4. A correct answer still flows through the untouched adaptive engine
     (mastery — the child's level actually promotes) and through rewards
     (stars accumulate).
And the legacy `choice` type still answers through `option_id`
(backward compatibility for verify.py and the original app flow).

The mastery check positions the child's skill at the exercise's own level
(server-side test setup, like the other verify scripts read the correct
answer from the db) so the four correct answers are measured against the
window that matters, and the level promotes.

Uses a throwaway SQLite file so it never touches a real db.
"""

import os

os.environ["TIFL_DATABASE_URL"] = "sqlite:///./verify_exercise_types.db"
os.environ["TIFL_SECRET_KEY"] = "test-only-dev-secret-not-for-production"

from sqlalchemy import func, select  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.domain.models import Exercise, Mastery, SkillLevel  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402
from app.services import exercise_types  # noqa: E402
import verify_answers  # noqa: E402,F401

Base.metadata.drop_all(engine)
seed(reset=True)
client = TestClient(app)

# Create a test parent for auth.
_parent = client.post(
    "/api/auth/signup",
    json={"email": "verify@example.com", "password": "testpass123", "name": "Verify"},
).json()
AUTH = {"Authorization": f"Bearer {_parent['access_token']}"}

MASTERY_CORRECT = 4  # must match settings.mastery_correct


def load_exercise(exercise_id: int) -> Exercise:
    db = SessionLocal()
    ex = db.get(Exercise, exercise_id)
    db.close()
    return ex


def post_answer(child_id: int, exercise: Exercise, body: dict, tries: int = 1) -> dict:
    return client.post(
        "/api/answers",
        json={"child_id": child_id, "exercise_id": exercise.id, **body, "tries": tries},
        headers=AUTH,
    ).json()


def position_skill_at_level(child_id: int, skill_id: int, level: int) -> None:
    """Server-side test setup: put the child at the exercise's level so the
    mastery window measures exactly the answers we're about to submit."""
    db = SessionLocal()
    mastery = db.scalar(
        select(Mastery).where(
            Mastery.child_id == child_id, Mastery.skill_id == skill_id
        )
    )
    assert mastery is not None, "expected a mastery row for every skill"
    mastery.current_level = level
    mastery.highest_mastered = level - 1
    db.commit()
    db.close()


def test_type(child_id: int, type_key: str, initial_stars: int) -> int:
    db = SessionLocal()
    top = (
        select(SkillLevel.skill_id, func.max(SkillLevel.level).label("top"))
        .group_by(SkillLevel.skill_id)
        .subquery()
    )
    ex = db.scalar(
        select(Exercise)
        .join(SkillLevel, Exercise.skill_level_id == SkillLevel.id)
        .join(top, top.c.skill_id == SkillLevel.skill_id)
        .where(Exercise.type == type_key, SkillLevel.level < top.c.top)
        .order_by(Exercise.id)
    )
    level = ex.skill_level.level
    skill_key = ex.skill_level.skill.key
    skill_id = ex.skill_level.skill_id
    db.close()
    assert ex is not None, f"no non-top seeded {type_key} exercise found"
    print(f"\n=== {type_key} (exercise #{ex.id}, skill={skill_key}, level {level}) ===")

    # 1. Serialized child payload carries no answer keys.
    payload = exercise_types.serialize_for_child(ex)
    assert "answer" not in payload, f"{type_key} payload leaked the answer!"
    assert "correct_option_id" not in payload, f"{type_key} payload leaked correct_option_id!"
    if type_key == "sequencing":
        assert all("step" not in item for item in payload["items"]), (
            "sequencing payload leaked the step order!"
        )
    print(f"  serializer: payload keys {sorted(payload.keys())} (no answer keys)")

    # 2. A wrong structured answer fails gently and never costs a star.
    wrong = post_answer(child_id, ex, verify_answers.wrong_body(ex))
    assert wrong["is_correct"] is False, f"{type_key} wrong answer was accepted"
    assert wrong["feedback"] == "try_again"
    assert wrong["rewards"]["streak"] == 0
    rewards = client.get(f"/api/children/{child_id}/rewards", headers=AUTH).json()
    assert rewards["total_stars"] == initial_stars, (
        f"wrong answer changed stars: {initial_stars} -> {rewards['total_stars']}"
    )
    print(f"  wrong answer -> feedback '{wrong['feedback']}', stars unchanged "
          f"({rewards['total_stars']}, no punishment)")

    # 3. Four correct structured answers promote the level (mastery flow)
    #    and earn four stars (rewards flow).
    position_skill_at_level(child_id, skill_id, level)
    leveled_up = None
    for i in range(1, MASTERY_CORRECT + 1):
        res = post_answer(child_id, ex, verify_answers.correct_body(ex))
        assert res["is_correct"] is True, f"{type_key} correct answer #{i} rejected"
        assert res["feedback"] == "correct"
        assert res["rewards"]["stars"] == initial_stars + i, (
            f"star #{i} not earned: {initial_stars + i} expected"
        )
        if res["leveled_up"]:
            leveled_up = res
    assert leveled_up is not None, (
        f"{type_key}: {MASTERY_CORRECT} correct answers did not promote the level"
    )
    assert leveled_up["new_level"] == level + 1
    print(f"  correct answers -> leveled_up to level {leveled_up['new_level']}, "
          f"stars now {initial_stars + MASTERY_CORRECT}")
    return initial_stars + MASTERY_CORRECT


def main() -> None:
    child = client.post(
        "/api/children", json={"name": "Types Test Child", "preferred_language": "ar"}, headers=AUTH
    ).json()
    cid = child["id"]
    print(f"Created child #{cid}: {child['name']}")

    initial = client.get(f"/api/children/{cid}/rewards", headers=AUTH).json()["total_stars"]
    assert initial == 0

    # Legacy choice: still answers through the plain `option_id` field, and
    # also through the generic nested form.
    db = SessionLocal()
    choice_ex = db.scalar(
        select(Exercise).where(Exercise.type == "choice").order_by(Exercise.id)
    )
    db.close()
    legacy = post_answer(cid, choice_ex, {"option_id": choice_ex.correct_option_id})
    assert legacy["is_correct"] is True, "legacy option_id path broke for choice"
    nested = post_answer(
        cid, choice_ex, {"answer": {"option_id": choice_ex.correct_option_id}}
    )
    assert nested["is_correct"] is True, "generic answer path broke for choice"
    print(f"choice back-compat: option_id AND answer.option_id both correct (star {nested['rewards']['stars']})")
    stars = nested["rewards"]["stars"]

    for type_key in ("matching", "sequencing", "tracing"):
        stars = test_type(cid, type_key, stars)

    # Every exercise served by the engine carries a payload with no answer
    # keys, whatever its type.
    nxt = client.get(f"/api/children/{cid}/next-exercise", headers=AUTH).json()["exercise"]
    served = exercise_types.serialize_for_child(load_exercise(nxt["id"]))
    assert "answer" not in served and "correct_option_id" not in served
    print(f"\nServed exercise ({nxt['type']}) payload also carries no answer keys")

    print("\nALL CHECKS PASSED")


if __name__ == "__main__":
    main()
