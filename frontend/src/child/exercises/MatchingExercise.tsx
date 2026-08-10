import { useMemo, useState } from "react";
import type { Option } from "../../types";
import type { ExerciseProps } from "./common";
import { labelFor, shuffle } from "./common";
import { Visual } from "./Visual";

interface Pair {
  id: string;
  left: Option;
  right: Option;
}

// Connection type (توصيل): tap a left card, then its right partner. When
// every pair is linked, a big done button submits. A partially-right answer
// is still a wrong answer (try again, nothing is punished).
export default function MatchingExercise({ exercise, lang, disabled, onSubmit }: ExerciseProps) {
  const pairs = (exercise.payload.pairs as Pair[]) ?? [];
  const [links, setLinks] = useState<Record<string, string>>({});
  const [selected, setSelected] = useState<string | null>(null);

  // The right column is shuffled once so the raw pair order never leaks the
  // answer; the child has to work the correspondence out for real.
  const rightOrder = useMemo(
    () => shuffle(pairs.map((p) => p.right)),
    [pairs],
  );

  // Colour-code each pair so a linked left/right visibly belong together.
  const accent = ["ring-emerald-500", "ring-sky-500", "ring-violet-500"];

  const pairIndex = useMemo(() => {
    const map: Record<string, number> = {};
    pairs.forEach((p, i) => {
      map[p.left.id] = i;
    });
    return map;
  }, [pairs]);

  function tapLeft(leftId: string) {
    if (disabled) return;
    if (links[leftId] !== undefined) {
      const next = { ...links };
      delete next[leftId];
      setLinks(next);
      setSelected(null);
      return;
    }
    setSelected(selected === leftId ? null : leftId);
  }

  function tapRight(rightId: string) {
    if (disabled || !selected) return;
    const next = { ...links };
    // A right card can only be linked once — stealing it from another left
    // is allowed, the old link simply moves.
    for (const [l, r] of Object.entries(next)) {
      if (r === rightId) delete next[l];
    }
    next[selected] = rightId;
    setLinks(next);
    setSelected(null);
  }

  async function submit() {
    const res = await onSubmit({ pairings: links });
    if (!res.is_correct) {
      // Gentle retry: clear the links, the child tries again.
      setLinks({});
      setSelected(null);
    }
  }

  const complete = Object.keys(links).length === pairs.length;

  const ring = (id: string) => {
    if (links[id] !== undefined) return accent[pairIndex[id] % accent.length];
    if (id === selected) return "ring-amber-400";
    return "ring-transparent";
  };

  return (
    <div className="w-full max-w-3xl mx-auto">
      <div className="flex gap-4 justify-center">
        {/* Left column — the animals / colours to name */}
        <div className="flex-1 max-w-[11rem] space-y-4">
          {pairs.map((p) => (
            <button
              key={p.left.id}
              onClick={() => tapLeft(p.left.id)}
              disabled={disabled}
              className={[
                "w-full animate-pop rounded-[2rem] bg-white shadow-lg border-4 border-transparent ring-4",
                "flex flex-col items-center gap-2 p-4 min-h-[9rem] transition-transform active:scale-95",
                "hover:-translate-y-1",
                ring(p.left.id),
              ].join(" ")}
            >
              <Visual visual={p.left.visual} size="text-5xl" />
              <span className="text-xl font-bold">{labelFor(lang, p.left)}</span>
            </button>
          ))}
        </div>

        {/* Right column — shuffled partners */}
        <div className="flex-1 max-w-[11rem] space-y-4">
          {rightOrder.map((r) => {
            const linkedLeft = Object.keys(links).find((l) => links[l] === r.id);
            return (
              <button
                key={r.id}
                onClick={() => tapRight(r.id)}
                disabled={disabled || !selected}
                className={[
                  "w-full animate-pop rounded-[2rem] bg-white shadow-lg border-4 border-transparent ring-4",
                  "flex flex-col items-center gap-2 p-4 min-h-[9rem] transition-transform active:scale-95",
                  "hover:-translate-y-1",
                  linkedLeft ? accent[pairIndex[linkedLeft] % accent.length] : "ring-transparent",
                  !selected && !linkedLeft ? "opacity-50" : "",
                ].join(" ")}
              >
                <Visual visual={r.visual} size="text-5xl" />
                <span className="text-xl font-bold">{labelFor(lang, r)}</span>
              </button>
            );
          })}
        </div>
      </div>

      {complete && (
        <div className="text-center mt-6">
          <button
            onClick={submit}
            disabled={disabled}
            className="text-2xl px-10 py-4 rounded-3xl bg-emerald-500 hover:bg-emerald-600 text-white font-bold shadow-lg animate-pop"
          >
            ✓
          </button>
        </div>
      )}
    </div>
  );
}
