"""Verification of the Learning Journey projection.

GET /api/children/{id}/journey is a READ-ONLY projection over existing
Mastery / Goal / Skill / Rewards data. This script proves the derived stop
statuses follow the locked -> current -> mastered progression as the child
really progresses through the (untouched) engine:

  1. A brand-new child: first stop is "current", everything else "locked",
     zero stars.
  2. An adult-set active goal makes that skill the "current" stop (the
     goal data is reused, not duplicated) even though it isn't first.
  3. Driving a skill to full mastery through the real /api/answers flow
     flips that stop to "mastered" and advances the focus.
  4. Archiving the goal returns the focus to the first non-mastered stop.
  5. The projection itself never writes: attempt count and mastery rows are
     unchanged by any number of journey reads.

Uses a throwaway SQLite file so it never touches a real db.
"""

import os

os.environ["TIFL_DATABASE_URL"] = "sqlite:///./verify_journey.db"

from sqlalchemy import func, select  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.domain.models import Attempt, Exercise, Mastery, SkillLevel  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402
import verify_answers  # noqa: E402,F401

Base.metadata.drop_all(engine)
seed(reset=True)
client = TestClient(app)

MASTERY_CORRECT = settings.mastery_correct


def journey(child_id: int) -> dict:
    return client.get(f"/api/children/{child_id}/journey").json()


def stop(j: dict, key: str) -> dict:
    return next(s for s in j["stops"] if s["skill_key"] == key)


def statuses(j: dict) -> list[str]:
    return [s["status"] for s in j["stops"]]


def attempts_count(child_id: int) -> int:
    db = SessionLocal()
    n = db.scalar(
        select(func.count(Attempt.id)).where(Attempt.child_id == child_id)
    ) or 0
    db.close()
    return n


def mastery_snapshot(child_id: int, skill_id: int) -> tuple[int, int]:
    db = SessionLocal()
    m = db.scalar(
        select(Mastery).where(
            Mastery.child_id == child_id, Mastery.skill_id == skill_id
        )
    )
    snap = (m.current_level, m.highest_mastered)
    db.close()
    return snap


def master_skill(child_id: int, skill_id: int, levels: int) -> None:
    """Drive a skill to full mastery through the real engine (4 correct
    answers at each level, the exact rule the engine promotes on)."""
    for level in range(1, levels + 1):
        for _ in range(MASTERY_CORRECT):
            db = SessionLocal()
            ex = db.scalar(
                select(Exercise)
                .join(SkillLevel, Exercise.skill_level_id == SkillLevel.id)
                .where(SkillLevel.skill_id == skill_id, SkillLevel.level == level)
                .order_by(Exercise.id)
            )
            body = verify_answers.correct_body(ex)
            db.close()
            res = client.post(
                "/api/answers",
                json={
                    "child_id": child_id,
                    "exercise_id": ex.id,
                    **body,
                    "tries": 1,
                },
            ).json()
            assert res["is_correct"] is True, "expected a correct answer"


def main() -> None:
    child = client.post(
        "/api/children", json={"name": "Journey Test Child", "preferred_language": "ar"}
    ).json()
    cid = child["id"]

    # 1. Brand-new child: first stop is the active focus, rest locked.
    j = journey(cid)
    assert j["total_stars"] == 0
    assert statuses(j) == ["current"] + ["locked"] * (len(j["stops"]) - 1), statuses(j)
    current = stop(j, j["stops"][0]["skill_key"])
    assert current["current_level"] == 1 and current["highest_mastered"] == 0
    print(f"1. new child -> current='{current['skill_key']}', "
          f"{statuses(j).count('locked')} locked, {j['total_stars']} stars")

    # 2. An active goal makes that skill the current stop (reuses goal data).
    colors = stop(j, "colors")
    dressing = stop(j, "dressing")
    client.post(
        f"/api/children/{cid}/goals",
        json={"skill_id": dressing["skill_id"], "target_level": 2},
    )
    j2 = journey(cid)
    now_current = [s for s in j2["stops"] if s["status"] == "current"][0]
    assert now_current["skill_key"] == "dressing", "goal skill should be current"
    assert now_current["is_active_goal"] is True
    assert stop(j2, "colors")["status"] == "locked", "colors is now behind the goal"
    print("2. active goal on 'dressing' -> current='dressing' (goal skill, not first)")

    # 3. Master colors through the real engine: it flips to 'mastered'.
    master_skill(cid, colors["skill_id"], colors["total_levels"])
    j3 = journey(cid)
    assert stop(j3, "colors")["status"] == "mastered", "colors should be mastered"
    assert stop(j3, "colors")["highest_mastered"] == colors["total_levels"]
    # Focus is still the goal skill until it too is done.
    assert stop(j3, "dressing")["status"] == "current"
    print(f"3. colors mastered -> 'mastered'; focus stays on goal 'dressing' "
          f"(stars now {j3['total_stars']})")

    # 4. Archiving the goal returns focus to the first non-mastered stop.
    goals = client.get(f"/api/children/{cid}/goals").json()
    client.patch(f"/api/goals/{goals[0]['id']}", json={"status": "archived"})
    j4 = journey(cid)
    focus = [s for s in j4["stops"] if s["status"] == "current"][0]
    assert focus["skill_key"] == "numbers", "focus should advance to 'numbers'"
    assert stop(j4, "numbers")["status"] == "current"
    assert stop(j4, "colors")["status"] == "mastered"
    print(f"4. goal archived -> current='numbers' (first non-mastered), "
          f"colors stays 'mastered'")

    # 5. Stars ride along, and the projection is read-only.
    expected_stars = colors["total_levels"] * MASTERY_CORRECT
    assert j4["total_stars"] == expected_stars, (
        f"stars {j4['total_stars']} != {expected_stars} after {expected_stars} "
        "correct answers"
    )
    snapshot = mastery_snapshot(cid, colors["skill_id"])
    before = attempts_count(cid)
    for _ in range(3):
        journey(cid)  # reading the journey must not write anything
    assert attempts_count(cid) == before, "journey reads must not create attempts"
    assert mastery_snapshot(cid, colors["skill_id"]) == snapshot, (
        "journey reads must not change mastery"
    )
    print(f"5. {before} attempts created by answering, unchanged by journey reads; "
          f"stars match rewards ({j4['total_stars']})")

    print("\nALL CHECKS PASSED")


if __name__ == "__main__":
    main()
