"""Per-tag progress and the "next problem" pick, from the public catalog."""
from collections import Counter

from django.db.models import Count
from django.utils import timezone

from apps.submissions.models import UserProblemSolved

from .models import Problem, Tag

LEVELS = [Problem.Difficulty.BEGINNER, Problem.Difficulty.EASY, Problem.Difficulty.MEDIUM, Problem.Difficulty.HARD]
MIN_TAG_PROBLEMS = 3  # a tag this small says little about what you can't do yet


def open_problems():
    """Public, approved, and not held by a running or upcoming contest."""
    now = timezone.now()
    return (Problem.objects.filter(is_public=True, status=Problem.Status.APPROVED)
            .exclude(contests__end__gt=now).distinct())


def skill_map(user) -> list[dict]:
    solved = set(UserProblemSolved.objects.filter(user=user).values_list("problem_id", flat=True))
    rows = []
    tags = (Tag.objects.filter(problem__in=open_problems()).distinct()
            .prefetch_related("problem_set").order_by("name"))
    open_ids = set(open_problems().values_list("id", flat=True))
    for tag in tags:
        ids = {p.id for p in tag.problem_set.all()} & open_ids
        done = len(ids & solved)
        rows.append({"tag": tag, "solved": done, "total": len(ids), "pct": round(100 * done / len(ids))})
    rows.sort(key=lambda r: (-r["total"], r["tag"].name))
    return rows


def shared_reason(picks) -> str:
    """The weak topic all the picks came from, if it's one: then it's said once, not per pick."""
    reasons = {reason for _, reason in picks}
    return reasons.pop() if len(reasons) == 1 else ""


def next_problems(user, n: int = 3, exclude: tuple[int, ...] = ()) -> list[tuple[Problem, str]]:
    """(problem, reason) picks: unsolved problems of the weakest tags first, at the
    difficulty the user solves most, then one step up, then one step down (so a user at
    the top level still gets a full set), most-solved first."""
    solved = set(UserProblemSolved.objects.filter(user=user).values_list("problem_id", flat=True))
    done_levels = Counter(Problem.objects.filter(pk__in=solved).values_list("difficulty", flat=True))
    level = LEVELS.index(done_levels.most_common(1)[0][0]) if done_levels else 1
    rank = {LEVELS[i]: r for r, i in enumerate((level, level + 1, level - 1)) if 0 <= i < len(LEVELS)}
    candidates = list(open_problems().filter(difficulty__in=rank).exclude(pk__in=solved).exclude(pk__in=exclude)
                      .annotate(solvers=Count("userproblemsolved", distinct=True)).prefetch_related("tags"))
    candidates.sort(key=lambda p: (rank[p.difficulty], -p.solvers, p.pk))

    weak = [r for r in skill_map(user) if r["total"] >= MIN_TAG_PROBLEMS and r["solved"] < r["total"]]
    weak.sort(key=lambda r: (r["solved"] / r["total"], -r["total"]))
    picks: list[tuple[Problem, str]] = []
    taken = set()
    for row in weak:
        for p in candidates:
            if len(picks) == n:
                return picks
            if p.pk not in taken and any(t.pk == row["tag"].pk for t in p.tags.all()):
                picks.append((p, row["tag"].name))
                taken.add(p.pk)
    for p in candidates:  # no weak tag left: just the next ones at your level
        if len(picks) == n:
            break
        if p.pk not in taken:
            picks.append((p, ""))
            taken.add(p.pk)
    return picks


