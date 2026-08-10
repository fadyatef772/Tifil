"""Tracing type (تتبّع): the child finger-traces a large guide glyph (a
number, a letter, or a shape). This trains fine-motor skills — a core
therapy goal for children with Down syndrome.

*** IMPORTANT — READ THIS BEFORE USING THIS TYPE'S SCORING ***
This is MOTOR PRACTICE, not handwriting recognition. There is no OCR, no
shape classifier, and no claim that the trace "looks like" the glyph. The
validator runs a deliberately LENIENT, completion-based coverage heuristic:

  * The guide is a polyline in a 0..100 coordinate space
    (`options["guide"]`: list of {"x","y"}).
  * The child's trace is normalized to that same space.
  * A guide sample point counts as "reached" when it lies within
    `settings.tracing_proximity_radius` units of some traced point.
  * The trace is correct when at least `settings.tracing_coverage_threshold`
    of the guide points are reached, and the trace has at least
    `settings.tracing_min_points` points.

A child who wanders near the shape and covers enough of it passes — that is
the intent (celebrate the motor effort), and it is exactly why we call it a
coverage check and NOT recognition. A real handwriting-recognition engine is
a separate, future feature.

Data in `options`:
  {
    "glyph": "circle",                 # machine id (numbers/letters/shapes)
    "visual": "⭕",                     # big decorative glyph for the child
    "guide": [{"x": 20.0, "y": 50.0}, ...]   # 0..100 coordinate space
  }

Answer contract: `{"answer": {"points": [{"x": .., "y": ..}, ...]}}`.
"""

from app.core.config import settings
from app.services.exercise_types.base import ExerciseType


def _sample(points: list, limit: int) -> list:
    """Evenly downsample a long trace so scoring stays cheap."""
    if len(points) <= limit:
        return points
    step = (len(points) + limit - 1) // limit
    return points[::step]


def _to_points(points: list) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for p in _sample(points, settings.tracing_max_points):
        if isinstance(p, dict):
            out.append((float(p["x"]), float(p["y"])))
        elif isinstance(p, (list, tuple)) and len(p) >= 2:
            out.append((float(p[0]), float(p[1])))
    return out


def coverage_fraction(guide: list, traced: list) -> float:
    """Fraction of guide sample points reached by the trace (0..1)."""
    guide_pts = _to_points(guide)
    traced_pts = _to_points(traced)
    if not guide_pts or not traced_pts:
        return 0.0
    radius2 = settings.tracing_proximity_radius ** 2
    reached = 0
    for gx, gy in guide_pts:
        min_d2 = min((gx - tx) ** 2 + (gy - ty) ** 2 for tx, ty in traced_pts)
        if min_d2 <= radius2:
            reached += 1
    return reached / len(guide_pts)


class TracingType(ExerciseType):
    key = "tracing"

    def serialize_for_child(self, exercise) -> dict:
        opts = exercise.options
        return {
            "glyph": opts.get("glyph", ""),
            "visual": opts.get("visual", ""),
            "guide": opts.get("guide", []),
        }

    def validate(self, exercise, payload) -> bool:
        if payload.answer is None:
            return False
        if isinstance(payload.answer, dict):
            points = payload.answer.get("points")
        else:
            points = payload.answer
        if not isinstance(points, list) or len(points) < settings.tracing_min_points:
            return False
        guide = exercise.options["guide"]
        return coverage_fraction(guide, points) >= settings.tracing_coverage_threshold
