import type {
  AnswerResult,
  Child,
  ChildProgress,
  DailyRoutine,
  Goal,
  GoalStatus,
  Journey,
  Lang,
  NextExercise,
  ParentSuggestion,
  ParentSummary,
  Rewards,
  SessionStart,
  SessionSummary,
  SpeechAnswerResult,
} from "./types";

const BASE = "/api";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  listChildren: () => fetch(`${BASE}/children`).then(json<Child[]>),

  createChild: (name: string, preferred_language: Lang) =>
    fetch(`${BASE}/children`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, preferred_language }),
    }).then(json<Child>),

  nextExercise: (childId: number) =>
    fetch(`${BASE}/children/${childId}/next-exercise`).then(json<NextExercise>),

  answer: (
    childId: number,
    exerciseId: number,
    optionId: string | null,
    answer: unknown,
    tries: number,
    sessionId?: number | null,
  ) =>
    fetch(`${BASE}/answers`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        child_id: childId,
        exercise_id: exerciseId,
        tries,
        session_id: sessionId ?? null,
        ...(optionId != null ? { option_id: optionId } : {}),
        ...(answer != null ? { answer } : {}),
      }),
    }).then(json<AnswerResult>),

  progress: (childId: number) =>
    fetch(`${BASE}/children/${childId}/progress`).then(json<ChildProgress>),

  // Speech-answer (optional, DL layer): the child speaks instead of tapping.
  speechAnswer: (
    childId: number,
    exerciseId: number,
    tries: number,
    lang: Lang,
    audio: Blob,
    sessionId?: number | null,
  ) => {
    const form = new FormData();
    form.append("child_id", String(childId));
    form.append("exercise_id", String(exerciseId));
    form.append("tries", String(tries));
    form.append("lang", lang);
    if (sessionId != null) form.append("session_id", String(sessionId));
    form.append("audio", audio, "answer.webm");
    return fetch(`${BASE}/speech-answer`, {
      method: "POST",
      body: form,
    }).then(json<SpeechAnswerResult>);
  },

  // --- Sessions ---------------------------------------------------------
  startSession: (childId: number) =>
    fetch(`${BASE}/children/${childId}/sessions/start`, { method: "POST" }).then(
      json<SessionStart>,
    ),

  endSession: (sessionId: number) =>
    fetch(`${BASE}/sessions/${sessionId}/end`, { method: "POST" }).then(
      json<SessionSummary>,
    ),

  recentSessions: (childId: number, limit = 5) =>
    fetch(`${BASE}/children/${childId}/sessions?limit=${limit}`).then(
      json<SessionSummary[]>,
    ),

  // --- Goals --------------------------------------------------------------
  listGoals: (childId: number) =>
    fetch(`${BASE}/children/${childId}/goals`).then(json<Goal[]>),

  createGoal: (childId: number, skillId: number, targetLevel: number | null) =>
    fetch(`${BASE}/children/${childId}/goals`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ skill_id: skillId, target_level: targetLevel }),
    }).then(json<Goal>),

  updateGoal: (goalId: number, status: GoalStatus) =>
    fetch(`${BASE}/goals/${goalId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    }).then(json<Goal>),

  // --- Rewards ------------------------------------------------------------
  rewards: (childId: number) =>
    fetch(`${BASE}/children/${childId}/rewards`).then(json<Rewards>),

  // --- Learning Journey (child view) ---------------------------------------
  journey: (childId: number) =>
    fetch(`${BASE}/children/${childId}/journey`).then(json<Journey>),

  // --- Daily Routine (child, read-only projection) ---------------------------
  daily: (childId: number) =>
    fetch(`${BASE}/children/${childId}/daily`).then(json<DailyRoutine>),

  // --- Parent View (adult, read-only aggregation) ----------------------------
  parentSummary: (childId: number) =>
    fetch(`${BASE}/children/${childId}/parent-summary`).then(json<ParentSummary>),

  suggestions: (childId: number) =>
    fetch(`${BASE}/children/${childId}/suggestions`).then(json<ParentSuggestion[]>),
};
