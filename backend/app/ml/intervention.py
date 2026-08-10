"""Turns a struggle prediction into a concrete, reversible serving decision.

This module never touches a Mastery row — it only changes which single
exercise is served for one turn, as a warm-up rep at a level the child has
already passed. The rule-based engine (app/services/adaptive_engine.py) is
completely untouched by this file and remains the sole authority on level
progression: nothing here can promote or demote a child.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.models import Attempt, Exercise, SkillLevel


def easier_exercise(
    db: Session, child_id: int, skill_id: int, current_level: int
) -> Exercise | None:
    """Least-recently-seen exercise at `current_level - 1`, for a confidence
    -building rep when the struggle predictor is highly confident. Returns
    None if the child is already at level 1 (nothing easier exists) or the
    skill has no lower level, in which case the caller should fall back to
    just flagging a hint instead."""
    if current_level <= 1:
        return None

    level_id = db.scalar(
        select(SkillLevel.id).where(
            SkillLevel.skill_id == skill_id, SkillLevel.level == current_level - 1
        )
    )
    if level_id is None:
        return None

    last_seen = (
        select(Attempt.exercise_id, func.max(Attempt.created_at).label("last"))
        .where(Attempt.child_id == child_id)
        .group_by(Attempt.exercise_id)
        .subquery()
    )
    stmt = (
        select(Exercise)
        .outerjoin(last_seen, last_seen.c.exercise_id == Exercise.id)
        .where(Exercise.skill_level_id == level_id)
        .order_by(last_seen.c.last.asc().nulls_first())
        .limit(1)
    )
    return db.scalar(stmt)
