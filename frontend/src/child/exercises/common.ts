import type { AnswerResult, Exercise, Lang } from "../../types";

// Every exercise renderer (choice, matching, sequencing, tracing) gets the
// same props. `onSubmit` posts a structured `answer` (the raw dict/list the
// backend type validator expects) and resolves with the engine's verdict so
// the renderer can show type-appropriate "try again" feedback.
export interface ExerciseProps {
  exercise: Exercise;
  lang: Lang;
  disabled: boolean;
  onSubmit: (answer: unknown) => Promise<AnswerResult>;
  // Set when the optional speech path (choice only) matched a WRONG card, so
  // the renderer can wiggle that card as if it had been tapped.
  wrongId?: string | null;
}

export function labelFor(
  lang: Lang,
  item: { label_ar: string; label_en: string },
): string {
  return lang === "ar" ? item.label_ar : item.label_en;
}

export function shuffle<T>(items: T[]): T[] {
  const copy = [...items];
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}
