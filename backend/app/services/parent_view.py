"""Parent view — read-only aggregation + gentle educational suggestions.

This module is a PURE PROJECTION over existing rows (Attempt, Session,
LevelUpEvent, Skill, Rewards). It never writes to the database, never calls
the adaptive engine, and introduces no new source of truth. Every number and
every tip is derived fresh from rows that the engine / rewards / sessions
layers already own.

=== Suggestions: what they are and are not ===

The suggestions are rule-based EDUCATIONAL TIPS for home activities. They are
NOT:
  * a diagnosis, or an implication of a medical/clinical condition,
  * medical or therapeutic advice,
  * statements of clinical fact.

They ARE gentle, general, optional ideas ("you could try...", "maybe..."),
always phrased positively and addressed to what the PARENT can do — never
"your child has a problem with X". Every rule below is simple, transparent and
deterministic so a parent can see exactly why a tip appeared.

The rules (in evaluation order; the module returns at most
settings.max_suggestions):

  * gentle_practice — a skill with at least
    settings.gentle_practice_min_attempts attempts in the last
    settings.parent_view_week_days days and accuracy at or below
    settings.gentle_practice_max_accuracy gets "you could try a few more
    [skill] activities together" (targets the qualifying skill with the
    lowest recent accuracy, i.e. the most relevant one to work on).
  * revisit — a skill with any prior attempts whose last attempt is older
    than settings.revisit_min_days days gets "it's been a few days since
    [skill] — maybe revisit it" (targets the skill with the longest gap).
  * consistency — a current streak at least
    settings.consistency_min_streak gets "great consistency this week — keep
    the daily routine going".
  * new_level — any level-up event within the last settings.parent_view_week_days
    days gets "nice progress — [skill] reached a new level".
  * encouragement — filler when fewer than two of the above apply: a generic
    "keep playing a little every day" tip. Only ever positive.

The module guarantees at least 2 suggestions (filling with encouragement if
needed) and at most settings.max_suggestions.

Time windows use UTC, matching how every timestamp in this app is stored.
"today" is the current UTC calendar day; "this week" is the rolling last
settings.parent_view_week_days days (so it includes today).
"""

from datetime import datetime, timedelta, timezone
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.models import Attempt, Child, LevelUpEvent, Rewards, Session, Skill

TONE = "encouraging"


def _now_naive() -> datetime:
    """UTC now without tzinfo, matching how SQLite hands back timestamps."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _naive(dt: datetime) -> datetime:
    """Normalize any stored timestamp to naive UTC for comparison."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _skill_ref(skill: Skill) -> dict:
    return {
        "skill_id": skill.id,
        "skill_key": skill.key,
        "name_ar": skill.name_ar,
        "name_en": skill.name_en,
    }


def _period_counts(attempts: list[Attempt], today_start: datetime, week_start: datetime) -> dict:
    """Classify attempts into today / this-week windows. `week` includes
    `today`; the two are separate rollups of the same rows."""
    today = [a for a in attempts if _naive(a.created_at) >= today_start]
    week = [a for a in attempts if _naive(a.created_at) >= week_start]
    return {"today": today, "week": week}


def _skills_practiced(attempts: list[Attempt], skills: list[Skill]) -> list[dict]:
    ids = {a.skill_id for a in attempts}
    return [_skill_ref(s) for s in skills if s.id in ids]


def summary(db: Session, child: Child) -> dict:
    """Today + this-week rollup over the child's existing rows.

    Pure reads: no writes, no engine calls. `stars_earned` in a window equals
    the correct-answer count in that window (the rewards layer awards exactly
    one star per exercise solved correctly)."""
    now = _now_naive()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=settings.parent_view_week_days)

    attempts = list(db.scalars(select(Attempt).where(Attempt.child_id == child.id)))
    skills = list(db.scalars(select(Skill).order_by(Skill.order)))
    sessions = list(db.scalars(select(Session).where(Session.child_id == child.id)))
    level_ups = list(db.scalars(select(LevelUpEvent).where(LevelUpEvent.child_id == child.id)))
    rewards_row = db.scalar(select(Rewards).where(Rewards.child_id == child.id))

    def rollup(rows: list[Attempt]) -> dict:
        if not rows:
            return {
                "activities_done": 0,
                "accuracy": 0.0,
                "sessions_count": 0,
                "stars_earned": 0,
                "skills_practiced": [],
                "level_ups": 0,
            }
        correct = [a for a in rows if a.is_correct]
        session_ids = {a.session_id for a in rows if a.session_id is not None}
        return {
            "activities_done": len(rows),
            "accuracy": len(correct) / len(rows),
            "sessions_count": len(session_ids),
            "stars_earned": len(correct),
            "skills_practiced": _skills_practiced(rows, skills),
            "level_ups": 0,  # filled in below from level-up rows
        }

    periods = _period_counts(attempts, today_start, week_start)
    today = rollup(periods["today"])
    week = rollup(periods["week"])

    def level_ups_in(start: datetime) -> int:
        return sum(1 for ev in level_ups if _naive(ev.created_at) >= start)

    today["level_ups"] = level_ups_in(today_start)
    week["level_ups"] = level_ups_in(week_start)

    return {
        "child": child,
        "today": today,
        "week": week,
        "current_streak": rewards_row.streak if rewards_row else 0,
        "total_stars": rewards_row.total_stars if rewards_row else 0,
    }


# --- Suggestions (gentle, rule-based educational tips) ------------------------
def _tip(
    type_: str,
    skill: Skill | None,
    text_ar: str,
    text_en: str,
) -> dict:
    out = {
        "type": type_,
        "skill": _skill_ref(skill) if skill else None,
        "text_ar": text_ar,
        "text_en": text_en,
        "tone": TONE,
    }
    return out


def _gentle_practice(skill: Skill) -> dict:
    return _tip(
        "gentle_practice",
        skill,
        f"تقدر تجرّبوا تمارين {skill.name_ar} مع بعض أكتر الأسبوع ده — كل محاولة بتحسب.",
        f"You could try a few more {skill.name_en} activities together this week — every try counts.",
    )


def _revisit(skill: Skill) -> dict:
    return _tip(
        "revisit",
        skill,
        f"من شوية أيام متمرّنوش على {skill.name_ar} — ممكن ترجّعوا تاني لو فيه وقت.",
        f"It's been a few days since {skill.name_en} — maybe revisit it when you have time.",
    )


def _consistency() -> dict:
    return _tip(
        "consistency",
        None,
        "استمراركم حلو الأسبوع ده — كمّلوا على الروتين اليومي.",
        "Great consistency this week — keep the daily routine going.",
    )


def _new_level(skill: Skill) -> dict:
    return _tip(
        "new_level",
        skill,
        f"برافو! {skill.name_ar} وصلت لمستوى جديد.",
        f"Nice progress! {skill.name_en} reached a new level.",
    )


def _encouragement() -> dict:
    return _tip(
        "encouragement",
        None,
        "كمّلوا اللعب شوية كل يوم — الخطوات الصغيرة بتعمل فرق.",
        "Keep playing a little every day — small steps add up.",
    )


def suggestions(db: Session, child: Child) -> list[dict]:
    """Rule-based educational tips (see the module docstring for the exact
    rules). Returns 2..settings.max_suggestions items, every one gentle and
    optional — never a diagnosis, never medical or therapeutic advice."""
    now = _now_naive()
    week_start = now - timedelta(days=settings.parent_view_week_days)

    attempts = list(db.scalars(select(Attempt).where(Attempt.child_id == child.id)))
    skills = list(db.scalars(select(Skill).order_by(Skill.order)))
    level_ups = list(db.scalars(select(LevelUpEvent).where(LevelUpEvent.child_id == child.id)))
    rewards_row = db.scalar(select(Rewards).where(Rewards.child_id == child.id))
    streak = rewards_row.streak if rewards_row else 0

    # Per-skill recent + overall history, computed once.
    by_skill: dict[int, list[Attempt]] = {}
    for a in attempts:
        by_skill.setdefault(a.skill_id, []).append(a)

    out: list[dict] = []

    # Rule: gentle_practice — a skill with low recent accuracy gets a gentle
    # "you could try more [skill] activities" idea. Picks the qualifying skill
    # with the lowest recent accuracy (the most relevant one to work on).
    candidates = []
    for skill in skills:
        recent = [a for a in by_skill.get(skill.id, []) if _naive(a.created_at) >= week_start]
        if len(recent) < settings.gentle_practice_min_attempts:
            continue
        acc = mean(1.0 if a.is_correct else 0.0 for a in recent)
        if acc <= settings.gentle_practice_max_accuracy:
            candidates.append((acc, skill))
    if candidates:
        _, skill = min(candidates, key=lambda c: c[0])
        out.append(_gentle_practice(skill))

    # Rule: revisit — a skill with prior practice but a long gap gets a gentle
    # "maybe revisit it" idea. Picks the skill with the oldest last attempt.
    gaps = []
    for skill in skills:
        hist = by_skill.get(skill.id, [])
        if not hist:
            continue
        last = max(_naive(a.created_at) for a in hist)
        days = (now - last).days
        if days >= settings.revisit_min_days:
            gaps.append((last, skill))
    if gaps:
        last, skill = min(gaps, key=lambda g: g[0])
        out.append(_revisit(skill))

    # Rule: consistency — a strong current streak earns a compliment.
    if streak >= settings.consistency_min_streak:
        out.append(_consistency())

    # Rule: new_level — a recent level-up earns a "nice progress" tip.
    recent_level_ups = [ev for ev in level_ups if _naive(ev.created_at) >= week_start]
    if recent_level_ups:
        latest = max(recent_level_ups, key=lambda ev: _naive(ev.created_at))
        skill = next((s for s in skills if s.id == latest.skill_id), None)
        if skill:
            out.append(_new_level(skill))

    # Fill to at least 2 with encouragement; cap at max_suggestions.
    while len(out) < 2:
        out.append(_encouragement())
    return out[: settings.max_suggestions]
