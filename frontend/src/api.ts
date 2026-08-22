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
  Parent,
  ParentSuggestion,
  ParentSummary,
  Rewards,
  SessionStart,
  SessionSummary,
  SpeechAnswerResult,
  TokenOut,
} from "./types";

const BASE = "/api";

// ── Error class that preserves status for callers ────────────────────────
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number | null, // null = network / proxy failure
  ) {
    super(message);
    this.name = "ApiError";
  }

  get serverUnreachable() {
    return this.status === null || (this.status !== null && this.status >= 500);
  }
}

// ── Auth state ────────────────────────────────────────────────────────────
let _authToken: string | null = null;

export function setAuthToken(token: string | null) {
  _authToken = token;
}

export function getAuthToken(): string | null {
  return _authToken;
}

function authHeaders(): Record<string, string> {
  return _authToken ? { Authorization: `Bearer ${_authToken}` } : {};
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new ApiError(`${res.status} ${res.statusText}`, res.status);
  return res.json() as Promise<T>;
}

// Wraps fetch + json so network errors (ECONNREFUSED → proxy 500, CORS, DNS)
// become ApiError with status=null instead of an opaque TypeError.
async function apiFetch<T>(url: string, init?: RequestInit): Promise<T> {
  try {
    const res = await fetch(url, init);
    return await json<T>(res);
  } catch (err) {
    if (err instanceof ApiError) throw err;
    // TypeError: Failed to fetch (network/proxy down, CORS block, etc.)
    throw new ApiError(
      err instanceof Error ? err.message : "Network error",
      null,
    );
  }
}

export const api = {
  // --- Auth ----------------------------------------------------------------
  signup: (email: string, password: string, name: string) =>
    apiFetch<TokenOut>(`${BASE}/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, name }),
    }),

  login: (email: string, password: string) =>
    apiFetch<TokenOut>(`${BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }),

  me: () =>
    fetch(`${BASE}/auth/me`, { headers: authHeaders() }).then(json<Parent>),

  // --- Children ------------------------------------------------------------
  listChildren: () =>
    fetch(`${BASE}/children`, { headers: authHeaders() }).then(json<Child[]>),

  createChild: (name: string, preferred_language: Lang) =>
    fetch(`${BASE}/children`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ name, preferred_language }),
    }).then(json<Child>),

  nextExercise: (childId: number) =>
    fetch(`${BASE}/children/${childId}/next-exercise`, {
      headers: authHeaders(),
    }).then(json<NextExercise>),

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
      headers: { "Content-Type": "application/json", ...authHeaders() },
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
    fetch(`${BASE}/children/${childId}/progress`, {
      headers: authHeaders(),
    }).then(json<ChildProgress>),

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
      headers: authHeaders(),
      body: form,
    }).then(json<SpeechAnswerResult>);
  },

  // --- Sessions ---------------------------------------------------------
  startSession: (childId: number) =>
    fetch(`${BASE}/children/${childId}/sessions/start`, {
      method: "POST",
      headers: authHeaders(),
    }).then(json<SessionStart>),

  endSession: (sessionId: number) =>
    fetch(`${BASE}/sessions/${sessionId}/end`, {
      method: "POST",
      headers: authHeaders(),
    }).then(json<SessionSummary>),

  recentSessions: (childId: number, limit = 5) =>
    fetch(`${BASE}/children/${childId}/sessions?limit=${limit}`, {
      headers: authHeaders(),
    }).then(json<SessionSummary[]>),

  // --- Goals --------------------------------------------------------------
  listGoals: (childId: number) =>
    fetch(`${BASE}/children/${childId}/goals`, {
      headers: authHeaders(),
    }).then(json<Goal[]>),

  createGoal: (childId: number, skillId: number, targetLevel: number | null) =>
    fetch(`${BASE}/children/${childId}/goals`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ skill_id: skillId, target_level: targetLevel }),
    }).then(json<Goal>),

  updateGoal: (goalId: number, status: GoalStatus) =>
    fetch(`${BASE}/goals/${goalId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ status }),
    }).then(json<Goal>),

  // --- Rewards ------------------------------------------------------------
  rewards: (childId: number) =>
    fetch(`${BASE}/children/${childId}/rewards`, {
      headers: authHeaders(),
    }).then(json<Rewards>),

  // --- Learning Journey (child view) ---------------------------------------
  journey: (childId: number) =>
    fetch(`${BASE}/children/${childId}/journey`, {
      headers: authHeaders(),
    }).then(json<Journey>),

  // --- Daily Routine (child, read-only projection) ---------------------------
  daily: (childId: number) =>
    fetch(`${BASE}/children/${childId}/daily`, {
      headers: authHeaders(),
    }).then(json<DailyRoutine>),

  // --- Parent View (adult, read-only aggregation) ----------------------------
  parentSummary: (childId: number) =>
    fetch(`${BASE}/children/${childId}/parent-summary`, {
      headers: authHeaders(),
    }).then(json<ParentSummary>),

  suggestions: (childId: number) =>
    fetch(`${BASE}/children/${childId}/suggestions`, {
      headers: authHeaders(),
    }).then(json<ParentSuggestion[]>),
};
