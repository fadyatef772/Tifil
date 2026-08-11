"""HTTP routes.

Thin layer: validate, call the engine or read progress, shape the response.
No pedagogy lives here — that all sits in adaptive_engine.py.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.domain import schemas
from app.domain.models import (
    Attempt,
    Child,
    Exercise,
    Goal,
    LevelUpEvent,
    Mastery,
    Rewards,
    Skill,
    SkillLevel,
)
from app.domain.models import Session as SessionModel
from app.ml import struggle_predictor
from app.ml.intervention import easier_exercise
from app.services import adaptive_engine as engine
from app.services import daily_routine
from app.services import exercise_types
from app.services import goals as goals_service
from app.services import parent_view
from app.services import rewards as rewards_service
from app.speech import match as speech_match
from app.speech import transcriber

router = APIRouter(prefix="/api")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- Children -------------------------------------------------------------
@router.post("/children", response_model=schemas.ChildOut)
def create_child(payload: schemas.ChildCreate, db: Session = Depends(get_db)):
    child = Child(name=payload.name, preferred_language=payload.preferred_language)
    db.add(child)
    db.commit()
    db.refresh(child)
    engine.ensure_masteries(db, child)
    return child


@router.get("/children", response_model=list[schemas.ChildOut])
def list_children(db: Session = Depends(get_db)):
    return list(db.scalars(select(Child).order_by(Child.name)).all())


@router.get("/children/{child_id}", response_model=schemas.ChildOut)
def get_child(child_id: int, db: Session = Depends(get_db)):
    child = db.get(Child, child_id)
    if not child:
        raise HTTPException(404, "Child not found")
    return child


@router.get("/children/{child_id}/rewards", response_model=schemas.RewardsOut)
def get_rewards(child_id: int, db: Session = Depends(get_db)):
    """Stars + streak + the full avatar catalog with per-avatar unlock state.
    Read-only; the answer endpoints below are the only writers."""
    child = db.get(Child, child_id)
    if not child:
        raise HTTPException(404, "Child not found")
    return schemas.RewardsOut(**rewards_service.get(db, child))


@router.get("/children/{child_id}/journey", response_model=schemas.JourneyOut)
def child_journey(child_id: int, db: Session = Depends(get_db)):
    """The child's learning path: every skill as an ordered stop with a
    derived status. A pure READ-ONLY projection over existing data — the
    engine, goals, rewards, ML, speech and exercise-type systems are never
    written or consulted for scoring here.

    Status derivation (no new source of truth):
      * mastered  — Mastery.highest_mastered >= number of skill levels.
      * current   — the single active focus: the skill an adult set an
                    ACTIVE goal on (Goal.status == "active", reusing the
                    existing goals data), if any of those are not yet
                    mastered; otherwise the first non-mastered stop in
                    journey order.
      * locked    — every other non-mastered stop (upcoming, dimmed).
    `ensure_masteries` lazily creates a level-1 Mastery row for any skill a
    brand-new skill was added under an existing child — same idempotent,
    additive helper the progress endpoint already uses; it never changes an
    existing mastery's level."""
    child = db.get(Child, child_id)
    if not child:
        raise HTTPException(404, "Child not found")
    engine.ensure_masteries(db, child)

    skills = db.scalars(select(Skill).order_by(Skill.order)).all()
    active_goal_skills = set(
        db.scalars(
            select(Goal.skill_id).where(
                Goal.skill_id.in_([s.id for s in skills]),
                Goal.child_id == child_id,
                Goal.status == "active",
            )
        ).all()
    )
    reward_row = db.scalar(select(Rewards).where(Rewards.child_id == child_id))

    stops = []
    for skill in skills:
        mastery = next((m for m in child.masteries if m.skill_id == skill.id), None)
        stops.append(
            {
                "skill_id": skill.id,
                "skill_key": skill.key,
                "name_ar": skill.name_ar,
                "name_en": skill.name_en,
                "icon": skill.icon,
                "category": skill.category,
                "total_levels": len(skill.levels),
                "current_level": mastery.current_level if mastery else 1,
                "highest_mastered": mastery.highest_mastered if mastery else 0,
                "is_active_goal": skill.id in active_goal_skills,
            }
        )

    mastered_ids = {
        s["skill_id"] for s in stops if s["highest_mastered"] >= s["total_levels"]
    }
    current_id = None
    # An adult-set active goal wins the focus if its skill isn't mastered yet;
    # otherwise the first non-mastered stop in journey order is "current".
    for s in stops:
        if s["skill_id"] not in mastered_ids and s["is_active_goal"]:
            current_id = s["skill_id"]
            break
    if current_id is None:
        for s in stops:
            if s["skill_id"] not in mastered_ids:
                current_id = s["skill_id"]
                break

    stop_outs = []
    for s in stops:
        if s["skill_id"] in mastered_ids:
            status = "mastered"
        elif s["skill_id"] == current_id:
            status = "current"
        else:
            status = "locked"
        stop_outs.append(schemas.JourneyStopOut(**s, status=status))

    return schemas.JourneyOut(
        child_id=child_id,
        total_stars=reward_row.total_stars if reward_row else 0,
        stops=stop_outs,
    )


# --- The learning loop ----------------------------------------------------
def _exercise_out(db: Session, ex: Exercise) -> schemas.ExerciseOut:
    level = ex.skill_level
    skill = level.skill
    # The type's serializer builds the child-facing payload with every
    # answer-bearing key stripped (see app/services/exercise_types/).
    payload = exercise_types.serialize_for_child(ex)
    options = payload.get("options", []) if isinstance(payload, dict) else []
    return schemas.ExerciseOut(
        id=ex.id,
        skill_id=skill.id,
        skill_key=skill.key,
        skill_name_ar=skill.name_ar,
        skill_name_en=skill.name_en,
        category=skill.category,
        level=level.level,
        type=ex.type,
        prompt_ar=ex.prompt_ar,
        prompt_en=ex.prompt_en,
        options=options,
        payload=payload,
    )


def _struggle_signal_for(db: Session, child_id: int, ex: Exercise) -> tuple[Exercise, schemas.StruggleSignalOut | None]:
    """Ask the ML struggle predictor about the exercise the rule-based engine
    just chose, and possibly swap in an easier rep for this one turn. Never
    changes level/mastery, and any failure here is swallowed -- the engine's
    original `ex` is always a safe fallback (see app/ml/struggle_predictor.py)."""
    try:
        skill_id = ex.skill_level.skill_id
        level = ex.skill_level.level
        prediction = struggle_predictor.predict_for_child_skill(
            db, child_id, skill_id, level
        )
        if not prediction.available:
            return ex, schemas.StruggleSignalOut(
                is_struggling=False, confidence=0.0, model_available=False
            )

        intervention = None
        if prediction.is_struggling:
            easier = easier_exercise(db, child_id, skill_id, level)
            if easier is not None:
                ex = easier
                intervention = "eased_difficulty"
            else:
                intervention = "hint_suggested"

        return ex, schemas.StruggleSignalOut(
            is_struggling=prediction.is_struggling,
            confidence=prediction.confidence,
            model_available=True,
            intervention=intervention,
        )
    except Exception:
        return ex, None


@router.get(
    "/children/{child_id}/next-exercise",
    response_model=schemas.NextExerciseOut,
)
def next_exercise(child_id: int, db: Session = Depends(get_db)):
    child = db.get(Child, child_id)
    if not child:
        raise HTTPException(404, "Child not found")
    ex = engine.select_next_exercise(db, child)
    if ex is None:
        return schemas.NextExerciseOut(exercise=None, all_caught_up=True)

    ex, struggle_signal = _struggle_signal_for(db, child_id, ex)
    return schemas.NextExerciseOut(
        exercise=_exercise_out(db, ex), struggle_signal=struggle_signal
    )


@router.get(
    "/children/{child_id}/skills/{skill_id}/struggle-prediction",
    response_model=schemas.StruggleSignalOut,
)
def struggle_prediction(child_id: int, skill_id: int, db: Session = Depends(get_db)):
    """Direct inspection of the ML signal for a (child, skill), independent
    of exercise serving -- e.g. for the adult dashboard. Never applies an
    intervention itself, so `intervention` is always null here."""
    child = db.get(Child, child_id)
    if not child:
        raise HTTPException(404, "Child not found")
    mastery = next((m for m in child.masteries if m.skill_id == skill_id), None)
    current_level = mastery.current_level if mastery else 1
    prediction = struggle_predictor.predict_for_child_skill(
        db, child_id, skill_id, current_level
    )
    return schemas.StruggleSignalOut(
        is_struggling=prediction.is_struggling,
        confidence=prediction.confidence,
        model_available=prediction.available,
        intervention=None,
    )


@router.post("/answers", response_model=schemas.AnswerOut)
def submit_answer(payload: schemas.AnswerIn, db: Session = Depends(get_db)):
    child = db.get(Child, payload.child_id)
    if not child:
        raise HTTPException(404, "Child not found")
    ex = db.get(Exercise, payload.exercise_id)
    if not ex:
        raise HTTPException(404, "Exercise not found")

    # Correctness is decided by the exercise type's own validator
    # (app/services/exercise_types/): the legacy `option_id` path still works
    # for choice; the newer types read the structured `answer` payload. The
    # engine / goals / rewards / ML layers below only consume `is_correct`.
    is_correct = exercise_types.validate_answer(ex, payload)
    result = engine.record_answer(
        db,
        child,
        ex,
        is_correct=is_correct,
        tries=payload.tries,
        session_id=payload.session_id,
    )
    goals_service.check_goal_achievement(db, child, ex.skill_level.skill_id)
    reward = rewards_service.record(db, child, is_correct=is_correct)
    return schemas.AnswerOut(**result, rewards=reward)


# --- Speech answers (DL layer) --------------------------------------------
@router.post("/speech-answer", response_model=schemas.SpeechAnswerOut)
async def speech_answer(
    child_id: int = Form(...),
    exercise_id: int = Form(...),
    tries: int = Form(default=1, ge=1),
    session_id: int | None = Form(default=None),
    lang: str = Form(default="ar"),
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """A child speaks their answer instead of tapping. Transcribes with
    Whisper (or the stub -- see the `engine` field in the response, which
    always says which one actually ran), then fuzzy-matches the transcript
    against this exercise's option labels. A confident match is scored and
    recorded exactly like a tapped answer via the same rule-based engine; an
    unclear transcript is reported as such and is NOT recorded as an
    attempt, so an unintelligible recording can never count against the
    child (consistent with the app's no-punishment design)."""
    if lang not in ("ar", "en"):
        raise HTTPException(400, "lang must be 'ar' or 'en'")

    child = db.get(Child, child_id)
    if not child:
        raise HTTPException(404, "Child not found")
    ex = db.get(Exercise, exercise_id)
    if not ex:
        raise HTTPException(404, "Exercise not found")
    if ex.type != "choice":
        # Speech matching works against option labels; the newer types have
        # no spoken single answer, so the mic is only offered for choice.
        # The frontend gates the 🎤 button on the same check.
        raise HTTPException(
            400,
            "Speech answers are only supported for 'choice' exercises; "
            f"this exercise is type '{ex.type}'.",
        )

    audio_bytes = await audio.read()
    transcription = transcriber.transcribe(audio_bytes, language=lang)
    match = speech_match.best_option_match(transcription.text, ex.options, lang)

    if match.option_id is None or match.score < settings.speech_match_threshold:
        return schemas.SpeechAnswerOut(
            transcript=transcription.text,
            matched_option_id=None,
            is_correct=None,
            feedback="unclear",
            confidence=match.score,
            engine=transcription.engine,
        )

    is_correct = match.option_id == ex.correct_option_id
    result = engine.record_answer(
        db, child, ex, is_correct=is_correct, tries=tries, session_id=session_id
    )
    goals_service.check_goal_achievement(db, child, ex.skill_level.skill_id)
    reward = rewards_service.record(db, child, is_correct=is_correct)
    return schemas.SpeechAnswerOut(
        transcript=transcription.text,
        matched_option_id=match.option_id,
        is_correct=is_correct,
        feedback=result["feedback"],
        leveled_up=result["leveled_up"],
        new_level=result["new_level"],
        confidence=match.score,
        engine=transcription.engine,
        rewards=reward,
    )


# --- Sessions ---------------------------------------------------------------
def _build_session_summary(db: Session, session: SessionModel) -> schemas.SessionSummaryOut:
    attempts = list(
        db.scalars(select(Attempt).where(Attempt.session_id == session.id)).all()
    )
    total = len(attempts)
    correct = sum(1 for a in attempts if a.is_correct)

    by_skill: dict[int, list[Attempt]] = {}
    for a in attempts:
        by_skill.setdefault(a.skill_id, []).append(a)

    skills_out = []
    for skill_id, skill_attempts in by_skill.items():
        skill = db.get(Skill, skill_id)
        if skill is None:
            continue
        s_correct = sum(1 for a in skill_attempts if a.is_correct)
        skills_out.append(
            schemas.SessionSkillSummary(
                skill_id=skill_id,
                skill_key=skill.key,
                name_ar=skill.name_ar,
                name_en=skill.name_en,
                attempts=len(skill_attempts),
                accuracy=(s_correct / len(skill_attempts)) if skill_attempts else 0.0,
            )
        )

    level_up_rows = db.scalars(
        select(LevelUpEvent).where(LevelUpEvent.session_id == session.id)
    ).all()
    level_ups_out = []
    for ev in level_up_rows:
        skill = db.get(Skill, ev.skill_id)
        if skill is None:
            continue
        level_ups_out.append(
            schemas.SessionLevelUpOut(
                skill_id=ev.skill_id,
                skill_key=skill.key,
                name_ar=skill.name_ar,
                name_en=skill.name_en,
                new_level=ev.new_level,
            )
        )

    return schemas.SessionSummaryOut(
        session_id=session.id,
        child_id=session.child_id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        target_exercises=settings.session_exercise_target,
        total_attempts=total,
        correct_attempts=correct,
        accuracy=(correct / total) if total else 0.0,
        target_reached=total >= settings.session_exercise_target,
        skills=skills_out,
        level_ups=level_ups_out,
    )


@router.post(
    "/children/{child_id}/sessions/start", response_model=schemas.SessionStartOut
)
def start_session(child_id: int, db: Session = Depends(get_db)):
    child = db.get(Child, child_id)
    if not child:
        raise HTTPException(404, "Child not found")
    session = SessionModel(child_id=child_id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return schemas.SessionStartOut(
        session_id=session.id,
        child_id=child_id,
        target_exercises=settings.session_exercise_target,
        started_at=session.started_at,
    )


@router.post("/sessions/{session_id}/end", response_model=schemas.SessionSummaryOut)
def end_session(session_id: int, db: Session = Depends(get_db)):
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session.ended_at is None:
        session.ended_at = _now()
        db.commit()
        db.refresh(session)
    return _build_session_summary(db, session)


@router.get("/sessions/{session_id}/summary", response_model=schemas.SessionSummaryOut)
def session_summary(session_id: int, db: Session = Depends(get_db)):
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return _build_session_summary(db, session)


@router.get(
    "/children/{child_id}/sessions", response_model=list[schemas.SessionSummaryOut]
)
def list_sessions(child_id: int, limit: int = 5, db: Session = Depends(get_db)):
    """Recent session summaries, most recent first — powers the adult
    dashboard's "recent sessions" section."""
    child = db.get(Child, child_id)
    if not child:
        raise HTTPException(404, "Child not found")
    sessions = db.scalars(
        select(SessionModel)
        .where(SessionModel.child_id == child_id)
        .order_by(SessionModel.started_at.desc())
        .limit(limit)
    ).all()
    return [_build_session_summary(db, s) for s in sessions]


# --- Goals (adult-set targets) ----------------------------------------------
def _goal_out(goal: Goal, skill: Skill, mastery: Mastery | None) -> schemas.GoalOut:
    return schemas.GoalOut(
        id=goal.id,
        child_id=goal.child_id,
        skill_id=goal.skill_id,
        skill_key=skill.key,
        skill_name_ar=skill.name_ar,
        skill_name_en=skill.name_en,
        target_level=goal.target_level,
        status=goal.status,
        created_at=goal.created_at,
        achieved_at=goal.achieved_at,
        current_level=mastery.current_level if mastery else 1,
        highest_mastered=mastery.highest_mastered if mastery else 0,
    )


@router.post("/children/{child_id}/goals", response_model=schemas.GoalOut)
def create_goal(
    child_id: int, payload: schemas.GoalCreate, db: Session = Depends(get_db)
):
    child = db.get(Child, child_id)
    if not child:
        raise HTTPException(404, "Child not found")
    skill = db.get(Skill, payload.skill_id)
    if not skill:
        raise HTTPException(404, "Skill not found")

    goal = Goal(
        child_id=child_id, skill_id=payload.skill_id, target_level=payload.target_level
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)

    engine.ensure_masteries(db, child)
    mastery = next((m for m in child.masteries if m.skill_id == skill.id), None)
    return _goal_out(goal, skill, mastery)


@router.get("/children/{child_id}/goals", response_model=list[schemas.GoalOut])
def list_goals(child_id: int, db: Session = Depends(get_db)):
    child = db.get(Child, child_id)
    if not child:
        raise HTTPException(404, "Child not found")
    goals = db.scalars(
        select(Goal)
        .where(Goal.child_id == child_id)
        .order_by(Goal.created_at.desc())
    ).all()
    out = []
    for g in goals:
        skill = db.get(Skill, g.skill_id)
        if skill is None:
            continue
        mastery = next((m for m in child.masteries if m.skill_id == g.skill_id), None)
        out.append(_goal_out(g, skill, mastery))
    return out


@router.patch("/goals/{goal_id}", response_model=schemas.GoalOut)
def update_goal(goal_id: int, payload: schemas.GoalUpdate, db: Session = Depends(get_db)):
    goal = db.get(Goal, goal_id)
    if not goal:
        raise HTTPException(404, "Goal not found")
    goal.status = payload.status
    if payload.status == "achieved" and goal.achieved_at is None:
        goal.achieved_at = _now()
    db.commit()
    db.refresh(goal)

    skill = db.get(Skill, goal.skill_id)
    child = db.get(Child, goal.child_id)
    mastery = (
        next((m for m in child.masteries if m.skill_id == goal.skill_id), None)
        if child
        else None
    )
    return _goal_out(goal, skill, mastery)


# --- Progress (adult dashboard) ------------------------------------------
@router.get(
    "/children/{child_id}/progress",
    response_model=schemas.ChildProgressOut,
)
def child_progress(child_id: int, db: Session = Depends(get_db)):
    child = db.get(Child, child_id)
    if not child:
        raise HTTPException(404, "Child not found")
    engine.ensure_masteries(db, child)

    skills = db.scalars(select(Skill).order_by(Skill.order)).all()
    out_skills: list[schemas.SkillProgress] = []
    total_attempts = 0
    total_correct = 0

    for skill in skills:
        mastery = next(
            (m for m in child.masteries if m.skill_id == skill.id), None
        )
        total_levels = (
            db.scalar(
                select(func.count(SkillLevel.id)).where(
                    SkillLevel.skill_id == skill.id
                )
            )
            or 0
        )
        attempts = (
            db.scalar(
                select(func.count(Attempt.id)).where(
                    Attempt.child_id == child.id, Attempt.skill_id == skill.id
                )
            )
            or 0
        )
        correct = (
            db.scalar(
                select(func.count(Attempt.id)).where(
                    Attempt.child_id == child.id,
                    Attempt.skill_id == skill.id,
                    Attempt.is_correct.is_(True),
                )
            )
            or 0
        )
        total_attempts += attempts
        total_correct += correct
        out_skills.append(
            schemas.SkillProgress(
                skill_id=skill.id,
                skill_key=skill.key,
                name_ar=skill.name_ar,
                name_en=skill.name_en,
                category=skill.category,
                current_level=mastery.current_level if mastery else 1,
                highest_mastered=mastery.highest_mastered if mastery else 0,
                total_levels=total_levels,
                attempts=attempts,
                accuracy=(correct / attempts) if attempts else 0.0,
            )
        )

    return schemas.ChildProgressOut(
        child=child,
        skills=out_skills,
        total_attempts=total_attempts,
        overall_accuracy=(total_correct / total_attempts)
        if total_attempts
        else 0.0,
    )


# --- Parent view (adult, read-only aggregation) ----------------------------
@router.get(
    "/children/{child_id}/daily",
    response_model=schemas.DailyRoutineOut,
)
def child_daily_routine(child_id: int, db: Session = Depends(get_db)):
    """The child's daily routine — daily streak, today's plan, and a recent
    activity calendar. A PURE READ-ONLY projection over the child's existing
    Attempt rows (see app/services/daily_routine.py): it never writes,
    never calls the engine, and never touches the rewards in-session streak.

    The streak is gentle by construction: a missed day resets it to 0, and
    the UI only ever frames a fresh start positively — there is no "play or
    lose your streak" mechanic anywhere."""
    child = db.get(Child, child_id)
    if not child:
        raise HTTPException(404, "Child not found")
    return schemas.DailyRoutineOut(**daily_routine.daily(db, child))


@router.get(
    "/children/{child_id}/parent-summary",
    response_model=schemas.ParentSummaryOut,
)
def child_parent_summary(child_id: int, db: Session = Depends(get_db)):
    """Today + this-week rollup for the parent dashboard. A PURE READ-ONLY
    projection over existing Attempt / Session / LevelUpEvent / Rewards rows —
    it never writes, never consults the engine, rewards, ML or speech layers,
    and adds no new source of truth (see app/services/parent_view.py)."""
    child = db.get(Child, child_id)
    if not child:
        raise HTTPException(404, "Child not found")
    return schemas.ParentSummaryOut(**parent_view.summary(db, child))


@router.get(
    "/children/{child_id}/suggestions",
    response_model=list[schemas.ParentSuggestionOut],
)
def child_suggestions(child_id: int, db: Session = Depends(get_db)):
    """Gentle, rule-based EDUCATIONAL TIPS for home activities. Read-only,
    optional ideas only — never a diagnosis, never medical or therapeutic
    advice (rules and wording live in app/services/parent_view.py)."""
    child = db.get(Child, child_id)
    if not child:
        raise HTTPException(404, "Child not found")
    return [schemas.ParentSuggestionOut(**s) for s in parent_view.suggestions(db, child)]
