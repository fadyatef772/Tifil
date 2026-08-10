import { useEffect, useState } from "react";
import { api } from "../api";
import { t } from "../i18n";
import type {
  Child,
  Lang,
  ParentPeriodSummary,
  ParentSuggestion,
  ParentSummary,
  SessionSummary,
  SkillProgress,
} from "../types";

interface Props {
  lang: Lang;
}

// Gentle, non-clinical per-skill statuses derived from the child's own data.
// Never a label of "weakness" — always framed as where the child is right now.
function friendlyStatus(s: SkillProgress): "doingWell" | "stillPracticing" | "gettingStarted" {
  if (s.attempts === 0) return "gettingStarted";
  return s.accuracy >= 0.6 ? "doingWell" : "stillPracticing";
}

const STATUS_STYLE = {
  doingWell: "bg-emerald-100 text-emerald-700",
  stillPracticing: "bg-amber-100 text-amber-700",
  gettingStarted: "bg-sky-100 text-sky-700",
} as const;

function LevelDots({ s }: { s: SkillProgress }) {
  return (
    <div className="flex gap-1.5">
      {Array.from({ length: s.total_levels }).map((_, i) => {
        const level = i + 1;
        const mastered = level <= s.highest_mastered;
        const current = level === s.current_level;
        return (
          <span
            key={i}
            title={`level ${level}`}
            className={[
              "w-3.5 h-3.5 rounded-full",
              mastered
                ? "bg-emerald-500"
                : current
                  ? "bg-amber-400 ring-2 ring-amber-200"
                  : "bg-stone-200",
            ].join(" ")}
          />
        );
      })}
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-2xl bg-white shadow-sm p-4">
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-sm text-stone-500 mt-0.5">{label}</div>
      {sub && <div className="text-xs text-stone-400 mt-0.5">{sub}</div>}
    </div>
  );
}

function PeriodCard({
  period,
  title,
  lang,
  s,
}: {
  period: ParentPeriodSummary | null;
  title: string;
  lang: Lang;
  s: (typeof t)["ar"] | (typeof t)["en"];
}) {
  const name = (sk: { name_ar: string; name_en: string }) =>
    lang === "ar" ? sk.name_ar : sk.name_en;
  return (
    <div className="rounded-3xl bg-white/80 shadow-sm p-5">
      <h4 className="text-base font-bold text-stone-600 mb-3">{title}</h4>
      {!period || period.activities_done === 0 ? (
        <p className="text-stone-400 text-sm">{s.noData}</p>
      ) : (
        <div className="grid grid-cols-2 gap-3">
          <Stat label={s.activities} value={String(period.activities_done)} />
          <Stat label={s.accuracy} value={`${Math.round(period.accuracy * 100)}%`} />
          <Stat label={s.starsEarned} value={String(period.stars_earned)} />
          <Stat label={s.sessionsLabel} value={String(period.sessions_count)} />
          <Stat
            label={s.levelUpsLabel}
            value={String(period.level_ups)}
            sub={period.level_ups > 0 ? "⭐" : undefined}
          />
          <div className="rounded-2xl bg-white shadow-sm p-4">
            <div className="text-sm text-stone-500">
              {s.skillsPracticed}:{" "}
              <span className="text-stone-700 font-semibold">
                {period.skills_practiced.length}
              </span>
            </div>
            <div className="flex flex-wrap gap-1 mt-2">
              {period.skills_practiced.map((sk) => (
                <span
                  key={sk.skill_id}
                  className="px-2 py-0.5 rounded-full bg-stone-100 text-xs text-stone-600"
                >
                  {name(sk)}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ParentView({ lang }: Props) {
  const s = t[lang];
  const [children, setChildren] = useState<Child[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [summary, setSummary] = useState<ParentSummary | null>(null);
  const [suggestions, setSuggestions] = useState<ParentSuggestion[]>([]);
  const [progress, setProgress] = useState<SkillProgress[]>([]);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);

  useEffect(() => {
    api.listChildren().then((cs) => {
      setChildren(cs);
      if (cs.length && selected === null) setSelected(cs[0].id);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (selected === null) return;
    api.parentSummary(selected).then(setSummary);
    api.suggestions(selected).then(setSuggestions);
    api.progress(selected).then((p) => setProgress(p.skills));
    api.recentSessions(selected).then(setSessions);
  }, [selected]);

  const name = (sk: { name_ar: string; name_en: string }) =>
    lang === "ar" ? sk.name_ar : sk.name_en;

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      <h2 className="text-2xl font-bold mb-1">{s.parentView}</h2>
      <p className="text-stone-500 text-sm mb-6">
        {s.tagline} · {s.suggestionsNote}
      </p>

      {children.length === 0 ? (
        <p className="text-stone-500">{s.noData}</p>
      ) : (
        <>
          {/* Child chooser */}
          <div className="flex flex-wrap gap-2 mb-8">
            {children.map((c) => (
              <button
                key={c.id}
                onClick={() => setSelected(c.id)}
                className={[
                  "px-5 py-2.5 rounded-full font-semibold transition-colors",
                  selected === c.id
                    ? "bg-stone-800 text-white"
                    : "bg-white text-stone-700 hover:bg-stone-100",
                ].join(" ")}
              >
                {c.name}
              </button>
            ))}
          </div>

          {summary && (
            <>
              {/* Overall line — streak + total stars */}
              <div className="flex flex-wrap gap-3 mb-6">
                <span className="flex items-center gap-1.5 px-4 py-2 rounded-full bg-white shadow-sm text-base font-bold">
                  <span aria-hidden>🔥</span> {s.currentStreak}: {summary.current_streak}
                </span>
                <span className="flex items-center gap-1.5 px-4 py-2 rounded-full bg-white shadow-sm text-base font-bold">
                  <span aria-hidden>⭐</span> {s.totalStars}: {summary.total_stars}
                </span>
              </div>

              {/* 1. Snapshot — today + this week */}
              <h3 className="text-lg font-bold text-stone-500 mb-3">
                {s.parentSummaryTitle}
              </h3>
              <div className="grid sm:grid-cols-2 gap-4 mb-10">
                <PeriodCard period={summary.today} title={s.today} lang={lang} s={s} />
                <PeriodCard period={summary.week} title={s.thisWeek} lang={lang} s={s} />
              </div>

              {/* 2. Skill progress — friendly status, no clinical labels */}
              <h3 className="text-lg font-bold text-stone-500 mb-3">{s.progress}</h3>
              <div className="space-y-3 mb-10">
                {progress.length === 0 && <p className="text-stone-500">{s.noData}</p>}
                {progress.map((sk) => {
                  const status = friendlyStatus(sk);
                  return (
                    <div
                      key={sk.skill_id}
                      className="rounded-2xl bg-white shadow-sm p-4 flex items-center justify-between gap-4"
                    >
                      <div className="min-w-0">
                        <div className="text-lg font-bold">{name(sk)}</div>
                        <div className="text-sm text-stone-500">
                          {s.level} {sk.current_level} {s.of} {sk.total_levels}
                          {" · "}
                          {sk.attempts} {s.attempts}
                        </div>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <LevelDots s={sk} />
                        <span
                          className={[
                            "px-3 py-1 rounded-full text-sm font-semibold",
                            STATUS_STYLE[status],
                          ].join(" ")}
                        >
                          {s[status]}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* 3. Suggestions — gentle, optional home ideas */}
              <h3 className="text-lg font-bold text-stone-500 mb-1">{s.suggestionsTitle}</h3>
              <p className="text-sm text-stone-400 mb-3">{s.suggestionsIntro}</p>
              <div className="space-y-3 mb-10">
                {suggestions.length === 0 ? (
                  <p className="text-stone-500">{s.noSuggestions}</p>
                ) : (
                  suggestions.map((su, i) => (
                    <div
                      key={i}
                      className="rounded-2xl bg-amber-50 border border-amber-100 shadow-sm p-4"
                    >
                      <div className="flex items-start gap-3">
                        <span className="text-xl" aria-hidden>
                          💡
                        </span>
                        <div>
                          <p className="text-stone-800 font-medium">
                            {lang === "ar" ? su.text_ar : su.text_en}
                          </p>
                          <p className="text-xs text-stone-400 mt-1">{s.suggestionsNote}</p>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>

              {/* 4. Recent sessions */}
              <h3 className="text-lg font-bold text-stone-500 mb-3">{s.recentSessions}</h3>
              {sessions.length === 0 ? (
                <p className="text-stone-500">{s.noSessions}</p>
              ) : (
                <div className="space-y-3 mb-10">
                  {sessions.map((sess) => (
                    <div key={sess.session_id} className="rounded-2xl bg-white shadow-sm p-4">
                      <div className="flex justify-between text-sm text-stone-500 mb-1">
                        <span>
                          {new Date(sess.started_at).toLocaleString(
                            lang === "ar" ? "ar-EG" : "en-US",
                          )}
                        </span>
                        <span>
                          {sess.total_attempts} {s.attempts} ·{" "}
                          {Math.round(sess.accuracy * 100)}% {s.accuracy}
                        </span>
                      </div>
                      {sess.level_ups.length > 0 && (
                        <div className="text-amber-600 text-sm font-semibold">
                          {sess.level_ups.map((lu, i) => (
                            <span key={i}>
                              ⭐ {name(lu)} → {s.level} {lu.new_level}
                              {i < sess.level_ups.length - 1 ? "  ·  " : ""}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
