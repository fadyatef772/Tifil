import { useState } from "react";
import type { Option } from "../../types";
import type { ExerciseProps } from "./common";
import { labelFor } from "./common";
import { Visual } from "./Visual";

// The classic tap-the-right-card exercise (extracted unchanged from the old
// ExercisePlayer so the behavior is byte-for-byte the same). Answers via the
// `option_id` of the tapped card.
export default function ChoiceExercise({
  exercise,
  lang,
  disabled,
  onSubmit,
  wrongId,
}: ExerciseProps) {
  const [shakeId, setShakeId] = useState<string | null>(null);
  const options = ((exercise.payload.options ?? exercise.options) as Option[]) ?? [];

  async function choose(o: Option) {
    const res = await onSubmit({ option_id: o.id });
    if (!res.is_correct) {
      // No punishment: wiggle the wrong card, encourage, let them try again.
      setShakeId(o.id);
      setTimeout(() => setShakeId(null), 500);
    }
  }

  return (
    <div
      className="grid gap-5 w-full max-w-3xl"
      style={{
        gridTemplateColumns: `repeat(${Math.min(
          options.length,
          options.length <= 2 ? 2 : 3,
        )}, minmax(0, 1fr))`,
      }}
    >
      {options.map((o) => {
        const isWrong = shakeId === o.id || wrongId === o.id;
        const dim = disabled;
        return (
          <button
            key={o.id}
            onClick={() => choose(o)}
            disabled={disabled}
            className={[
              "animate-pop rounded-[2rem] bg-white shadow-lg border-4",
              "flex flex-col items-center justify-center gap-4 p-6 min-h-[11rem]",
              "transition-transform active:scale-95",
              isWrong ? "animate-wiggle border-amber-300" : "border-transparent",
              dim ? "opacity-40" : "hover:-translate-y-1",
            ].join(" ")}
          >
            <Visual visual={o.visual} />
            <span className="text-2xl font-bold">{labelFor(lang, o)}</span>
          </button>
        );
      })}
    </div>
  );
}
