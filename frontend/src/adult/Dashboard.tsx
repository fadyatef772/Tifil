import { useEffect, useState } from "react";
import { api } from "../api";
import { t } from "../i18n";
import type {
  Child,
  ChildProgress,
  Goal,
  Lang,
  SessionSummary,
  SkillProgress,
} from "../types";

interface Props {
  lang: Lang;
}

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
              "w-4 h-4 rounded-full",
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

export default function Dashboard({ lang }: Props) {
  const s = t[lang];
  const [children, setChildren] = useState<Child[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [progress, setProgress] = useState<ChildProgress | null>(null);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [newGoalSkillId, setNewGoalSkillId] = useState<number | "">("");
  const [newGoalLevel, setNewGoalLevel] = useState<string>("");

  useEffect(() => {
    api.listChildren().then((cs) => {
      setChildren(cs);
      if (cs.length && selected === null) setSelected(cs[0].id);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (selected === null) return;
    api.progress(selected).then(setProgress);
    api.listGoals(selected).then(setGoals);
    api.recentSessions(selected).then(setSessions);
    setNewGoalSkillId("");
    setNewGoalLevel("");
  }, [selected]);

  const name = (sk: { name_ar: string; name_en: string }) =>
    lang === "ar" ? sk.name_ar : sk.name_en;
  const cognitive = progress?.skills.filter((x) => x.category === "cognitive") ?? [];
  const daily = progress?.skills.filter((x) => x.category === "daily_life") ?? [];
  const social = progress?.skills.filter((x) => x.category === "social") ?? [];

  async function addGoal() {
    if (selected === null || newGoalSkillId === "") return;
    const level = newGoalLevel === "" ? null : Number(newGoalLevel);
    await api.createGoal(selected, newGoalSkillId, level);
    setNewGoalSkillId("");
    setNewGoalLevel("");
    setGoals(await api.listGoals(selected));
  }

  async function archiveGoal(goalId: number) {
    await api.updateGoal(goalId, "archived");
    if (selected !== null) setGoals(await api.listGoals(selected));
  }

  const skillForNewGoal = progress?.skills.find(
    (sk) => sk.skill_id === newGoalSkillId,
  );

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      <h2 className="text-2xl font-bold mb-6">{s.progress}</h2>

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

          {progress && (
            <>
              {/* Headline numbers */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-10">
                <Stat
                  label={s.overall + " " + s.accuracy}
                  value={`${Math.round(progress.overall_accuracy * 100)}%`}
                />
                <Stat
                  label={s.attempts}
                  value={String(progress.total_attempts)}
                />
              </div>

              <SkillGroup title={s.cognitive} skills={cognitive} name={name} s={s} />
              <SkillGroup title={s.dailyLife} skills={daily} name={name} s={s} />
              <SkillGroup title={s.social} skills={social} name={name} s={s} />

              {/* Goals — adult-set, nudge exercise selection but never
                  restrict it (see backend adaptive_engine.select_next_exercise) */}
              <section className="mb-10">
                <h3 className="text-lg font-bold text-stone-500 mb-3">{s.goals}</h3>

                <div className="rounded-2xl bg-white shadow-sm p-5 mb-4 flex flex-wrap items-center gap-3">
                  <select
                    value={newGoalSkillId}
                    onChange={(e) =>
                      setNewGoalSkillId(e.target.value === "" ? "" : Number(e.target.value))
                    }
                    className="px-4 py-2 rounded-xl bg-stone-100 outline-none"
                  >
                    <option value="">{s.chooseSkill}</option>
                    {progress?.skills.map((sk) => (
                      <option key={sk.skill_id} value={sk.skill_id}>
                        {name(sk)}
                      </option>
                    ))}
                  </select>
                  <select
                    value={newGoalLevel}
                    onChange={(e) => setNewGoalLevel(e.target.value)}
                    disabled={!skillForNewGoal}
                    className="px-4 py-2 rounded-xl bg-stone-100 outline-none disabled:opacity-50"
                  >
                    <option value="">{s.practiceGoal}</option>
                    {Array.from(
                      { length: skillForNewGoal?.total_levels ?? 0 },
                      (_, i) => i + 1,
                    ).map((lvl) => (
                      <option key={lvl} value={lvl}>
                        {s.masterLevel} {lvl}
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={addGoal}
                    disabled={newGoalSkillId === ""}
                    className="px-5 py-2 rounded-xl bg-emerald-500 text-white font-semibold disabled:opacity-40"
                  >
                    {s.addGoal}
                  </button>
                </div>

                {goals.length === 0 ? (
                  <p className="text-stone-500">{s.noGoals}</p>
                ) : (
                  <div className="space-y-3">
                    {goals.map((g) => (
                      <div
                        key={g.id}
                        className="rounded-2xl bg-white shadow-sm p-5 flex items-center justify-between gap-4"
                      >
                        <div className="min-w-0">
                          <div className="text-lg font-bold">
                            {lang === "ar" ? g.skill_name_ar : g.skill_name_en}
                            {" — "}
                            {g.target_level
                              ? `${s.masterLevel} ${g.target_level}`
                              : s.practiceGoal}
                          </div>
                          <div className="text-sm text-stone-500">
                            {s.level} {g.current_level} · {s.masteredUpTo}{" "}
                            {g.highest_mastered}
                          </div>
                        </div>
                        <div className="flex items-center gap-3 shrink-0">
                          <span
                            className={[
                              "px-3 py-1 rounded-full text-sm font-semibold",
                              g.status === "achieved"
                                ? "bg-emerald-100 text-emerald-700"
                                : g.status === "active"
                                  ? "bg-amber-100 text-amber-700"
                                  : "bg-stone-100 text-stone-500",
                            ].join(" ")}
                          >
                            {g.status === "achieved"
                              ? s.goalAchieved
                              : g.status === "active"
                                ? s.goalActive
                                : s.goalArchived}
                          </span>
                          {g.status !== "archived" && (
                            <button
                              onClick={() => archiveGoal(g.id)}
                              className="text-sm text-stone-400 hover:text-stone-600 underline"
                            >
                              {s.archive}
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              {/* Recent sessions */}
              <section className="mb-10">
                <h3 className="text-lg font-bold text-stone-500 mb-3">
                  {s.recentSessions}
                </h3>
                {sessions.length === 0 ? (
                  <p className="text-stone-500">{s.noSessions}</p>
                ) : (
                  <div className="space-y-3">
                    {sessions.map((sess) => (
                      <div
                        key={sess.session_id}
                        className="rounded-2xl bg-white shadow-sm p-5"
                      >
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
              </section>
            </>
          )}
        </>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-white shadow-sm p-5">
      <div className="text-3xl font-bold">{value}</div>
      <div className="text-sm text-stone-500 mt-1">{label}</div>
    </div>
  );
}

function SkillGroup({
  title,
  skills,
  name,
  s,
}: {
  title: string;
  skills: SkillProgress[];
  name: (x: SkillProgress) => string;
  s: (typeof t)["ar"] | (typeof t)["en"];
}) {
  if (!skills.length) return null;
  return (
    <section className="mb-10">
      <h3 className="text-lg font-bold text-stone-500 mb-3">{title}</h3>
      <div className="space-y-3">
        {skills.map((sk) => (
          <div
            key={sk.skill_id}
            className="rounded-2xl bg-white shadow-sm p-5 flex items-center justify-between gap-4"
          >
            <div className="min-w-0">
              <div className="text-xl font-bold">{name(sk)}</div>
              <div className="text-sm text-stone-500">
                {s.level} {sk.current_level} {s.of} {sk.total_levels}
                {" · "}
                {sk.attempts} {s.attempts} · {Math.round(sk.accuracy * 100)}%{" "}
                {s.accuracy}
              </div>
            </div>
            <LevelDots s={sk} />
          </div>
        ))}
      </div>
    </section>
  );
}
