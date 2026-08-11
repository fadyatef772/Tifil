"""Verification of the Daily Routine feature (read-only projection).

One new read-only endpoint over existing Attempt timestamps:

  * GET /api/children/{id}/daily -> daily_streak, active_today,
    today_plan {target, done}, recent_days (last 14 days, oldest first).

This script builds a KNOWN attempt history through the real /api/answers
flow (the only writer of attempts), backdates the stored timestamps so the
streak's calendar semantics are truly exercised, and then asserts:

  1. a fresh child starts at daily_streak 0, not active today, plan 0/N.
  2. consecutive days of activity increment the streak (0 -> 0 -> 0 -> 3
     while the run ends yesterday — still "alive" — then -> 4 once today
     is played), and `active_today` flips at exactly the right moment.
  3. same-day repeat visits count toward today's plan but never inflate the
     daily streak.
  4. a missed day (gap) resets the daily streak to 0, with the plan back to
     0 — the UI is the only thing that frames this, positively.
  5. recent_days is the last 14 UTC days, oldest first, with active flags
     matching the backdated attempts exactly.
  6. the endpoint is read-only (repeated reads change nothing) and the daily
     streak is COMPLETELY SEPARATE from the in-session rewards streak: the
     rewards streak stays at the number of consecutive correct answers while
     the daily streak may be 0.

Uses a throwaway SQLite file so it never touches a real db.
"""

import os
from datetime import datetime, timedelta, timezone

os.environ["TIFL_DATABASE_URL"] = "sqlite:///./verify_daily_routine.db"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.domain.models import Attempt, Exercise  # noqa: E402
from app.domain.models import Session as SessionModel  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402
import verify_answers  # noqa: E402,F401

Base.metadata.drop_all(engine)
seed(reset=True)
client = TestClient(app)


def daily(cid: int) -> dict:
    return client.get(f"/api/children/{cid}/daily").json()


def answer_correctly(cid: int, session_id: int | None = None) -> None:
    """Fetch the next exercise and answer it correctly through the API."""
    nxt = client.get(f"/api/children/{cid}/next-exercise").json()
    ex = nxt["exercise"]
    assert ex is not None, "engine ran out of exercises mid-verify"
    db = SessionLocal()
    body = verify_answers.correct_body(db.get(Exercise, ex["id"]))
    db.close()
    payload = {"child_id": cid, "exercise_id": ex["id"], **body, "tries": 1}
    if session_id is not None:
        payload["session_id"] = session_id
    res = client.post("/api/answers", json=payload).json()
    assert res["is_correct"] is True, "expected a correct answer"


def backdate(session_id: int, days_ago: int) -> None:
    """Rewind one session's attempts (and the session itself) to `days_ago`."""
    db = SessionLocal()
    when = datetime.now(timezone.utc) - timedelta(days=days_ago)
    when_naive = when.replace(tzinfo=None)  # SQLite hands back naive UTC
    db.execute(
        SessionModel.__table__.update()
        .where(SessionModel.id == session_id)
        .values(started_at=when_naive)
    )
    db.execute(
        Attempt.__table__.update()
        .where(Attempt.session_id == session_id)
        .values(created_at=when_naive)
    )
    db.commit()
    db.close()


def today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def main() -> None:
    target = settings.session_exercise_target
    print(f"session_exercise_target = {target} (today's plan target)")

    child = client.post(
        "/api/children", json={"name": "Daily Routine Test Child", "preferred_language": "ar"}
    ).json()
    cid = child["id"]

    # --- 1. A fresh child: nothing yet. -----------------------------------
    r = daily(cid)
    assert r["daily_streak"] == 0, r
    assert r["active_today"] is False, r
    assert r["today_plan"] == {"target": target, "done": 0}, r
    assert len(r["recent_days"]) == 14, r
    assert r["recent_days"][-1]["date"] == today_str(), r["recent_days"]
    assert all(not d["active"] for d in r["recent_days"]), r["recent_days"]
    print("1. fresh child: streak=0, not active today, plan 0/"
          f"{target}, 14 empty days")

    # --- 2. Build a 4-day run ending today, oldest day first. -------------
    # Day -3: still more than a day ago -> the streak stays 0 (gap).
    s_3 = client.post(f"/api/children/{cid}/sessions/start").json()["session_id"]
    answer_correctly(cid, s_3)
    backdate(s_3, 3)
    r = daily(cid)
    assert r["daily_streak"] == 0, r
    assert r["active_today"] is False, r

    # Day -2: still not adjacent to today/yesterday -> streak stays 0.
    s_2 = client.post(f"/api/children/{cid}/sessions/start").json()["session_id"]
    answer_correctly(cid, s_2)
    backdate(s_2, 2)
    r = daily(cid)
    assert r["daily_streak"] == 0, r
    assert r["active_today"] is False, r

    # Day -1 (yesterday): now the run {-3,-2,-1} is consecutive and STILL
    # ALIVE (today simply hasn't happened yet) -> streak 3, not active today.
    s_1 = client.post(f"/api/children/{cid}/sessions/start").json()["session_id"]
    answer_correctly(cid, s_1)
    backdate(s_1, 1)
    r = daily(cid)
    assert r["daily_streak"] == 3, r
    assert r["active_today"] is False, r
    print("2. 3 consecutive past days -> streak=3 (alive, waiting for today)")

    # Today: three attempts -> the streak now includes today: 3 + 1 = 4.
    s_today = client.post(f"/api/children/{cid}/sessions/start").json()["session_id"]
    for _ in range(3):
        answer_correctly(cid, s_today)
    r = daily(cid)
    assert r["daily_streak"] == 4, r
    assert r["active_today"] is True, r
    assert r["today_plan"]["done"] == 3, r
    print("3. played 3 today -> streak=4, active_today=True, plan 3/"
          f"{target}")

    # --- 3. Same-day repeats: plan counts, streak does not inflate. -------
    s_repeat = client.post(f"/api/children/{cid}/sessions/start").json()["session_id"]
    for _ in range(2):
        answer_correctly(cid, s_repeat)
    r = daily(cid)
    assert r["daily_streak"] == 4, r  # still 4, NOT 5/6
    assert r["active_today"] is True, r
    assert r["today_plan"]["done"] == 5, r  # 3 + 2 today
    print("4. 2 more today -> streak still 4 (no inflation), plan 5/"
          f"{target}")

    # --- 4. A missed day resets the streak to 0 (gently). -----------------
    # Move every attempt onto distinct past days ENDING 3 days ago, leaving
    # today, yesterday and the day before empty: the child played a
    # consecutive run, then missed a few days. The streak is a fresh start.
    backdate(s_today, 3)
    backdate(s_repeat, 3)  # same day as s_today — still a single active day
    backdate(s_1, 4)
    backdate(s_2, 5)
    backdate(s_3, 6)
    r = daily(cid)
    assert r["daily_streak"] == 0, r
    assert r["active_today"] is False, r
    assert r["today_plan"]["done"] == 0, r
    print("5. gap of a missed day -> streak=0, plan 0/N (fresh start, "
          "never 'you lost your streak')")

    # --- 5. recent_days calendar matches the backdated attempts. ----------
    r = daily(cid)
    days = r["recent_days"]
    assert len(days) == 14, days
    dates = [d["date"] for d in days]
    assert dates == sorted(dates) and len(set(dates)) == 14, dates
    assert dates[-1] == today_str(), dates
    active_dates = {d["date"] for d in days if d["active"]}
    expected = {
        (datetime.strptime(today_str(), "%Y-%m-%d") - timedelta(days=n))
        .strftime("%Y-%m-%d")
        for n in (3, 4, 5, 6)  # the four active days, 3..6 days ago
    }
    assert active_dates == expected, (active_dates, expected)
    print(f"6. recent_days: 14 UTC days, oldest first, active on "
          f"{sorted(active_dates)}")

    # --- 6. Read-only + separation from the in-session rewards streak. ----
    db = SessionLocal()
    before_attempts = db.scalar(
        select(func.count(Attempt.id)).where(Attempt.child_id == cid)
    ) or 0
    db.close()
    for _ in range(3):
        client.get(f"/api/children/{cid}/daily")

    db = SessionLocal()
    after_attempts = db.scalar(
        select(func.count(Attempt.id)).where(Attempt.child_id == cid)
    ) or 0
    db.close()
    assert after_attempts == before_attempts, "daily reads must not create attempts"

    rewards = client.get(f"/api/children/{cid}/rewards").json()
    # Every answer was correct, so the IN-SESSION rewards streak counts them
    # all (8 answers total) — while the daily streak is currently 0. That is
    # the whole point: two completely separate streaks.
    assert rewards["streak"] == before_attempts, (rewards["streak"], before_attempts)
    assert r["daily_streak"] == 0
    assert rewards["streak"] > 0
    print(f"7. {before_attempts} attempts unchanged by daily reads; "
          f"in-session rewards streak = {rewards['streak']} (untouched, "
          f"distinct from daily streak = 0)")

    print("\nALL CHECKS PASSED")


if __name__ == "__main__":
    main()
