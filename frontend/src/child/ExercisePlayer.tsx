import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { speak, t } from "../i18n";
import type {
  AnswerResult,
  AnswerRewards,
  Avatar,
  Exercise,
  Lang,
  SessionSummary,
} from "../types";
import ExerciseRenderer from "./exercises/registry";

interface Props {
  childId: number;
  lang: Lang;
  onExit: () => void;
}

// Feature-detect the recording APIs once; tapping always works regardless.
const micSupported =
  typeof navigator !== "undefined" &&
  !!navigator.mediaDevices?.getUserMedia &&
  typeof MediaRecorder !== "undefined";

export default function ExercisePlayer({ childId, lang, onExit }: Props) {
  const s = t[lang];
  const [exercise, setExercise] = useState<Exercise | null>(null);
  const [loading, setLoading] = useState(true);
  const [done, setDone] = useState(false);
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [wrongId, setWrongId] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [processingSpeech, setProcessingSpeech] = useState(false);
  const [speechHint, setSpeechHint] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<number | null>(null);
  // 8 is just a placeholder matching the backend default until the real
  // target comes back from POST .../sessions/start.
  const [sessionTarget, setSessionTarget] = useState(8);
  const [completedCount, setCompletedCount] = useState(0);
  const [sessionSummary, setSessionSummary] = useState<SessionSummary | null>(null);
  const [totalStars, setTotalStars] = useState(0);
  const [streak, setStreak] = useState(0);
  const [newAvatar, setNewAvatar] = useState<Avatar | null>(null);
  const triesRef = useRef(1);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  // Start a session once per mount. Sessions are additive: if this fails
  // for any reason the child can still play, just without a summary at
  // the end (answers below always tolerate a null sessionId).
  useEffect(() => {
    let cancelled = false;
    api
      .startSession(childId)
      .then((s) => {
        if (cancelled) return;
        setSessionId(s.session_id);
        setSessionTarget(s.target_exercises);
      })
      .catch(() => {});
    // Pre-load the child's current stars/streak so the counters aren't
    // blank on the first exercise. Best-effort: failure leaves them at 0.
    api
      .rewards(childId)
      .then((r) => {
        if (cancelled) return;
        setTotalStars(r.total_stars);
        setStreak(r.streak);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [childId]);

  // Apply reward updates from an answer/speech result.
  function applyRewards(rewards: AnswerRewards | undefined) {
    if (!rewards) return;
    setTotalStars(rewards.stars);
    setStreak(rewards.streak);
    if (rewards.new_avatar) setNewAvatar(rewards.new_avatar);
  }

  // A newly-unlocked avatar celebrates for a moment, then lets the child
  // carry on. No interaction required — just delight.
  useEffect(() => {
    if (!newAvatar) return;
    const timer = setTimeout(() => setNewAvatar(null), 3000);
    return () => clearTimeout(timer);
  }, [newAvatar]);

  const prompt = (ex: Exercise) => (lang === "ar" ? ex.prompt_ar : ex.prompt_en);

  const load = useCallback(async () => {
    setLoading(true);
    setResult(null);
    setWrongId(null);
    setSpeechHint(null);
    setProcessingSpeech(false);
    triesRef.current = 1;
    const next = await api.nextExercise(childId);
    if (next.exercise) {
      setExercise(next.exercise);
      // Read the prompt aloud automatically — the child leads by ear + eye.
      setTimeout(() => speak(prompt(next.exercise!), lang), 350);
    } else {
      setDone(true);
    }
    setLoading(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [childId, lang]);

  useEffect(() => {
    load();
  }, [load]);

  // Post a structured answer (option_id, pairings, order, points, ...) and
  // handle the shared success/retry + reward bookkeeping. The exercise
  // renderer reads the verdict to show type-appropriate feedback.
  async function submitAnswer(answer: unknown): Promise<AnswerResult> {
    if (!exercise) throw new Error("no exercise loaded");
    const res = await api.answer(
      childId,
      exercise.id,
      null,
      answer,
      triesRef.current,
      sessionId,
    );
    if (res.is_correct) {
      setResult(res);
      setCompletedCount((c) => c + 1);
      applyRewards(res.rewards);
      speak(s.greatJob, lang);
    } else {
      // No punishment: the renderer lets them try again.
      triesRef.current += 1;
      applyRewards(res.rewards); // streak quietly returns to zero
      speak(s.tryAgain, lang);
    }
    return res;
  }

  async function startRecording() {
    if (!exercise || result?.is_correct || recording) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        void handleRecordedAnswer(
          new Blob(chunksRef.current, { type: recorder.mimeType }),
        );
      };
      mediaRecorderRef.current = recorder;
      setSpeechHint(null);
      recorder.start();
      setRecording(true);
    } catch {
      // Mic permission denied or unavailable — tapping still works.
      setRecording(false);
    }
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
    setRecording(false);
  }

  async function handleRecordedAnswer(audio: Blob) {
    if (!exercise) return;
    setProcessingSpeech(true);
    try {
      const res = await api.speechAnswer(
        childId,
        exercise.id,
        triesRef.current,
        lang,
        audio,
        sessionId,
      );
      if (res.feedback === "unclear") {
        setSpeechHint(s.didNotHear);
      } else if (res.is_correct) {
        setResult({
          is_correct: true,
          feedback: "correct",
          leveled_up: res.leveled_up,
          new_level: res.new_level,
        });
        setCompletedCount((c) => c + 1);
        applyRewards(res.rewards);
        speak(s.greatJob, lang);
      } else {
        triesRef.current += 1;
        applyRewards(res.rewards); // streak quietly returns to zero
        if (res.matched_option_id) {
          setWrongId(res.matched_option_id);
          setTimeout(() => setWrongId(null), 500);
        }
        speak(s.tryAgain, lang);
      }
    } catch {
      setSpeechHint(s.didNotHear);
    } finally {
      setProcessingSpeech(false);
    }
  }

  async function handleNext() {
    if (sessionId && completedCount >= sessionTarget) {
      setLoading(true);
      try {
        setSessionSummary(await api.endSession(sessionId));
      } catch {
        // No summary available, but don't trap the child on this screen.
        onExit();
      }
      setLoading(false);
      return;
    }
    load();
  }

  if (loading) {
    return (
      <div className="min-h-screen grid place-items-center text-3xl">…</div>
    );
  }

  if (sessionSummary) {
    const skillName = (sk: { name_ar: string; name_en: string }) =>
      lang === "ar" ? sk.name_ar : sk.name_en;
    return (
      <div className="min-h-screen grid place-items-center text-center px-6">
        <div className="max-w-md w-full">
          <div className="text-8xl mb-4 animate-cheer">🌟</div>
          <p className="text-3xl font-bold mb-2">{s.sessionDone}</p>
          <p className="text-lg text-stone-500 mb-6">{s.sessionRecap}</p>

          <div className="rounded-3xl bg-white shadow-lg p-6 mb-8 text-start">
            <div className="flex justify-between text-lg font-semibold mb-4">
              <span>
                {sessionSummary.total_attempts} {s.exercisesDone}
              </span>
              <span>{Math.round(sessionSummary.accuracy * 100)}% {s.accuracy}</span>
            </div>
            <div className="space-y-2">
              {sessionSummary.skills.map((sk) => (
                <div key={sk.skill_id} className="flex justify-between text-stone-600">
                  <span>{skillName(sk)}</span>
                  <span>{sk.attempts} · {Math.round(sk.accuracy * 100)}%</span>
                </div>
              ))}
            </div>
            {sessionSummary.level_ups.length > 0 && (
              <div className="mt-4 pt-4 border-t border-stone-100 space-y-1">
                {sessionSummary.level_ups.map((lu, i) => (
                  <div key={i} className="text-amber-600 font-semibold">
                    ⭐️ {skillName(lu)} → {s.level} {lu.new_level}
                  </div>
                ))}
              </div>
            )}
          </div>

          <button
            onClick={onExit}
            className="text-2xl px-10 py-5 rounded-3xl bg-amber-400 hover:bg-amber-500 shadow-lg font-bold"
          >
            {s.backToChildren}
          </button>
        </div>
      </div>
    );
  }

  if (done) {
    return (
      <div className="min-h-screen grid place-items-center text-center px-6">
        <div>
          <div className="text-8xl mb-6 animate-cheer">🎉</div>
          <p className="text-3xl font-bold mb-8">{s.done}</p>
          <button
            onClick={onExit}
            className="text-2xl px-10 py-5 rounded-3xl bg-amber-400 hover:bg-amber-500 shadow-lg font-bold"
          >
            {s.backToChildren}
          </button>
        </div>
      </div>
    );
  }

  if (!exercise) return null;

  const correct = result?.is_correct;

  return (
    <div className="min-h-screen flex flex-col">
      {/* Quiet top bar — small exit, no clutter for the child */}
      <div className="flex items-center justify-between px-5 py-4">
        <button
          onClick={onExit}
          aria-label={s.backToChildren}
          className="w-12 h-12 grid place-items-center rounded-full bg-white/70 hover:bg-white shadow text-2xl"
        >
          {lang === "ar" ? "→" : "←"}
        </button>

        {/* Rewards — stars + streak, positive-only, big and calm */}
        <div className="flex items-center gap-2">
          <span
            className="flex items-center gap-1.5 px-4 py-1.5 rounded-full bg-white/70 shadow text-lg font-bold"
            aria-label={`${totalStars} ${s.stars}`}
          >
            <span aria-hidden>⭐</span>
            {totalStars}
          </span>
          {streak > 1 && (
            <span
              className="flex items-center gap-1.5 px-4 py-1.5 rounded-full bg-white/70 shadow text-lg font-bold"
              aria-label={`${s.streak} ${streak}`}
            >
              <span aria-hidden>🔥</span>
              ×{streak}
            </span>
          )}
        </div>

        <span className="px-4 py-1.5 rounded-full bg-white/70 text-lg font-semibold">
          {lang === "ar" ? exercise.skill_name_ar : exercise.skill_name_en}
        </span>
      </div>

      {/* Visual session progress — stars, not a number, for the child */}
      <div
        className="flex justify-center gap-1 mb-2"
        role="img"
        aria-label={`${Math.min(completedCount, sessionTarget)}/${sessionTarget}`}
      >
        {Array.from({ length: sessionTarget }).map((_, i) => (
          <span key={i} className="text-2xl" aria-hidden>
            {i < completedCount ? "⭐" : "☆"}
          </span>
        ))}
      </div>

      {/* Prompt with a big replay-audio button */}
      <div className="text-center px-6 mt-2 mb-8">
        <button
          onClick={() => speak(prompt(exercise), lang)}
          className="inline-flex items-center gap-3 text-3xl sm:text-4xl font-bold px-6 py-4 rounded-3xl bg-white/70 hover:bg-white shadow"
        >
          <span aria-hidden>🔊</span>
          <span>{prompt(exercise)}</span>
        </button>
      </div>

      {/* Optional speech input — tapping remains the primary path, and only
          choice exercises accept speech answers (the backend rejects it for
          matching/sequencing/tracing). */}
      {exercise.type === "choice" && micSupported && !correct && (
        <div className="flex flex-col items-center gap-2 mb-6">
          <button
            onClick={recording ? stopRecording : startRecording}
            disabled={processingSpeech}
            className={[
              "flex items-center gap-2 text-lg font-semibold px-6 py-3 rounded-2xl shadow transition-colors",
              recording
                ? "bg-red-500 text-white animate-pulse"
                : "bg-white/70 hover:bg-white",
              processingSpeech ? "opacity-60" : "",
            ].join(" ")}
          >
            <span aria-hidden>🎤</span>
            {processingSpeech
              ? s.thinking
              : recording
                ? s.stopRecording
                : s.sayAnswer}
          </button>
          {speechHint && (
            <p className="text-lg text-amber-600 font-medium">{speechHint}</p>
          )}
        </div>
      )}

      {/* The exercise itself — the renderer registry picks the component
          for this exercise's type (choice / matching / sequencing / tracing) */}
      <div className="flex-1 flex items-start justify-center px-4 pb-4">
        <ExerciseRenderer
          exercise={exercise}
          lang={lang}
          disabled={!!correct}
          wrongId={wrongId}
          onSubmit={submitAnswer}
        />
      </div>

      {/* Reward band — only ever positive */}
      <div className="h-40 grid place-items-center">
        {correct ? (
          <div className="text-center animate-cheer">
            <div className="text-6xl mb-2">
              {result?.leveled_up ? "⭐️" : "✅"}
            </div>
            <p className="text-2xl font-bold text-emerald-700">
              {result?.leveled_up ? s.levelUp : s.greatJob}
            </p>
            <button
              onClick={handleNext}
              className="mt-3 text-xl px-8 py-4 rounded-3xl bg-emerald-500 hover:bg-emerald-600 text-white font-bold shadow-lg"
            >
              {completedCount >= sessionTarget ? s.finish : s.next} →
            </button>
          </div>
        ) : (
          <p className="text-xl text-stone-400">{/* neutral, no pressure */}</p>
        )}
      </div>

      {/* Avatar-unlock celebration — reuse the app's existing animations,
          no new dependencies */}
      {newAvatar && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/40">
          <div className="text-center bg-white rounded-[2.5rem] px-10 py-8 shadow-2xl animate-pop max-w-sm mx-6">
            <div className="text-4xl mb-2">
              <span className="inline-block animate-pop">✨</span>{" "}
              <span className="inline-block animate-pop">🎉</span>
            </div>
            <div className="text-8xl mb-4 animate-cheer">{newAvatar.emoji}</div>
            <p className="text-3xl font-bold mb-1">{s.newAvatar}</p>
            <p className="text-lg text-stone-500 mb-5">{s.keepCollecting}</p>
            <button
              onClick={() => setNewAvatar(null)}
              className="text-2xl px-10 py-4 rounded-3xl bg-amber-400 hover:bg-amber-500 shadow-lg font-bold"
            >
              {s.wonderful}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
