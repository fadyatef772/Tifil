"""Goal achievement detection.

A Goal is set by an adult (POST /api/children/{id}/goals): either "practice
this skill" (target_level is null) or "master up to level N"
(target_level=N). This module is the only place that flips a Goal's status
to "achieved" — it only *reads* Mastery and Attempt, it never writes them,
and it never touches the rule-based engine's own state. Call
`check_goal_achievement` after recording an answer for a (child, skill).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.models import Attempt, Child, Goal


def _now() -> datetime:
    return datetime.now(timezone.utc)


def check_goal_achievement(db: Session, child: Child, skill_id: int) -> list[Goal]:
    """Check every active goal the child has on `skill_id` and mark any that
    now qualify as achieved. Returns the goals just achieved (usually
    empty) — callers are free to ignore the return value."""
    active_goals = db.scalars(
        select(Goal).where(
            Goal.child_id == child.id,
            Goal.skill_id == skill_id,
            Goal.status == "active",
        )
    ).all()
    if not active_goals:
        return []

    mastery = next((m for m in child.masteries if m.skill_id == skill_id), None)
    just_achieved: list[Goal] = []

    for goal in active_goals:
        if goal.target_level is not None:
            # "Master up to level N": the rule-based engine's own
            # highest_mastered is the single source of truth here.
            achieved = mastery is not None and mastery.highest_mastered >= goal.target_level
        else:
            # Level-less "practice this skill" goal: achieved after enough
            # correct attempts *since the goal was set* — attempts from
            # before the goal existed don't count towards it.
            correct_since = (
                db.scalar(
                    select(func.count(Attempt.id)).where(
                        Attempt.child_id == child.id,
                        Attempt.skill_id == skill_id,
                        Attempt.is_correct.is_(True),
                        Attempt.created_at >= goal.created_at,
                    )
                )
                or 0
            )
            achieved = correct_since >= settings.goal_practice_attempts_target

        if achieved:
            goal.status = "achieved"
            goal.achieved_at = _now()
            just_achieved.append(goal)

    if just_achieved:
        db.commit()
    return just_achieved
