"""End-to-end smoke test of the learning loop through the real API.

Proves: a child is created, the engine serves exercises, correct answers
eventually trigger a level-up, and progress is reported. Uses a throwaway
SQLite file so it never touches a real db.
"""

import os

os.environ["TIFL_DATABASE_URL"] = "sqlite:///./verify.db"

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402
import verify_answers  # noqa: E402,F401

Base.metadata.drop_all(engine)
seed(reset=True)
client = TestClient(app)


def answer_correctly(child_id: int, n: int) -> list[dict]:
    """Fetch and correctly answer n exercises, returning each result."""
    results = []
    for _ in range(n):
        nxt = client.get(f"/api/children/{child_id}/next-exercise").json()
        ex = nxt["exercise"]
        if ex is None:
            break
        # Build the correct answer from the server-side truth in the db —
        # this now covers every exercise type, not just choice.
        from app.core.database import SessionLocal
        from app.domain.models import Exercise

        db = SessionLocal()
        body = verify_answers.correct_body(db.get(Exercise, ex["id"]))
        db.close()

        res = client.post(
            "/api/answers",
            json={"child_id": child_id, "exercise_id": ex["id"], **body, "tries": 1},
        ).json()
        results.append({"skill": ex["skill_key"], "level": ex["level"], **res})
    return results


def main():
    # 1. Create a child
    child = client.post(
        "/api/children", json={"name": "Test Child", "preferred_language": "ar"}
    ).json()
    cid = child["id"]
    print(f"Created child #{cid}: {child['name']}")

    # 2. Health + first exercise served
    assert client.get("/api/health").json()["status"] == "ok"
    first = client.get(f"/api/children/{cid}/next-exercise").json()
    assert first["exercise"] is not None, "engine served no exercise"
    print(f"First exercise skill: {first['exercise']['skill_key']} "
          f"(level {first['exercise']['level']})")

    # 3. Answer 60 correctly and confirm at least one level-up fired.
    #    (Calibrated to the full curriculum: the engine rotates across all
    #    skills, so 60 answers guarantee ~4+ correct answers on at least one
    #    skill — the mastery_window/mastery_correct promotion threshold.
    #    Raised from 40 when 5 more skills were added to the seed.)
    results = answer_correctly(cid, 60)
    level_ups = [r for r in results if r["leveled_up"]]
    print(f"Answered {len(results)} correctly; {len(level_ups)} level-up(s):")
    for lu in level_ups:
        print(f"  -> {lu['skill']} promoted to level {lu['new_level']}")
    assert level_ups, "expected at least one promotion after 40 correct answers"

    # 4. A wrong answer returns encouraging feedback, never an error
    nxt = client.get(f"/api/children/{cid}/next-exercise").json()["exercise"]
    from app.core.database import SessionLocal
    from app.domain.models import Exercise

    db = SessionLocal()
    body = verify_answers.wrong_body(db.get(Exercise, nxt["id"]))
    db.close()
    wrong = client.post(
        "/api/answers",
        json={"child_id": cid, "exercise_id": nxt["id"], **body, "tries": 3},
    ).json()
    assert wrong["is_correct"] is False
    assert wrong["feedback"] == "try_again"
    print(f"Wrong answer feedback: '{wrong['feedback']}' (no punishment)")

    # 5. Progress report
    prog = client.get(f"/api/children/{cid}/progress").json()
    print(f"\nProgress for {prog['child']['name']}: "
          f"{prog['total_attempts']} attempts, "
          f"{prog['overall_accuracy']:.0%} accuracy")
    for s in prog["skills"]:
        print(f"  {s['name_en']:16} level {s['current_level']}/{s['total_levels']}"
              f"  mastered up to {s['highest_mastered']}"
              f"  ({s['attempts']} attempts, {s['accuracy']:.0%})")

    print("\nALL CHECKS PASSED")


if __name__ == "__main__":
    main()
