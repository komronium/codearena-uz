"""Solved problems per level, and the figure drawn from them (the problem list's side card, the home
page)."""
from django.db.models import Count

from apps.submissions.models import UserProblemSolved

from .models import Problem
from .skills import open_problems


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


def level_tops(user) -> dict:
    """How far ahead of the other solvers `user` is: for each level (and "all"), the whole percent of the people who have
    solved something who solved fewer problems there. {} when nobody else has solved anything."""
    rows = (UserProblemSolved.objects.filter(problem__in=open_problems(), user__is_active=True, user__is_staff=False)
            .order_by().values("user_id", "problem__difficulty").annotate(n=Count("id")))
    per: dict[int, dict[str, int]] = {}
    for r in rows:
        per.setdefault(r["user_id"], {})[r["problem__difficulty"]] = r["n"]
    others = [lv for uid, lv in per.items() if uid != user.pk]
    if not others:
        return {}
    mine = per.get(user.pk, {})

    def ahead(count_of):
        mine_n = count_of(mine)
        return round(100 * sum(1 for lv in others if count_of(lv) < mine_n) / len(others))

    tops = {v: ahead(lambda lv, v=v: lv.get(v, 0)) for v, _ in Problem.Difficulty.choices}
    tops["all"] = ahead(lambda lv: sum(lv.values()))
    return tops


def solved_ring(levels, user=None) -> dict | None:
    """What problems/_solved_ring.html draws: a segment per level (as wide as the level's share of the problems, filled as
    far as it is solved) and the total. With `user`, each also carries `top`: the percent of other solvers they are ahead of."""
    total = sum(lv["total"] for lv in levels)
    if not total:
        return None
    done = sum(lv["done"] for lv in levels)
    tops = level_tops(user) if user is not None else {}
    return {"segments": [{**lv, "i": i, "pct": _pct(lv["done"], lv["total"]), "top": tops.get(lv["value"])}
                         for i, lv in enumerate(levels)],
            "done": done, "total": total, "pct": _pct(done, total), "top": tops.get("all")}
