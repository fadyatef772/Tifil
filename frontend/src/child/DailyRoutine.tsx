import { t } from "../i18n";
import type { DailyRoutine, Lang } from "../types";

interface Props {
  data: DailyRoutine;
  lang: Lang;
}

// The child's daily routine — a gentle nudge to come back, never a
// punishment. Built to the app's no-pressure principle:
//   * The daily streak (calendar days) is shown as a cheerful fact. A missed
//     day simply means a fresh start, framed only positively ("Let's start
//     today!" / "يلا نبدأ النهارده!") — there is NO "you lost your streak",
//     NO countdown, NO "play or lose it" warning anywhere.
//   * Today's plan is a small, fixed target (reusing the session target) shown
//     as filled stars — a struggling child still fills stars, so the plan
//     never becomes a source of anxiety.
//   * The 14-day calendar is celebratory: active days are colored, inactive
//     ones are merely pale — never red, never shaming.
export default function DailyRoutine({ data, lang }: Props) {
  const s = t[lang];
  const { daily_streak: streak, active_today: active, today_plan: plan } = data;
  const dayWord = streak === 1 ? s.dayWord : s.daysWord;
  const filled = Math.min(plan.done, plan.target);
  const activeCount = data.recent_days.filter((d) => d.active).length;

  return (
    <div className="animate-pop w-full max-w-xs mx-auto rounded-[2rem] bg-white/80 shadow-lg p-5 flex flex-col gap-4">
      {/* Daily streak — a cheerful fact, with only positive framing */}
      <div className="flex items-center justify-center gap-2 text-2xl font-bold">
        <span aria-hidden>{streak > 0 ? "🔥" : "🌱"}</span>
        <span aria-label={`${s.dailyStreakLabel}: ${streak}`}>
          {streak > 0 ? `${streak} ${dayWord}` : s.letsStartToday}
        </span>
      </div>

      {/* One gentle message: celebrate today, or invite a fresh start. There
          is deliberately no "play or lose your streak" language. */}
      <p className="text-center text-lg font-semibold text-emerald-700">
        {active ? s.greatJobToday : s.letsStartToday}
      </p>

      {/* Today's plan — filled stars, visual not numeric guilt */}
      <div className="flex flex-col items-center gap-1">
        <span className="text-sm font-semibold text-stone-500">{s.todayPlan}</span>
        <div
          className="flex justify-center gap-1"
          role="img"
          aria-label={`${s.todayPlan}: ${plan.done} ${s.of} ${plan.target}`}
        >
          {Array.from({ length: plan.target }).map((_, i) => (
            <span key={i} className="text-xl" aria-hidden>
              {i < filled ? "⭐" : "☆"}
            </span>
          ))}
        </div>
        <span className="text-sm font-bold text-stone-600">
          {plan.done}/{plan.target}
        </span>
      </div>

      {/* Recent-day calendar — active in colour, inactive merely pale */}
      <div className="flex flex-col items-center gap-2">
        <span className="text-sm font-semibold text-stone-500">
          {s.myDays} · {activeCount} {s.lastDaysActive}
        </span>
        <div
          className="flex flex-wrap justify-center gap-1.5"
          role="img"
          aria-label={`${s.myDays}: ${activeCount} ${s.lastDaysActive}`}
        >
          {data.recent_days.map((d) => (
            <span
              key={d.date}
              aria-hidden
              title={`${d.date}${d.active ? " · ✓" : ""}`}
              className={[
                "w-3.5 h-3.5 rounded-full",
                d.active
                  ? "bg-emerald-400 shadow-sm"
                  : "bg-stone-200/70",
              ].join(" ")}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
