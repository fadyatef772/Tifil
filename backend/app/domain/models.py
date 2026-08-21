"""Domain models.

The shape of the data encodes the pedagogy:

- A Skill (e.g. "colors", "handwashing") has ordered SkillLevels.
- Each SkillLevel has one or more Exercises.
- A Child accumulates Attempts, grouped into Sessions.
- A child's position in every skill is tracked in one Mastery row per
  (child, skill): the current level and the mastered levels below it.

Nothing here computes difficulty — the adaptive engine reads these rows and
decides. Keeping the model dumb keeps the engine testable and auditable,
which matters because an adult must be able to see *why* the app moved a
child up or down.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Parent(Base):
    """Parent account. Only parents have credentials (email + password);
    children NEVER type a password — they pick their avatar from the
    child picker screen after the parent is logged in."""

    __tablename__ = "parents"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    children: Mapped[list["Child"]] = relationship(
        back_populates="parent", cascade="all, delete-orphan"
    )


class Child(Base):
    __tablename__ = "children"

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("parents.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(120))
    # "ar" or "en" — the child's default interface language.
    preferred_language: Mapped[str] = mapped_column(String(2), default="ar")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    parent: Mapped["Parent | None"] = relationship(back_populates="children")
    masteries: Mapped[list["Mastery"]] = relationship(
        back_populates="child", cascade="all, delete-orphan"
    )
    attempts: Mapped[list["Attempt"]] = relationship(
        back_populates="child", cascade="all, delete-orphan"
    )
    rewards: Mapped["Rewards | None"] = relationship(
        back_populates="child", cascade="all, delete-orphan", uselist=False
    )


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(60), unique=True)
    # "cognitive" or "daily_life"
    category: Mapped[str] = mapped_column(String(30))
    name_ar: Mapped[str] = mapped_column(String(120))
    name_en: Mapped[str] = mapped_column(String(120))
    icon: Mapped[str] = mapped_column(String(40), default="star")
    order: Mapped[int] = mapped_column(Integer, default=0)

    levels: Mapped[list["SkillLevel"]] = relationship(
        back_populates="skill",
        cascade="all, delete-orphan",
        order_by="SkillLevel.level",
    )


class SkillLevel(Base):
    __tablename__ = "skill_levels"

    id: Mapped[int] = mapped_column(primary_key=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"))
    level: Mapped[int] = mapped_column(Integer)  # 1-based
    name_ar: Mapped[str] = mapped_column(String(160))
    name_en: Mapped[str] = mapped_column(String(160))

    skill: Mapped["Skill"] = relationship(back_populates="levels")
    exercises: Mapped[list["Exercise"]] = relationship(
        back_populates="skill_level", cascade="all, delete-orphan"
    )


class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(primary_key=True)
    skill_level_id: Mapped[int] = mapped_column(ForeignKey("skill_levels.id"))
    # Pluggable exercise types — see app/services/exercise_types/:
    #   "choice"      prompt + 2-4 options, one correct (the MVP type)
    #   "matching"    connect 2-3 pairs (animal↔sound, number↔quantity, ...)
    #   "sequencing"  order 3 steps (routines: handwashing, dressing, ...)
    #   "tracing"     finger-trace a guide glyph (fine-motor practice,
    #                 lenient coverage check, NOT handwriting recognition)
    type: Mapped[str] = mapped_column(String(20), default="choice")
    prompt_ar: Mapped[str] = mapped_column(String(240))
    prompt_en: Mapped[str] = mapped_column(String(240))

    # Type-specific data for the exercise (the shape is the type's contract):
    #   choice:     list of {"id","label_ar","label_en","visual"}
    #   matching:   {"pairs": [{id,left,right}], "answer": {left_id: right_id}}
    #   sequencing: {"items": [{id,label_ar,label_en,visual,step}],
    #                "answer": [item_id, ...]}           (correct order)
    #   tracing:    {"glyph","visual","guide": [{"x","y"}, ...]} (0..100 space)
    # `correct_option_id` is only meaningful for "choice"; the other types
    # store an "n/a" sentinel because the column predates the pluggable
    # system and is non-nullable (no migration on existing dbs).
    options: Mapped[list] = mapped_column(JSON)
    correct_option_id: Mapped[str] = mapped_column(String(40))

    skill_level: Mapped["SkillLevel"] = relationship(back_populates="exercises")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("children.id"))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("children.id"))
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("sessions.id"), nullable=True
    )
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id"))
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"))
    level: Mapped[int] = mapped_column(Integer)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    # How many taps the child needed on this exercise before getting it right.
    tries: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    child: Mapped["Child"] = relationship(back_populates="attempts")


class Mastery(Base):
    __tablename__ = "masteries"

    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("children.id"))
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"))
    current_level: Mapped[int] = mapped_column(Integer, default=1)
    # Highest level the child has demonstrated mastery of (0 = none yet).
    highest_mastered: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    child: Mapped["Child"] = relationship(back_populates="masteries")


class Goal(Base):
    """An adult-set target for a child on one skill: either "practice this
    skill" (target_level is null) or "master up to level N" (target_level=N).
    Achievement is decided by app/services/goals.py, not by the rule-based
    engine itself — this table only records the outcome."""

    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("children.id"))
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"))
    target_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # "active" | "achieved" | "archived"
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    achieved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Rewards(Base):
    """Positive-reinforcement state for one child: stars, current streak, and
    which avatars have been unlocked. One row per child.

    This is a separate table (rather than columns on Child) on purpose:
    `Base.metadata.create_all` creates *missing tables* on an existing
    database but never adds *columns* to an existing table, so a new table is
    the only way the feature appears on an existing `tifl.db` with no manual
    migration — the same reason Goal and LevelUpEvent are separate tables.

    Rules (see app/services/rewards.py — the engine never writes these):
    - total_stars only ever increases, one star per exercise solved correctly.
    - streak counts consecutive correct answers and returns quietly to zero
      on a wrong answer; nothing is ever deducted.
    - unlocked_avatar_ids is derived from total_stars (the avatar catalog and
      its star thresholds live in app/services/rewards.py)."""

    __tablename__ = "rewards"

    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("children.id"), unique=True)
    total_stars: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    # Avatar ids the child has unlocked so far, e.g. ["fox", "koala"].
    unlocked_avatar_ids: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    child: Mapped["Child"] = relationship(back_populates="rewards")


class LevelUpEvent(Base):
    """An audit trail row written whenever adaptive_engine.record_answer
    actually promotes a child's level, so a session summary can report
    "which level-ups happened during this session" without re-deriving it
    from Mastery.updated_at (which is touched on every answer, not just
    promotions, and so can't be used for this)."""

    __tablename__ = "level_up_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("children.id"))
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("sessions.id"), nullable=True
    )
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"))
    new_level: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
