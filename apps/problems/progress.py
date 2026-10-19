"""Solved problems per level, and the figure drawn from them (the problem list's side card, the home
page)."""
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


def _pct(done, total) -> int:
    """Whole percent solved; a started level never reads 0%, an unfinished one never reads 100%."""
    if not total or not done:
        return 0
    return min(99 if done < total else 100, max(1, round(done * 100 / total)))


def solved_ring(levels) -> dict | None:
    """What problems/_solved_ring.html draws: a segment per level (its own percent solved, so a level of ten problems
    reads as plainly as one of a hundred) and the total."""
    total = sum(lv["total"] for lv in levels)
    if not total:
        return None
    done = sum(lv["done"] for lv in levels)
    return {"segments": [{**lv, "i": i, "pct": _pct(lv["done"], lv["total"])} for i, lv in enumerate(levels)],
            "done": done, "total": total, "pct": _pct(done, total)}
