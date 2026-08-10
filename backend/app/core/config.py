"""Central configuration.

Every tunable of the adaptive engine lives here so a therapist-facing
settings screen can later expose them without touching logic. The defaults
below are deliberately conservative: promotion is slow, demotion is gentle,
and a child is never dropped below the first level of a skill.
"""

from pydantic_settings import BaseSettings


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

    class Config:
        env_prefix = "TIFL_"


settings = Settings()
