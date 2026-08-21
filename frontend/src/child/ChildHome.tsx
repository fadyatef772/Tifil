import { useEffect, useState } from "react";
import { api } from "../api";
import { t } from "../i18n";
import type { Child, Lang, Rewards } from "../types";
import ExercisePlayer from "./ExercisePlayer";
import LearningJourney from "./LearningJourney";

interface Props {
  lang: Lang;
}

export default function ChildHome({ lang }: Props) {
  const s = t[lang];
  const [children, setChildren] = useState<Child[]>([]);
  const [rewardsMap, setRewardsMap] = useState<Record<number, Rewards>>({});
  const [active, setActive] = useState<Child | null>(null);
  const [playing, setPlaying] = useState(false);
  const [newName, setNewName] = useState("");
  const [adding, setAdding] = useState(false);

  async function refresh() {
    const list = await api.listChildren();
    setChildren(list);
    // Load each child's rewards so their avatar strip shows unlocked vs.
    // locked. Best-effort per child: a failure just skips that strip.
    const rows = await Promise.all(
      list.map((c) => api.rewards(c.id).catch(() => null)),
    );
    const map: Record<number, Rewards> = {};
    list.forEach((c, i) => {
      if (rows[i]) map[c.id] = rows[i]!;
    });
    setRewardsMap(map);
  }
  useEffect(() => {
    refresh();
  }, []);

  async function addChild() {
    if (!newName.trim()) return;
    const child = await api.createChild(newName.trim(), lang);
    setNewName("");
    setAdding(false);
    await refresh();
    setActive(child);
  }

  const activeAvatar = (childId: number) =>
    rewardsMap[childId]?.active_avatar?.emoji ?? "🦊";

  // Child flow: pick a child -> their learning path (journey) -> play.
  // Tapping a stop on the journey starts the exercise player; finishing a
  // session lands back on the journey (which re-fetches, so any new mastery
  // is reflected immediately) and the journey's back arrow returns to the
  // child picker.
  if (playing && active) {
    return (
      <ExercisePlayer
        childId={active.id}
        lang={lang}
        speechLang={active.preferred_language}
        onExit={() => {
          setPlaying(false);
          refresh();
        }}
      />
    );
  }

  if (active) {
    return (
      <LearningJourney
        child={active}
        lang={lang}
        onExit={() => {
          setActive(null);
          refresh();
        }}
        onPlay={() => setPlaying(true)}
      />
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      <h2 className="text-3xl font-bold mb-8 text-center">{s.pickChild}</h2>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-5">
        {children.map((c) => {
          const r = rewardsMap[c.id];
          return (
            <button
              key={c.id}
              onClick={() => setActive(c)}
              className="animate-pop rounded-[2rem] bg-white shadow-lg p-6 flex flex-col items-center gap-2 hover:-translate-y-1 transition-transform"
            >
              <span className="text-6xl" aria-hidden>
                {activeAvatar(c.id)}
              </span>
              <span className="text-2xl font-bold">{c.name}</span>
              {r && (
                <>
                  <span className="flex items-center gap-1 text-xl font-bold text-amber-600">
                    <span aria-hidden>⭐</span>
                    {r.total_stars}
                  </span>
                  {/* Avatar collection: unlocked in color, locked dimmed as
                      a silhouette so the child sees what's coming */}
                  <div
                    className="flex gap-1.5 mt-1"
                    role="img"
                    aria-label={s.collection}
                  >
                    {r.avatars.map((a) => (
                      <span
                        key={a.id}
                        aria-hidden
                        title={a.unlocked ? a.emoji : `${a.stars} ${s.needsStars}`}
                        className={
                          a.unlocked
                            ? "text-xl"
                            : "text-xl opacity-25 grayscale"
                        }
                      >
                        {a.emoji}
                      </span>
                    ))}
                  </div>
                </>
              )}
            </button>
          );
        })}

        {adding ? (
          <div className="rounded-[2rem] bg-white shadow-lg p-5 flex flex-col gap-3 justify-center">
            <input
              autoFocus
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addChild()}
              placeholder={s.name}
              className="text-xl px-4 py-3 rounded-2xl bg-stone-100 outline-none text-center"
            />
            <button
              onClick={addChild}
              className="text-xl py-3 rounded-2xl bg-emerald-500 text-white font-bold"
            >
              {s.add}
            </button>
          </div>
        ) : (
          <button
            onClick={() => setAdding(true)}
            className="rounded-[2rem] border-4 border-dashed border-stone-300 p-6 flex flex-col items-center gap-3 text-stone-400 hover:border-stone-400 hover:text-stone-500"
          >
            <span className="text-6xl leading-none">＋</span>
            <span className="text-xl font-bold">{s.newChild}</span>
          </button>
        )}
      </div>
    </div>
  );
}
