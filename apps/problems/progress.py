"""Solved problems per level, and LeetCode's horseshoe ring drawn from them (the problem list's side card, the home
page)."""
import math

from django.db.models import Count

from apps.submissions.models import UserProblemSolved

from .models import Problem


def level_progress(user, visible) -> list[dict]:
    """One {"value", "label", "done", "total"} per level that has open problems, out of `visible`."""
    totals = dict(visible.order_by().values("difficulty").annotate(n=Count("id", distinct=True))
                  .values_list("difficulty", "n"))
    done = dict(UserProblemSolved.objects.filter(user=user, problem__in=visible)
                .values("problem__difficulty").annotate(n=Count("id"))
                .values_list("problem__difficulty", "n"))
    return [{"value": v, "label": label, "done": done.get(v, 0), "total": totals[v]}
            for v, label in Problem.Difficulty.choices if totals.get(v)]


def solved_ring(levels, size=112, stroke=7) -> dict | None:
    """A horseshoe with a track per level (as long as the level has problems), each filled as far as solved.
    Only SVG dash numbers here; problems/_solved_card.html draws them."""
    total = sum(lv["total"] for lv in levels)
    if not total:
        return None
    c = size / 2
    r = c - stroke / 2 - 1
    circ = 2 * math.pi * r
    gap = stroke + 3  # the round caps eat into the gaps
    avail = circ * 0.75 - gap * (len(levels) - 1)
    off, segments = 0.0, []
    for lv in levels:
        length = avail * lv["total"] / total
        segments.append({**lv, "offset": f"{-off:.2f}", "track": f"{length:.2f} {circ:.2f}",
                         "fill": f"{length * lv['done'] / lv['total']:.2f} {circ:.2f}"})
        off += length + gap
    return {"size": size, "c": c, "r": f"{r:.2f}", "stroke": stroke, "segments": segments,
            "done": sum(lv["done"] for lv in levels), "total": total}
