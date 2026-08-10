"""The adaptive engine.

This is the pedagogical core. It answers two questions:

  1. select_next_exercise(child) -> what should this child do right now?
  2. record_answer(child, exercise, correct) -> update the child's position
     and return an encouraging result.

Design decisions, stated plainly because they matter in a therapeutic tool:

* It is rule-based, not a black box. An adult must be able to read a child's
  history and see exactly why the app promoted or demoted them. A neural
  recommender cannot offer that, and at this data scale (one child, a handful
  of sessions) it would also just overfit.

* Promotion is slow and demotion is gentle. A child moves up only after
  MASTERY_CORRECT of their last MASTERY_WINDOW answers at a level are right.
  They move down only after a sustained struggle, and never below level 1.

* There is no punishment. A wrong answer returns "try_again" — the same
  exercise is simply offered again. Failure never removes progress within a
  session; it only slows promotion.

Everything here is pure Python over ORM rows, so it is unit-testable with an
in-memory database and no network.
"""

import random
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.models import (
    Attempt,
    Child,
    Exercise,
    Goal,
    LevelUpEvent,
    Mastery,
    Skill,
    SkillLevel,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_masteries(db: Session, child: Child) -> None:
    """Give the child a Mastery row (at level 1) for every skill they lack one
    for. Called lazily so newly seeded skills appear for existing children."""
    existing = {m.skill_id for m in child.masteries}
    skill_ids = db.scalars(select(Skill.id)).all()
    created = False
    for sid in skill_ids:
        if sid not in existing:
            db.add(Mastery(child_id=child.id, skill_id=sid, current_level=1))
            created = True
    if created:
        db.commit()
        db.refresh(child)


def _recent_attempts(
    db: Session, child_id: int, skill_id: int, level: int, limit: int
) -> list[Attempt]:
    stmt = (
        select(Attempt)
        .where(
            Attempt.child_id == child_id,
            Attempt.skill_id == skill_id,
            Attempt.level == level,
        )
        .order_by(Attempt.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def _max_level(db: Session, skill_id: int) -> int:
    return (
        db.scalar(
            select(func.max(SkillLevel.level)).where(
                SkillLevel.skill_id == skill_id
            )
        )
        or 1
    )


def _exercise_for_mastery(db: Session, child: Child, mastery: Mastery) -> Exercise | None:
    """Least-recently-attempted exercise at `mastery`'s current level (nulls
    first), or None if that skill/level has no exercises to serve."""
    level_id = db.scalar(
        select(SkillLevel.id).where(
            SkillLevel.skill_id == mastery.skill_id,
            SkillLevel.level == mastery.current_level,
        )
    )
    if level_id is None:
        return None

    last_seen = (
        select(
            Attempt.exercise_id,
            func.max(Attempt.created_at).label("last"),
        )
        .where(Attempt.child_id == child.id)
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


def _active_goal_skill_ids(db: Session, child_id: int) -> set[int]:
    return set(
        db.scalars(
            select(Goal.skill_id).where(
                Goal.child_id == child_id, Goal.status == "active"
            )
        ).all()
    )


def select_next_exercise(db: Session, child: Child) -> Exercise | None:
    """Choose the next exercise across all of the child's skills.

    Base strategy (unchanged from before goals existed): rotate focus to the
    skill touched least recently, so a session spreads across skills instead
    of drilling one. Within that skill, pick the exercise at the child's
    current level that they've seen least recently (or never), which keeps
    repetition varied without being random.

    Goal weighting (additive): if the child has an active Goal, with
    probability `settings.goal_bias_probability` this instead tries the
    goal skill(s) first, still using the exact same least-recently-touched
    tie-break among them. This is a *weighting*, not a hard restriction —
    it only ever changes which skill is tried first; if none of the goal
    skills currently have a servable exercise, or a child has no goals, or
    the coin flip goes the other way, behaviour falls through to the
    unchanged base rotation over every skill. A child with no goals at all
    sees byte-identical behaviour to before this feature existed."""
    ensure_masteries(db, child)

    masteries = sorted(child.masteries, key=lambda m: m.updated_at or _now())

    goal_skill_ids = _active_goal_skill_ids(db, child.id)
    if goal_skill_ids and random.random() < settings.goal_bias_probability:
        for mastery in masteries:
            if mastery.skill_id not in goal_skill_ids:
                continue
            exercise = _exercise_for_mastery(db, child, mastery)
            if exercise is not None:
                return exercise
        # No goal skill had anything to serve right now — fall through.

    for mastery in masteries:
        exercise = _exercise_for_mastery(db, child, mastery)
        if exercise is not None:
            return exercise

    return None


def record_answer(
    db: Session,
    child: Child,
    exercise: Exercise,
    is_correct: bool,
    tries: int = 1,
    session_id: int | None = None,
) -> dict:
    """Log the attempt and re-evaluate the child's level for that skill.

    Returns a dict the API layer turns into AnswerOut."""
    level = exercise.skill_level
    skill_id = level.skill_id

    db.add(
        Attempt(
            child_id=child.id,
            session_id=session_id,
            exercise_id=exercise.id,
            skill_id=skill_id,
            level=level.level,
            is_correct=is_correct,
            tries=tries,
        )
    )
    db.commit()

    mastery = next(
        (m for m in child.masteries if m.skill_id == skill_id), None
    )
    if mastery is None:  # defensive; ensure_masteries normally covers this
        mastery = Mastery(child_id=child.id, skill_id=skill_id, current_level=1)
        db.add(mastery)
        db.commit()
        db.refresh(child)

    leveled_up = False
    new_level: int | None = None

    # Only a correct answer can trigger re-evaluation of the level, so a child
    # never loses ground mid-struggle from the act of answering itself.
    if is_correct:
        window = _recent_attempts(
            db, child.id, skill_id, mastery.current_level, settings.mastery_window
        )
        correct = sum(1 for a in window if a.is_correct)
        top = _max_level(db, skill_id)
        if (
            correct >= settings.mastery_correct
            and mastery.current_level < top
        ):
            mastery.highest_mastered = max(
                mastery.highest_mastered, mastery.current_level
            )
            mastery.current_level += 1
            mastery.updated_at = _now()
            leveled_up = True
            new_level = mastery.current_level
            # Audit trail for session summaries (see LevelUpEvent's
            # docstring) — purely additive, never read by this function.
            db.add(
                LevelUpEvent(
                    child_id=child.id,
                    session_id=session_id,
                    skill_id=skill_id,
                    new_level=new_level,
                )
            )
        elif correct >= settings.mastery_correct:
            # Mastered the top level; record it, stay put.
            mastery.highest_mastered = max(
                mastery.highest_mastered, mastery.current_level
            )
            mastery.updated_at = _now()
    else:
        # Gentle demotion only after a sustained struggle at this level.
        window = _recent_attempts(
            db, child.id, skill_id, mastery.current_level, settings.struggle_window
        )
        if len(window) >= settings.struggle_window:
            correct = sum(1 for a in window if a.is_correct)
            if correct <= settings.struggle_correct and mastery.current_level > 1:
                mastery.current_level -= 1
                mastery.updated_at = _now()

    mastery.updated_at = _now()
    db.commit()

    return {
        "is_correct": is_correct,
        "feedback": "correct" if is_correct else "try_again",
        "leveled_up": leveled_up,
        "new_level": new_level,
    }
