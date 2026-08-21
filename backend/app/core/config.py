"""Central configuration.

Every tunable of the adaptive engine lives here so a therapist-facing
settings screen can later expose them without touching logic. The defaults
below are deliberately conservative: promotion is slow, demotion is gentle,
and a child is never dropped below the first level of a skill.
"""

import os

from pydantic import model_validator
from pydantic_settings import BaseSettings

# The old hardcoded default — REJECTED at startup to prevent token forgery.
_OLD_SECRET_DEFAULT = "dev-only-secret-change-me-in-production"


class Settings(BaseSettings):
    app_name: str = "Tifl - Adaptive Learning"

    # SQLite for zero-config local runs. Swap for a Supabase/Postgres URL in
    # production, e.g. postgresql+psycopg://user:pass@host:5432/db
    database_url: str = "sqlite:///./tifl.db"

    # CORS origins allowed to call the API (the Vite dev server).
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # --- Adaptive engine tunables -----------------------------------------
    # A level is considered mastered when the child answers at least
    # MASTERY_CORRECT of the last MASTERY_WINDOW attempts at that level.
    mastery_window: int = 5
    mastery_correct: int = 4

    # A level is considered too hard (gentle demotion) when the child answers
    # at most STRUGGLE_CORRECT of the last STRUGGLE_WINDOW attempts.
    struggle_window: int = 5
    struggle_correct: int = 1

    # --- Struggle predictor (ML layer) tunables ----------------------------
    # Minimum P(struggling) before the serving layer intervenes (easier rep
    # or hint flag). See app/ml/struggle_predictor.py.
    struggle_confidence_threshold: float = 0.75

    # --- Speech answers (DL layer) tunables --------------------------------
    # Minimum fuzzy-match ratio (0..1) before a transcript is accepted as
    # matching an option; below this the endpoint reports feedback="unclear"
    # rather than guessing. See app/speech/match.py.
    speech_match_threshold: float = 0.55

    # --- Sessions -----------------------------------------------------------
    # Small on purpose: a short, patient session matches a young child's
    # attention span better than an open-ended one.
    session_exercise_target: int = 8

    # --- Goals (adult-set targets) ------------------------------------------
    # How often select_next_exercise prefers an active goal's skill over the
    # normal least-recently-touched rotation — a *weighting*, not a hard
    # restriction, so the child still sees other skills. See
    # adaptive_engine.select_next_exercise.
    goal_bias_probability: float = 0.6
    # Correct attempts (since the goal was created) needed to mark a
    # level-less ("just practice this skill") goal as achieved. Goals with a
    # target_level instead use Mastery.highest_mastered — see
    # app/services/goals.py.
    goal_practice_attempts_target: int = 15

    # --- Rewards (positive reinforcement only) ------------------------------
    # A new avatar unlocks every N stars accumulated (the first avatar is
    # free at 0 stars so a new child always has a colourful friend). See
    # app/services/rewards.py for the catalog and rules.
    rewards_avatar_star_step: int = 10

    # --- Tracing (fine-motor practice) tunables -----------------------------
    # Lenient completion heuristic, deliberately NOT handwriting recognition
    # (see app/services/exercise_types/tracing.py): a traced path counts as
    # correct when at least TRACING_COVERAGE_THRESHOLD of the guide path's
    # sample points lie within TRACING_PROXIMITY_RADIUS (in the shared 0..100
    # coordinate space) of some traced point. A near-empty trace is ignored.
    tracing_coverage_threshold: float = 0.6
    tracing_proximity_radius: float = 18.0
    tracing_min_points: int = 5
    # Traces are downsampled to at most this many points before scoring.
    tracing_max_points: int = 400

    # --- Parent view (adult, read-only aggregation) --------------------------
    # Tunables for the gentle, rule-based EDUCATIONAL TIPS in
    # app/services/parent_view.py. These are optional home-activity ideas, not
    # medical or therapeutic advice — the module never diagnoses anything.
    # "This week" window (in days) used by the summary rollups and tips.
    parent_view_week_days: int = 7
    # "gentle_practice" tip: a skill with at least this many attempts in the
    # window and at most this accuracy (0..1) earns a "you could try more
    # [skill] activities" suggestion — never a problem label.
    gentle_practice_min_attempts: int = 3
    gentle_practice_max_accuracy: float = 0.5
    # "revisit" tip: a skill last practiced more than this many days ago gets
    # a gentle "maybe revisit it" idea.
    revisit_min_days: int = 5
    # "consistency" tip: a current streak at least this long earns a
    # "keep the daily routine going" compliment.
    consistency_min_streak: int = 5
    # Never return more suggestions than this.
    max_suggestions: int = 4

    # --- Auth (parent accounts) ---------------------------------------------
    # HMAC signing key for bearer tokens.  REQUIRED — set via TIFL_SECRET_KEY
    # environment variable.  The app will not start without it.
    # Generate with:  python3 -c "import secrets; print(secrets.token_urlsafe(32))"
    secret_key: str
    # Bearer token lifetime in days.
    session_expiry_days: int = 30

    @model_validator(mode="after")
    def _reject_insecure_secret_key(self) -> "Settings":
        if not self.secret_key or self.secret_key.strip() == "":
            raise ValueError(
                "TIFL_SECRET_KEY is not set.  "
                "The app requires a secret key to sign bearer tokens.  "
                "Generate one with:  "
                'python3 -c "import secrets; print(secrets.token_urlsafe(32))"  '
                "and set it:  export TIFL_SECRET_KEY=<your-generated-key>"
            )
        if self.secret_key == _OLD_SECRET_DEFAULT:
            raise ValueError(
                "TIFL_SECRET_KEY is still the insecure dev default.  "
                "Anyone who reads the source code can forge tokens.  "
                "Generate a real key with:  "
                'python3 -c "import secrets; print(secrets.token_urlsafe(32))"  '
                "and set it:  export TIFL_SECRET_KEY=<your-generated-key>"
            )
        return self

    class Config:
        env_prefix = "TIFL_"


settings = Settings()
