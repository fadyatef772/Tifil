import { useRef, useState } from "react";
import type { ExerciseProps } from "./common";
import { t } from "../../i18n";

interface Pt {
  x: number;
  y: number;
}

// Tracing type (تتبّع): the child finger-traces the guide glyph. The trace
// is submitted as points in the same 0..100 space as the guide. This is
// motor practice — the backend scores it with a lenient coverage check,
// NOT handwriting recognition (see backend tracing.py).
export default function TracingExercise({ exercise, lang, disabled, onSubmit }: ExerciseProps) {
  const s = t[lang];
  const guide = (exercise.payload.guide as Pt[] | undefined) ?? [];
  const visual = (exercise.payload.visual as string | undefined) ?? "";
  const svgRef = useRef<SVGSVGElement | null>(null);
  const drawingRef = useRef(false);
  const traceRef = useRef<Pt[]>([]);
  const [points, setPoints] = useState<Pt[]>([]);

  const polyline = (pts: Pt[]) => pts.map((p) => `${p.x},${p.y}`).join(" ");

  function toSvgPoint(e: React.PointerEvent<SVGSVGElement>): Pt {
    const rect = svgRef.current!.getBoundingClientRect();
    return {
      x: Math.min(100, Math.max(0, ((e.clientX - rect.left) / rect.width) * 100)),
      y: Math.min(100, Math.max(0, ((e.clientY - rect.top) / rect.height) * 100)),
    };
  }

  function onPointerDown(e: React.PointerEvent<SVGSVGElement>) {
    if (disabled) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    drawingRef.current = true;
    traceRef.current = [toSvgPoint(e)];
    setPoints(traceRef.current);
  }

  function onPointerMove(e: React.PointerEvent<SVGSVGElement>) {
    if (!drawingRef.current || disabled) return;
    const p = toSvgPoint(e);
    const last = traceRef.current[traceRef.current.length - 1];
    if (last && Math.hypot(p.x - last.x, p.y - last.y) < 0.5) return;
    traceRef.current = [...traceRef.current, p];
    setPoints(traceRef.current);
  }

  async function finish() {
    drawingRef.current = false;
    if (disabled) return;
    const trace = traceRef.current;
    traceRef.current = [];
    setPoints([]);
    // Too short to judge: just start over, no pressure.
    if (trace.length < 5) return;
    await onSubmit({ points: trace });
  }

  return (
    <div className="w-full max-w-xl mx-auto">
      <svg
        ref={svgRef}
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        className="w-full aspect-square touch-none rounded-[2rem] bg-white shadow-lg"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={() => void finish()}
        onPointerCancel={() => void finish()}
        role="img"
        aria-label={s.trace}
      >
        {/* The glyph, faint, behind the trace */}
        <text
          x={50}
          y={54}
          textAnchor="middle"
          dominantBaseline="central"
          fontSize={44}
          opacity={0.12}
          aria-hidden
        >
          {visual}
        </text>
        {/* The guide the child traces over (dashed, easy to see) */}
        <polyline
          points={polyline(guide)}
          fill="none"
          stroke="#d6d3d1"
          strokeWidth={2.5}
          strokeDasharray="3 3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {/* The child's trace */}
        {points.length > 0 && (
          <polyline
            points={polyline(points)}
            fill="none"
            stroke="#10b981"
            strokeWidth={5}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}
      </svg>
      <p className="text-center text-xl text-stone-500 mt-4 font-medium">{s.trace}</p>
    </div>
  );
}
