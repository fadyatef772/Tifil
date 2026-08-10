import { useMemo, useState } from "react";
import type { ExerciseProps } from "./common";
import { labelFor, shuffle } from "./common";
import { Visual } from "./Visual";

interface SeqItem {
  id: string;
  label_ar: string;
  label_en: string;
  visual: string;
}

// Ordering type (ترتيب): the steps come shuffled; the child taps the first
// step, then the second, and so on. Tapping a filled slot sends that step
// back to the pool. Submits only when every slot is filled.
export default function SequencingExercise({ exercise, lang, disabled, onSubmit }: ExerciseProps) {
  const items = (exercise.payload.items as SeqItem[]) ?? [];
  const [chosen, setChosen] = useState<string[]>([]);

  // The pool order is decided once per exercise so the items don't jump
  // around while the child is deciding.
  const poolOrder = useMemo(() => shuffle(items), [items]);

  const pool = poolOrder.filter((item) => !chosen.includes(item.id));
  const complete = chosen.length === items.length;

  function pick(itemId: string) {
    if (disabled) return;
    setChosen((c) => [...c, itemId]);
  }

  function unpick(index: number) {
    if (disabled) return;
    setChosen((c) => c.filter((_, i) => i !== index));
  }

  async function submit() {
    const res = await onSubmit({ order: chosen });
    if (!res.is_correct) {
      // Gentle retry: send everything back to the pool.
      setChosen([]);
    }
  }

  const slotItem = (slotIndex: number) => items.find((i) => i.id === chosen[slotIndex]);

  return (
    <div className="w-full max-w-2xl mx-auto">
      {/* The numbered slots — tap a filled slot to undo it */}
      <div className="flex justify-center gap-3 mb-8">
        {items.map((_, slotIndex) => {
          const item = slotItem(slotIndex);
          return (
            <button
              key={slotIndex}
              onClick={() => item && unpick(slotIndex)}
              disabled={disabled || !item}
              className={[
                "w-28 h-28 rounded-[1.75rem] bg-white shadow-lg border-4 flex flex-col items-center justify-center gap-1",
                item
                  ? "border-emerald-400 animate-pop hover:-translate-y-1 transition-transform"
                  : "border-dashed border-stone-300",
              ].join(" ")}
            >
              {item ? (
                <>
                  <Visual visual={item.visual} size="text-4xl" />
                  <span className="text-base font-bold leading-tight text-center px-1">
                    {labelFor(lang, item)}
                  </span>
                </>
              ) : (
                <span className="text-3xl font-bold text-stone-300">{slotIndex + 1}</span>
              )}
            </button>
          );
        })}
      </div>

      {/* The shuffled pool — tap the next step */}
      <div className="flex flex-wrap justify-center gap-4">
        {pool.map((item) => (
          <button
            key={item.id}
            onClick={() => pick(item.id)}
            disabled={disabled}
            className="animate-pop rounded-[2rem] bg-white shadow-lg border-4 border-transparent flex flex-col items-center gap-2 p-5 min-h-[8rem] w-32 transition-transform active:scale-95 hover:-translate-y-1"
          >
            <Visual visual={item.visual} size="text-5xl" />
            <span className="text-lg font-bold text-center leading-tight">
              {labelFor(lang, item)}
            </span>
          </button>
        ))}
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
