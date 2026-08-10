export type Lang = "ar" | "en";

export interface Child {
  id: number;
  name: string;
  preferred_language: Lang;
  created_at: string;
}

export interface Option {
  id: string;
  label_ar: string;
  label_en: string;
  visual: string; // emoji, #hex color, or icon name
}

export interface Exercise {
  id: number;
  skill_id: number;
  skill_key: string;
  skill_name_ar: string;
  skill_name_en: string;
  category: "cognitive" | "daily_life";
  level: number;
  type: string;
  prompt_ar: string;
  prompt_en: string;
  options: Option[];
  // Type-specific child-facing data (answer keys stripped server-side):
  //   choice      -> { options: Option[] }
  //   matching    -> { pairs: [{ id, left: Option, right: Option }] }
  //   sequencing  -> { items: [{ id, label_ar, label_en, visual }] }
  //   tracing     -> { glyph, visual, guide: [{x,y}] }   (0..100 space)
  payload: Record<string, unknown>;
}

export interface NextExercise {
  exercise: Exercise | null;
  all_caught_up: boolean;
}

export interface AnswerResult {
  is_correct: boolean;
  feedback: "correct" | "try_again";
  leveled_up: boolean;
  new_level: number | null;
  rewards?: AnswerRewards;
}

// Response from POST /api/speech-answer (Deep Learning layer — Whisper).
// `engine` is always honest about what actually ran: "whisper-<size>" for a
// real transcription, or "stub" if no model could be loaded in this
// environment (see backend/app/speech/transcriber.py).
export interface SpeechAnswerResult {
  transcript: string;
  matched_option_id: string | null;
  is_correct: boolean | null; // null when feedback is "unclear"
  feedback: "correct" | "try_again" | "unclear";
  leveled_up: boolean;
  new_level: number | null;
  confidence: number;
  engine: string;
  rewards?: AnswerRewards;
}

export interface SkillProgress {
  skill_id: number;
  skill_key: string;
  name_ar: string;
  name_en: string;
  category: "cognitive" | "daily_life";
  current_level: number;
  highest_mastered: number;
  total_levels: number;
  attempts: number;
  accuracy: number;
}

export interface ChildProgress {
  child: Child;
  skills: SkillProgress[];
  total_attempts: number;
  overall_accuracy: number;
}

// --- Sessions ---------------------------------------------------------------
export interface SessionStart {
  session_id: number;
  child_id: number;
  target_exercises: number;
  started_at: string;
}

export interface SessionSkillSummary {
  skill_id: number;
  skill_key: string;
  name_ar: string;
  name_en: string;
  attempts: number;
  accuracy: number;
}

export interface SessionLevelUp {
  skill_id: number;
  skill_key: string;
  name_ar: string;
  name_en: string;
  new_level: number;
}

export interface SessionSummary {
  session_id: number;
  child_id: number;
  started_at: string;
  ended_at: string | null;
  target_exercises: number;
  total_attempts: number;
  correct_attempts: number;
  accuracy: number;
  target_reached: boolean;
  skills: SessionSkillSummary[];
  level_ups: SessionLevelUp[];
}

// --- Goals (adult-set targets) -----------------------------------------------
export type GoalStatus = "active" | "achieved" | "archived";

export interface Goal {
  id: number;
  child_id: number;
  skill_id: number;
  skill_key: string;
  skill_name_ar: string;
  skill_name_en: string;
  target_level: number | null;
  status: GoalStatus;
  created_at: string;
  achieved_at: string | null;
  current_level: number;
  highest_mastered: number;
}

// --- Rewards (positive reinforcement only) ------------------------------------
export interface Avatar {
  id: string;
  emoji: string;
  stars: number; // stars needed to unlock (0 = free starter avatar)
  unlocked: boolean;
}

export interface Rewards {
  child_id: number;
  total_stars: number;
  streak: number;
  avatars: Avatar[];
  active_avatar: Avatar | null;
}

export interface AnswerRewards {
  stars: number;
  streak: number;
  new_avatar: Avatar | null; // set exactly when this answer unlocked one
}

// --- Learning Journey (child view) ------------------------------------------
export type JourneyStopStatus = "locked" | "current" | "mastered";

export interface JourneyStop {
  skill_id: number;
  skill_key: string;
  name_ar: string;
  name_en: string;
  icon: string;
  category: string;
  total_levels: number;
  current_level: number;
  highest_mastered: number;
  status: JourneyStopStatus;
  is_active_goal: boolean;
}

export interface Journey {
  child_id: number;
  total_stars: number;
  stops: JourneyStop[];
}

// --- Parent View (adult, read-only aggregation) ------------------------------
export interface ParentSkillRef {
  skill_id: number;
  skill_key: string;
  name_ar: string;
  name_en: string;
}

export interface ParentPeriodSummary {
  activities_done: number;
  accuracy: number;
  sessions_count: number;
  stars_earned: number;
  skills_practiced: ParentSkillRef[];
  level_ups: number;
}

export interface ParentSummary {
  child: Child;
  today: ParentPeriodSummary;
  week: ParentPeriodSummary;
  current_streak: number;
  total_stars: number;
}

export interface ParentSuggestion {
  type: string;
  skill: ParentSkillRef | null;
  text_ar: string;
  text_en: string;
  tone: string;
}
