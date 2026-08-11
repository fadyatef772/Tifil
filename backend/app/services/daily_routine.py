"""Daily Routine — daily streak, today's plan, and a simple activity calendar.

A PURE READ-ONLY PROJECTION over the child's existing `Attempt` rows. There
is deliberately NO new source of truth and NO new storage: a child is
"active" on a calendar day if they have at least one attempt that day, and
everything else (the streak, today's progress, the recent-day calendar) is
derived fresh from those existing timestamps on every read. This matches the
philosophy of the learning journey and the parent view — the adaptive
engine, rewards, sessions, goals, ML, speech and exercise-type layers are
never written or consulted here.

=== Daily streak ===

Consecutive UTC calendar days with at least one attempt. Same-day repeat
visits never inflate it (a day is either active or not). Missing a day ends
the run; the next visit starts a fresh streak of 1.

The streak is *gentle by construction*:

  * If the child has been active today, the streak counts today backwards
    through the consecutive active days.
  * If today has no attempts yet but YESTERDAY was active, the streak still
    reports the run ending yesterday — the day isn't over, so the streak is
    simply still alive and waiting. There is no countdown and no "play or
    you'll lose it" warning anywhere in this module.
  * If the last active day is older than yesterday, the streak is 0 — a
    fresh start, which the UI frames only positively ("Let's start today!").

=== Today's plan ===

A small, fixed daily target reusing the sessions layer's own target
(`settings.session_exercise_target`, default 8) — the same number a session
summary uses for `target_reached`. "done" is the number of attempts logged
today, the exact metric sessions already count, so a struggling child still
makes progress on their plan (no pressure). The frontend renders it as
filled stars/dots, never as a shaming gap.

=== Time ===

UTC throughout, matching how every timestamp in this app is stored; SQLite
hands back naive UTC, so all comparisons normalize to naive UTC first (same
convention as app/services/parent_view.py).
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.models import Attempt, Child

# How many recent days the activity calendar exposes (oldest first).
RECENT_DAY_COUNT = 14


def _now_naive() -> datetime:
    """UTC now without tzinfo, matching how SQLite hands back timestamps."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _naive(dt: datetime) -> datetime:
    """Normalize any stored timestamp to naive UTC for comparison."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _date_key(dt: datetime) -> str:
    return _naive(dt).strftime("%Y-%m-%d")


def _streak(active_days: set[str], today_key: str) -> int:
    """Length of the consecutive active run ending today (or, if today has
    no attempt yet, ending yesterday — the streak is still alive until the
    day is over). A gap older than that resets to 0."""
    cursor = datetime.strptime(today_key, "%Y-%m-%d").date()
    if today_key not in active_days:
        cursor -= timedelta(days=1)
    count = 0
    while cursor.strftime("%Y-%m-%d") in active_days:
        count += 1
        cursor -= timedelta(days=1)
    return count


def daily(db: Session, child: Child) -> dict:
    """Derive the child's daily routine from their existing attempt rows.

    Pure reads only: never writes, never calls the engine, never touches the
    rewards streak (the in-session answer streak lives entirely in
    app/services/rewards.py and is untouched by this feature).
    """
    timestamps = db.scalars(
        select(Attempt.created_at).where(Attempt.child_id == child.id)
    )

    today = _now_naive().date()
    today_key = today.strftime("%Y-%m-%d")

    active_days: set[str] = set()
    today_done = 0
    for ts in timestamps:
        key = _date_key(ts)
        active_days.add(key)
        if key == today_key:
            today_done += 1

    active_today = today_key in active_days

    recent_keys = [
        (today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(RECENT_DAY_COUNT - 1, -1, -1)
    ]

    return {
        "child_id": child.id,
        "daily_streak": _streak(active_days, today_key),
        "active_today": active_today,
        "today_plan": {
            "target": settings.session_exercise_target,
            "done": today_done,
        },
        "recent_days": [
            {"date": key, "active": key in active_days} for key in recent_keys
        ],
    }
