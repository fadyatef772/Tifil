"""Pydantic schemas — the public API contract.

The child-facing exercise payload deliberately omits `correct_option_id`:
the answer is checked server-side so it never ships to the browser.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# --- Children -------------------------------------------------------------
class ChildCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    preferred_language: str = Field(default="ar", pattern="^(ar|en)$")


class ChildOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    preferred_language: str
    created_at: datetime


# --- Exercises ------------------------------------------------------------
class OptionOut(BaseModel):
    id: str
    label_ar: str
    label_en: str
    visual: str


class ExerciseOut(BaseModel):
    """What the child interface receives. No correct answer inside.

    `options` is the legacy field, kept byte-for-byte for `choice` exercises.
    `payload` is the type-specific child-facing payload produced by the
    exercise-type serializer (app/services/exercise_types/), with every
    answer-bearing key stripped. For `choice`, `payload["options"]` mirrors
    `options`; for the newer types `options` is empty and `payload` carries
    the pairs / items / guide path.
    """

    id: int
    skill_id: int
    skill_key: str
    skill_name_ar: str
    skill_name_en: str
    category: str
    level: int
    type: str
    prompt_ar: str
    prompt_en: str
    options: list[OptionOut] = []
    payload: dict


class StruggleSignalOut(BaseModel):
    """The ML struggle predictor's read on the child's current level, and
    what (if anything) the serving layer did about it. See
    app/ml/struggle_predictor.py — trained on synthetic data, proof of
    concept, never overrides the rule-based engine's level decisions."""

    model_config = ConfigDict(protected_namespaces=())

    is_struggling: bool
    confidence: float  # P(struggling), 0..1
    model_available: bool  # False if no trained artifact could be loaded
    intervention: str | None = None  # "eased_difficulty" | "hint_suggested" | None


class NextExerciseOut(BaseModel):
    """The engine's answer to 'what should this child do next?'"""

    exercise: ExerciseOut | None
    # True when every skill is at its top mastered level — nothing harder left.
    all_caught_up: bool = False
    struggle_signal: StruggleSignalOut | None = None


# --- Rewards ---------------------------------------------------------------
class AvatarOut(BaseModel):
    id: str
    emoji: str
    # Stars needed to unlock this avatar (0 = free starter avatar).
    stars: int
    unlocked: bool = True  # a freshly-unlocked avatar is always unlocked


class RewardsOut(BaseModel):
    """GET /api/children/{id}/rewards — stars, streak, and the full avatar
    catalog with per-avatar unlock state. The catalog lives here so the
    frontend never hardcodes it; locked avatars are shown dimmed."""

    child_id: int
    total_stars: int
    streak: int
    avatars: list[AvatarOut]
    # The child's current avatar — the most recently unlocked one.
    active_avatar: AvatarOut | None


# --- Answering ------------------------------------------------------------
class AnswerIn(BaseModel):
    child_id: int
    exercise_id: int
    # Legacy field, kept byte-for-byte for the original "choice" flow: the id
    # of the tapped option, compared against `correct_option_id` server-side
    # (verify.py still posts it). The `choice` validator also accepts the same
    # id nested in `answer`, for callers that use the generic path.
    option_id: str | None = None
    # Generic answer for the pluggable exercise types. Its shape depends on
    # exercise.type and is validated by that type's validator
    # (app/services/exercise_types/): matching sends {"pairings": {...}},
    # sequencing sends {"order": [...]}, tracing sends {"points": [...]}.
    answer: dict | list | None = None
    tries: int = Field(default=1, ge=1)
    session_id: int | None = None


class AnswerRewardsOut(BaseModel):
    """Rewards state after recording an answer. Positive-only: stars never
    decrease and `new_avatar` is set exactly when this answer unlocked one
    (the frontend uses it for a small celebration)."""

    stars: int
    streak: int
    new_avatar: AvatarOut | None = None


class AnswerOut(BaseModel):
    is_correct: bool
    # Encouraging, never punishing. The frontend maps these to sound + art.
    feedback: str  # "correct" | "try_again"
    leveled_up: bool = False
    new_level: int | None = None
    rewards: AnswerRewardsOut | None = None


# --- Speech answers (DL layer) ---------------------------------------------
class SpeechAnswerOut(BaseModel):
    """Response for POST /api/speech-answer. See app/speech/ — `engine`
    reports which transcriber actually ran ("whisper-<size>" or "stub") so
    the frontend/caller never has to guess whether real speech recognition
    happened."""

    transcript: str
    matched_option_id: str | None
    is_correct: bool | None  # None when feedback == "unclear"
    feedback: str  # "correct" | "try_again" | "unclear"
    leveled_up: bool = False
    new_level: int | None = None
    confidence: float  # fuzzy-match ratio (0..1) against the matched option
    engine: str
    rewards: AnswerRewardsOut | None = None


# --- Sessions ---------------------------------------------------------------
class SessionStartOut(BaseModel):
    session_id: int
    child_id: int
    target_exercises: int
    started_at: datetime


class SessionSkillSummary(BaseModel):
    skill_id: int
    skill_key: str
    name_ar: str
    name_en: str
    attempts: int
    accuracy: float


class SessionLevelUpOut(BaseModel):
    skill_id: int
    skill_key: str
    name_ar: str
    name_en: str
    new_level: int


class SessionSummaryOut(BaseModel):
    session_id: int
    child_id: int
    started_at: datetime
    ended_at: datetime | None
    target_exercises: int
    total_attempts: int
    correct_attempts: int
    accuracy: float
    # True once total_attempts has reached target_exercises — the frontend
    # uses this to decide when to show the celebratory summary screen.
    target_reached: bool
    skills: list[SessionSkillSummary]
    level_ups: list[SessionLevelUpOut]


# --- Goals (adult-set targets) ----------------------------------------------
class GoalCreate(BaseModel):
    skill_id: int
    # None = "practice this skill"; a number = "master up to level N".
    target_level: int | None = Field(default=None, ge=1)


class GoalUpdate(BaseModel):
    status: str = Field(pattern="^(active|achieved|archived)$")


class GoalOut(BaseModel):
    id: int
    child_id: int
    skill_id: int
    skill_key: str
    skill_name_ar: str
    skill_name_en: str
    target_level: int | None
    status: str
    created_at: datetime
    achieved_at: datetime | None
    # Read-only convenience so the frontend doesn't need a second call to
    # show progress toward the goal.
    current_level: int
    highest_mastered: int


# --- Progress (adult view) ------------------------------------------------
class SkillProgress(BaseModel):
    skill_id: int
    skill_key: str
    name_ar: str
    name_en: str
    category: str
    current_level: int
    highest_mastered: int
    total_levels: int
    attempts: int
    accuracy: float  # 0..1 over all attempts in this skill


class ChildProgressOut(BaseModel):
    child: ChildOut
    skills: list[SkillProgress]
    total_attempts: int
    overall_accuracy: float


# --- Learning Journey (child view) -----------------------------------------
class JourneyStopOut(BaseModel):
    """One skill rendered as a stop on the child's learning path.

    `status` is derived, never stored: "mastered" when the child has
    finished every level (Mastery.highest_mastered >= total_levels),
    "current" for the single active focus (the skill an adult set an active
    goal on if any, otherwise the first not-yet-mastered stop in journey
    order), and "locked" for everything else — upcoming stops are shown
    dimmed to build anticipation, never as punishment.
    """

    skill_id: int
    skill_key: str
    name_ar: str
    name_en: str
    icon: str
    category: str
    total_levels: int
    current_level: int
    highest_mastered: int
    status: str  # "locked" | "current" | "mastered"
    is_active_goal: bool


class JourneyOut(BaseModel):
    """GET /api/children/{id}/journey — a read-only projection over existing
    Mastery, Goal, Skill and Rewards data; there is no journey table and no
    parallel progress system."""

    child_id: int
    total_stars: int
    stops: list[JourneyStopOut]


# --- Parent view (adult, read-only aggregation) ------------------------------
class ParentSkillRef(BaseModel):
    """A lightweight, bilingual skill reference used by the parent view."""

    skill_id: int
    skill_key: str
    name_ar: str
    name_en: str


class ParentPeriodSummary(BaseModel):
    """Read-only rollup over existing Attempt / Session / LevelUpEvent rows
    for one window ("today" or "this week"). Nothing here is stored and
    nothing is a source of truth — it is derived fresh on every read.

    `stars_earned` is the number of correct answers in the window: the
    rewards layer awards exactly one star per exercise solved correctly, so
    correct attempts are a faithful projection of stars earned. `accuracy` is
    correct / total attempts in the window. `skills_practiced` are the
    distinct skills touched in the window.
    """

    activities_done: int
    accuracy: float  # 0..1 over attempts in the window
    sessions_count: int
    stars_earned: int
    skills_practiced: list[ParentSkillRef]
    level_ups: int


class ParentSummaryOut(BaseModel):
    """GET /api/children/{id}/parent-summary — a pure read-only aggregation
    for the parent dashboard. `today` is the current UTC calendar day;
    `week` is the rolling last N days (config `parent_view_week_days`, default
    7) and therefore includes `today`."""

    child: ChildOut
    today: ParentPeriodSummary
    week: ParentPeriodSummary
    current_streak: int
    total_stars: int


class ParentSuggestionOut(BaseModel):
    """GET /api/children/{id}/suggestions — gentle, rule-based EDUCATIONAL
    TIPS for home activities. Never a diagnosis, never medical or therapeutic
    advice: each tip is an optional idea ("you could try...", "maybe...") and
    `tone` is always "encouraging". The rules are documented in
    app/services/parent_view.py."""

    type: str  # "gentle_practice" | "revisit" | "consistency" | "new_level" | "encouragement"
    skill: ParentSkillRef | None
    text_ar: str
    text_en: str
    tone: str = "encouraging"
