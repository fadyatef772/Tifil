"""End-to-end smoke test of Sessions + Goals through the real API.

Proves: a session can be started, tracks attempts via session_id, ends with
a summary (attempts, accuracy, skills practiced, level-ups); a goal (both
the level-based and the level-less kind) can be created, nudges exercise
selection towards its skill, and is detected as achieved. Uses a throwaway
SQLite file so it never touches a real db.
"""

import os

os.environ["TIFL_DATABASE_URL"] = "sqlite:///./verify_sessions.db"
os.environ["TIFL_SECRET_KEY"] = "test-only-dev-secret-not-for-production"

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.domain.models import Exercise  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402
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


def answer_correctly(child_id: int, session_id: int | None = None) -> dict | None:
    """Fetch the next exercise and answer it correctly. Returns None if the
    engine has nothing left to serve (all_caught_up)."""
    nxt = client.get(f"/api/children/{child_id}/next-exercise", headers=AUTH).json()
    ex = nxt["exercise"]
    if ex is None:
        return None

    db = SessionLocal()
    body = verify_answers.correct_body(db.get(Exercise, ex["id"]))
    db.close()

    payload = {
        "child_id": child_id,
        "exercise_id": ex["id"],
        **body,
        "tries": 1,
    }
    if session_id is not None:
        payload["session_id"] = session_id
    res = client.post("/api/answers", json=payload, headers=AUTH).json()
    return {"skill_id": ex["skill_id"], "skill_key": ex["skill_key"], **res}


def main() -> None:
    # 1. Create a child
    child = client.post(
        "/api/children", json={"name": "Session Test Child", "preferred_language": "ar"}, headers=AUTH
    ).json()
    cid = child["id"]
    print(f"Created child #{cid}: {child['name']}")

    # 2. Start a session
    start = client.post(f"/api/children/{cid}/sessions/start", headers=AUTH).json()
    sid = start["session_id"]
    target = start["target_exercises"]
    print(f"Started session #{sid}, target = {target} exercises")
    assert target > 0

    # 3. Play exactly `target` exercises through this session
    seen_skill_ids: list[int] = []
    for i in range(target):
        result = answer_correctly(cid, session_id=sid)
        assert result is not None, "engine ran out of exercises mid-session"
        assert result["is_correct"], "expected a correct answer"
        if result["skill_id"] not in seen_skill_ids:
            seen_skill_ids.append(result["skill_id"])
    print(f"Answered {target} exercises correctly across {len(seen_skill_ids)} skill(s)")

    # 4. End the session and check the summary
    summary = client.post(f"/api/sessions/{sid}/end", headers=AUTH).json()
    assert summary["ended_at"] is not None, "session should be marked ended"
    assert summary["total_attempts"] == target
    assert summary["target_reached"] is True
    print(
        f"\nSession #{sid} summary: {summary['total_attempts']} attempts, "
        f"{summary['accuracy']:.0%} accuracy, "
        f"{len(summary['skills'])} skill(s) practiced, "
        f"{len(summary['level_ups'])} level-up(s)"
    )
    for sk in summary["skills"]:
        print(f"  {sk['name_en']:16} {sk['attempts']} attempts, {sk['accuracy']:.0%} accuracy")
    for lu in summary["level_ups"]:
        print(f"  -> {lu['name_en']} promoted to level {lu['new_level']}")

    # Fetching the same summary again (GET, not just the POST /end response)
    # should agree exactly.
    reread = client.get(f"/api/sessions/{sid}/summary", headers=AUTH).json()
    assert reread == summary, "GET summary should match the /end response"

    # Ending an already-ended session should be idempotent, not an error.
    again = client.post(f"/api/sessions/{sid}/end", headers=AUTH).json()
    assert again["ended_at"] == summary["ended_at"]
    print("Re-ending an already-ended session is idempotent (no error, same ended_at)")

    # Recent-sessions listing should include it.
    recent = client.get(f"/api/children/{cid}/sessions", headers=AUTH).json()
    assert any(s["session_id"] == sid for s in recent)
    print(f"GET .../sessions lists {len(recent)} recent session(s), including #{sid}")

    # 5. Goals: one level-based, one level-less, on two different skills seen above
    assert len(seen_skill_ids) >= 2, "need at least 2 distinct skills to test both goal kinds"
    level_goal_skill, practice_goal_skill = seen_skill_ids[0], seen_skill_ids[1]

    level_goal = client.post(
        f"/api/children/{cid}/goals",
        json={"skill_id": level_goal_skill, "target_level": 2}, headers=AUTH,
    ).json()
    practice_goal = client.post(
        f"/api/children/{cid}/goals", json={"skill_id": practice_goal_skill}, headers=AUTH
    ).json()
    print(
        f"\nCreated goal #{level_goal['id']} ({level_goal['skill_key']} -> level 2) "
        f"and goal #{practice_goal['id']} ({practice_goal['skill_key']} -> practice)"
    )
    assert level_goal["status"] == "active"
    assert practice_goal["status"] == "active"

    # 6. Keep answering correctly (no session this time -- goals don't need
    # one) until both goals are achieved, or give up after a generous cap.
    MAX_ATTEMPTS = 250
    level_done = practice_done = False
    attempts_made = 0
    for i in range(MAX_ATTEMPTS):
        result = answer_correctly(cid, session_id=None)
        if result is None:
            break
        attempts_made += 1
        if not (level_done and practice_done):
            goals = {g["id"]: g for g in client.get(f"/api/children/{cid}/goals", headers=AUTH).json()}
            level_done = goals[level_goal["id"]]["status"] == "achieved"
            practice_done = goals[practice_goal["id"]]["status"] == "achieved"
            if level_done and practice_done:
                break

    goals_final = {g["id"]: g for g in client.get(f"/api/children/{cid}/goals", headers=AUTH).json()}
    level_goal_final = goals_final[level_goal["id"]]
    practice_goal_final = goals_final[practice_goal["id"]]

    print(f"After {attempts_made} more correct answers:")
    print(
        f"  Level goal ({level_goal_final['skill_key']} -> level 2): "
        f"status={level_goal_final['status']}, "
        f"highest_mastered={level_goal_final['highest_mastered']}"
    )
    print(
        f"  Practice goal ({practice_goal_final['skill_key']}): "
        f"status={practice_goal_final['status']}"
    )

    assert level_goal_final["status"] == "achieved", (
        f"level-based goal did not reach 'achieved' within {MAX_ATTEMPTS} attempts "
        f"(highest_mastered={level_goal_final['highest_mastered']})"
    )
    assert level_goal_final["achieved_at"] is not None
    assert practice_goal_final["status"] == "achieved", (
        f"level-less goal did not reach 'achieved' within {MAX_ATTEMPTS} attempts"
    )
    assert practice_goal_final["achieved_at"] is not None

    # 7. PATCH still works for a manual override (archive an achieved goal)
    archived = client.patch(
        f"/api/goals/{practice_goal['id']}", json={"status": "archived"}, headers=AUTH
    ).json()
    assert archived["status"] == "archived"
    print(f"Archived goal #{practice_goal['id']} via PATCH -- status now '{archived['status']}'")

    print("\nALL CHECKS PASSED")


if __name__ == "__main__":
    main()
