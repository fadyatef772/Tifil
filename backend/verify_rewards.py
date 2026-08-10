"""End-to-end smoke test of the Rewards system through the real API.

Proves the three reward rules:
  1. A correct answer increases total stars AND the streak; the answer
     response reports the new totals.
  2. A wrong answer resets the streak to zero but NEVER reduces stars, and
     solving the same exercise correctly afterwards still earns the star.
  3. Accumulating enough stars (one new avatar every 10) unlocks the next
     avatar — the answer that crosses the threshold reports `new_avatar`,
     and GET /children/{id}/rewards reflects the unlocked set.

Uses a throwaway SQLite file so it never touches a real db.
"""

import os

os.environ["TIFL_DATABASE_URL"] = "sqlite:///./verify_rewards.db"

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.domain.models import Exercise  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402
import verify_answers  # noqa: E402,F401

Base.metadata.drop_all(engine)
seed(reset=True)
client = TestClient(app)

AVATAR_STEP = 10  # must match settings.rewards_avatar_star_step


def fetch_next(child_id: int) -> dict:
    nxt = client.get(f"/api/children/{child_id}/next-exercise").json()
    assert nxt["exercise"] is not None, "engine served no exercise"
    return nxt["exercise"]


def answer_correctly(child_id: int, tries: int = 1) -> dict:
    ex = fetch_next(child_id)
    db = SessionLocal()
    body = verify_answers.correct_body(db.get(Exercise, ex["id"]))
    db.close()
    res = client.post(
        "/api/answers",
        json={"child_id": child_id, "exercise_id": ex["id"], **body, "tries": tries},
    ).json()
    assert res["is_correct"] is True, "expected a correct answer"
    return res


def main() -> None:
    # 1. Fresh child starts with 0 stars, 0 streak, starter avatar unlocked.
    child = client.post(
        "/api/children", json={"name": "Rewards Test Child", "preferred_language": "ar"}
    ).json()
    cid = child["id"]
    print(f"Created child #{cid}: {child['name']}")

    rewards0 = client.get(f"/api/children/{cid}/rewards").json()
    assert rewards0["total_stars"] == 0
    assert rewards0["streak"] == 0
    assert rewards0["active_avatar"]["id"] == "fox"
    unlocked0 = {a["id"] for a in rewards0["avatars"] if a["unlocked"]}
    assert unlocked0 == {"fox"}, f"expected only starter avatar, got {unlocked0}"
    print("Initial rewards: 0 stars, 0 streak, only starter avatar unlocked")

    # 2. Three correct answers: +3 stars, streak climbs to 3.
    for i in range(1, 4):
        res = answer_correctly(cid)
        assert res["rewards"]["stars"] == i, f"expected {i} stars"
        assert res["rewards"]["streak"] == i, f"expected streak {i}"
    print("3 correct answers -> 3 stars, streak 3 (tracked in each answer)")

    # 3. A wrong answer resets the streak but takes no stars away.
    wrong_ex = fetch_next(cid)
    db = SessionLocal()
    wrong_body = verify_answers.wrong_body(db.get(Exercise, wrong_ex["id"]))
    db.close()
    wrong = client.post(
        "/api/answers",
        json={"child_id": cid, "exercise_id": wrong_ex["id"], **wrong_body, "tries": 1},
    ).json()
    assert wrong["is_correct"] is False
    assert wrong["rewards"]["stars"] == 3, "wrong answer must not reduce stars"
    assert wrong["rewards"]["streak"] == 0, "wrong answer resets the streak"
    print("Wrong answer -> streak 0, stars still 3 (gentle reset, no penalty)")

    # 4. Solving the SAME exercise correctly afterwards (tries=2) still earns
    #    exactly one star — repetition is never punished or double-counted.
    db = SessionLocal()
    correct_body = verify_answers.correct_body(db.get(Exercise, wrong_ex["id"]))
    db.close()
    res = client.post(
        "/api/answers",
        json={"child_id": cid, "exercise_id": wrong_ex["id"], **correct_body, "tries": 2},
    ).json()
    assert res["is_correct"] is True
    assert res["rewards"]["stars"] == 4, "solving the exercise still earns the star"
    assert res["rewards"]["streak"] == 1, "streak restarts at 1"
    print("Same exercise solved correctly (2 tries) -> +1 star (total 4), streak 1")

    # 5. Keep answering correctly until 10 stars total: the 10th star unlocks
    #    the koala avatar and the response says so.
    need = AVATAR_STEP - 4  # 6 more correct answers
    for i in range(1, need + 1):
        res = answer_correctly(cid)
        stars = 4 + i
        assert res["rewards"]["stars"] == stars, f"expected {stars} stars"
        if stars == AVATAR_STEP:
            assert res["rewards"]["new_avatar"] is not None
            assert res["rewards"]["new_avatar"]["id"] == "koala", (
                f"expected koala to unlock at {AVATAR_STEP} stars"
            )
            print(
                f"Star #{AVATAR_STEP}: avatar '{res['rewards']['new_avatar']['id']}' "
                f"({res['rewards']['new_avatar']['emoji']}) unlocked"
            )
        else:
            assert res["rewards"]["new_avatar"] is None, (
                f"no avatar should unlock at {stars} stars"
            )

    # 6. GET /rewards agrees: koala unlocked and reflected everywhere.
    rewards_final = client.get(f"/api/children/{cid}/rewards").json()
    assert rewards_final["total_stars"] == AVATAR_STEP
    # Uninterrupted run since step 4's correct answer: 1 (step 4) + need.
    assert rewards_final["streak"] == need + 1
    unlocked_final = {a["id"] for a in rewards_final["avatars"] if a["unlocked"]}
    assert unlocked_final == {"fox", "koala"}, f"unexpected unlocks: {unlocked_final}"
    assert rewards_final["active_avatar"]["id"] == "koala"
    print(
        f"Final rewards: {rewards_final['total_stars']} stars, "
        f"streak {rewards_final['streak']}, unlocked: "
        f"{', '.join(sorted(unlocked_final))}"
    )

    print("\nALL CHECKS PASSED")


if __name__ == "__main__":
    main()
