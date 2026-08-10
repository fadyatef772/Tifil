import { useEffect, useState } from "react";
import { api } from "../api";
import { t } from "../i18n";
import type { Child, Journey, JourneyStop, Lang } from "../types";

// The skills' `icon` field is a stable string key from the seed curriculum;
// this map turns it into the child-friendly emoji shown on the path
// (presentation only — the data still comes from the API). No new source of
// truth; the keys mirror app/seed.py's CURRICULUM icons exactly.
const ICON_EMOJI: Record<string, string> = {
  palette: "🎨",
  numbers: "🔢",
  "hand-stop": "🧼",
  shirt: "👕",
  shapes: "🔷",
  paw: "🐾",
  smile: "😊",
  hand: "🖐️",
  sun: "☀️",
  wave: "👋",
  handshake: "🤝",
  memory: "🧠",
  magnifier: "🔎",
  picture: "🖼️",
};
const FALLBACK_ICON = "⭐";

interface Props {
  child: Child;
  lang: Lang;
  onExit: () => void;
  onPlay: () => void;
}

// Level pips: one dot per skill level. Fully-mastered levels are filled,
// the child's current level is marked "here", the rest stay hollow — a
// tiny, purely visual sense of where they are on that stop.
function Pips({ stop }: { stop: JourneyStop }) {
  const pips = [];
  for (let i = 0; i < stop.total_levels; i++) {
    const done = i < stop.highest_mastered;
    const here = stop.status === "current" && i === stop.current_level - 1;
    pips.push(
      <span
        key={i}
        aria-hidden
        className={[
          "inline-block w-2.5 h-2.5 rounded-full",
          done ? "bg-emerald-500" : here ? "bg-amber-400" : "bg-stone-200",
        ].join(" ")}
      />,
    );
  }
  return <span className="flex gap-1.5 justify-center">{pips}</span>;
}

export default function LearningJourney({ child, lang, onExit, onPlay }: Props) {
  const s = t[lang];
  const [journey, setJourney] = useState<Journey | null>(null);

  // Re-fetch on every mount — when the child returns from playing, the
  // journey reflects any new mastery from the answers they just gave.
  useEffect(() => {
    let cancelled = false;
    api.journey(child.id).then((j) => {
      if (!cancelled) setJourney(j);
    });
    return () => {
      cancelled = true;
    };
  }, [child.id]);

  const name = (stop: JourneyStop) =>
    lang === "ar" ? stop.name_ar : stop.name_en;
  const emoji = (stop: JourneyStop) => ICON_EMOJI[stop.icon] ?? FALLBACK_ICON;

  if (!journey) {
    return (
      <div className="min-h-[60vh] grid place-items-center text-3xl">…</div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      {/* Quiet top bar — back to the child picker, child's name, total stars */}
      <div className="flex items-center justify-between px-5 py-4">
        <button
          onClick={onExit}
          aria-label={s.backToChildren}
          className="w-12 h-12 grid place-items-center rounded-full bg-white/70 hover:bg-white shadow text-2xl"
        >
          {lang === "ar" ? "→" : "←"}
        </button>
        <span className="text-2xl font-bold">{child.name}</span>
        <span
          className="flex items-center gap-1.5 px-4 py-1.5 rounded-full bg-white/70 shadow text-lg font-bold"
          aria-label={`${journey.total_stars} ${s.stars}`}
        >
          <span aria-hidden>⭐</span>
          {journey.total_stars}
        </span>
      </div>

      <h1 className="text-center text-3xl font-bold mt-2 mb-6">{s.journey}</h1>

      {/* One clear, linear path: mastered … current … locked. */}
      <div className="flex-1 flex justify-center px-6 pb-10">
        <ol className="w-full max-w-xs">
          {journey.stops.map((stop, i) => (
            <li key={stop.skill_id} className="flex flex-col items-center">
              {/* Connector between stops — dashed, builds anticipation */}
              {i > 0 && (
                <div
                  aria-hidden
                  className="w-1 h-8 border-l-4 border-dashed border-stone-300"
                />
              )}

              {stop.status === "current" ? (
                <button
                  onClick={onPlay}
                  className={[
                    "animate-pop relative flex flex-col items-center gap-2 p-3 rounded-[2rem]",
                    "bg-white shadow-lg ring-4 ring-amber-400 animate-pulse",
                    "hover:-translate-y-1 transition-transform active:scale-95",
                  ].join(" ")}
                  aria-label={`${name(stop)} ${s.start}`}
                >
                  <span className="relative">
                    <span
                      className="grid place-items-center w-24 h-24 rounded-full bg-amber-100 text-6xl"
                      aria-hidden
                    >
                      {emoji(stop)}
                    </span>
                    {stop.is_active_goal && (
                      <span
                        className="absolute -top-1 -end-1 text-3xl animate-cheer"
                        aria-hidden
                      >
                        🎯
                      </span>
                    )}
                  </span>
                  <span className="text-2xl font-bold leading-tight text-center">
                    {name(stop)}
                  </span>
                  <span className="text-lg font-bold text-amber-600">
                    ▶ {s.start}
                  </span>
                  <Pips stop={stop} />
                </button>
              ) : (
                <div
                  className="flex flex-col items-center gap-2 p-3"
                  aria-label={name(stop)}
                >
                  <span className="relative">
                    <span
                      className={[
                        "grid place-items-center w-24 h-24 rounded-full text-6xl",
                        stop.status === "mastered"
                          ? "bg-emerald-100"
                          : "bg-white/70 grayscale opacity-40",
                      ].join(" ")}
                      aria-hidden
                    >
                      {emoji(stop)}
                    </span>
                    {stop.status === "mastered" ? (
                      <span
                        className="absolute -top-1 -end-1 text-3xl animate-cheer"
                        aria-hidden
                      >
                        ⭐
                      </span>
                    ) : (
                      <span
                        className="absolute -top-1 -end-1 text-2xl opacity-40"
                        aria-hidden
                      >
                        ☆
                      </span>
                    )}
                  </span>
                  <span
                    className={[
                      "text-xl font-bold leading-tight text-center",
                      stop.status === "mastered"
                        ? "text-emerald-700"
                        : "text-stone-400",
                    ].join(" ")}
                  >
                    {name(stop)}
                  </span>
                  <Pips stop={stop} />
                </div>
              )}
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
