"""Rewards — stars, streak, and unlockable avatars.

Positive reinforcement only, never punishment:

- A star for every exercise solved correctly, no matter how many tries it
  took. A wrong tap earns nothing yet, but it never takes a star back.
- Streak counts consecutive correct answers and returns quietly to zero on a
  wrong answer; nothing else changes — no punishing message, no penalty.
- Avatars unlock as stars accumulate: one new avatar every
  `settings.rewards_avatar_star_step` stars (default 10), with the first
  avatar free at 0 stars so a brand-new child always has a colourful friend.
  Locked avatars are returned to the frontend too, so it can show them
  dimmed as something to look forward to.

This module is deliberately separate from `adaptive_engine.record_answer`:
the pedagogical core stays byte-for-byte unchanged; rewards just ride
alongside it, called from the API layer after an answer is recorded.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.models import Child, Rewards


@dataclass(frozen=True)
class Avatar:
    id: str
    emoji: str
    stars: int  # threshold: stars needed to unlock


def avatar_catalog() -> list[Avatar]:
    """Ordered avatar lineup, cheapest first. Threshold i is i * step for
    i >= 1; the starter avatar (index 0) is free."""
    step = settings.rewards_avatar_star_step
    lineup = [
        ("fox", "🦊"),
        ("koala", "🐨"),
        ("rabbit", "🐰"),
        ("panda", "🐼"),
        ("lion", "🦁"),
        ("frog", "🐸"),
        ("monkey", "🐵"),
        ("unicorn", "🦄"),
    ]
    return [
        Avatar(id=id_, emoji=emoji, stars=0 if i == 0 else i * step)
        for i, (id_, emoji) in enumerate(lineup)
    ]


def ensure_rewards(db: Session, child: Child) -> Rewards:
    """Return the child's Rewards row, creating it (with defaults) if it
    doesn't exist yet. Persists only when it creates."""
    rewards = db.scalar(select(Rewards).where(Rewards.child_id == child.id))
    if rewards is None:
        rewards = Rewards(
            child_id=child.id, total_stars=0, streak=0, unlocked_avatar_ids=[]
        )
        db.add(rewards)
        db.flush()
        db.commit()
        db.refresh(rewards)
    return rewards


def _sync_unlocked(rewards: Rewards) -> None:
    """Re-derive unlocked_avatar_ids from total_stars so stored state always
    agrees with the catalog and the current star threshold."""
    rewards.unlocked_avatar_ids = [
        a.id for a in avatar_catalog() if rewards.total_stars >= a.stars
    ]


def record(db: Session, child: Child, is_correct: bool) -> dict:
    """Update stars/streak after an answer. Returns the reward summary for
    the API layer, including `new_avatar` exactly when this answer unlocked
    one (so the frontend can celebrate it)."""
    rewards = ensure_rewards(db, child)
    before = set(rewards.unlocked_avatar_ids or [])
    if is_correct:
        rewards.total_stars += 1
        rewards.streak += 1
    else:
        # Gentle reset: the counter quietly returns to zero, nothing else.
        rewards.streak = 0
    _sync_unlocked(rewards)
    after = set(rewards.unlocked_avatar_ids)

    new_avatar = None
    if after - before:
        for avatar in avatar_catalog():
            if avatar.id in after and avatar.id not in before:
                new_avatar = {
                    "id": avatar.id,
                    "emoji": avatar.emoji,
                    "stars": avatar.stars,
                }
                break

    db.commit()
    return {
        "stars": rewards.total_stars,
        "streak": rewards.streak,
        "new_avatar": new_avatar,
    }


def get(db: Session, child: Child) -> dict:
    """Full rewards payload for GET /children/{id}/rewards: totals plus the
    whole avatar catalog with unlock state and the child's active avatar."""
    rewards = ensure_rewards(db, child)
    _sync_unlocked(rewards)
    db.commit()

    unlocked = set(rewards.unlocked_avatar_ids or [])
    avatars = [
        {
            "id": a.id,
            "emoji": a.emoji,
            "stars": a.stars,
            "unlocked": a.id in unlocked,
        }
        for a in avatar_catalog()
    ]
    active = next((a for a in reversed(avatars) if a["unlocked"]), None)
    return {
        "child_id": child.id,
        "total_stars": rewards.total_stars,
        "streak": rewards.streak,
        "avatars": avatars,
        "active_avatar": active,
    }
