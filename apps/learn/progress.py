"""Derived learn data (plan progress, the plan strip, the save menu), read from solves over the
problems a user may see right now, so rejudges, publishes and newly hidden problems show up
without anything stored."""
from apps.problems.skills import open_problems
from apps.submissions.models import UserProblemSolved

from .models import PlanItem, ProblemListItem


def plan_problem_ids(plans) -> dict[int, list[int]]:
    """Plan id -> its open problems' ids, in plan order (section, then item)."""
    out: dict[int, list[int]] = {p.pk: [] for p in plans}
    rows = (PlanItem.objects.filter(section__plan__in=list(out), problem__in=open_problems())
            .order_by("section__order", "section_id", "order", "id")
            .values_list("section__plan_id", "problem_id"))
    for plan_id, problem_id in rows:
        if problem_id not in out[plan_id]:
            out[plan_id].append(problem_id)
    return out


def solved_ids(user, ids) -> set[int]:
    if not user.is_authenticated:
        return set()
    return set(UserProblemSolved.objects.filter(user=user, problem_id__in=list(ids))
               .values_list("problem_id", flat=True))


def plan_progress(user, plans) -> dict[int, dict]:
    """Plan id -> {"done", "total", "pct", "completed"}; a plan with nothing open is never completed."""
    ids = plan_problem_ids(plans)
    solved = solved_ids(user, {i for v in ids.values() for i in v})
    out = {}
    for plan_id, pids in ids.items():
        done, total = len(solved.intersection(pids)), len(pids)
        out[plan_id] = {"done": done, "total": total, "pct": round(100 * done / total) if total else 0,
                        "completed": total > 0 and done == total}
    return out


def plan_sections(user, plans) -> dict[int, dict]:
    """Plan id -> {"sections": [{"done", "total", "complete"}, ...] in plan order, "next_id":
    the first unsolved open problem or None}; drives the section dots and the "Keyingi"
    button. Sections with no open problem yet are listed too, never complete."""
    from .models import PlanSection

    out: dict[int, dict] = {p.pk: {"sections": [], "next_id": None} for p in plans}
    by_section: dict[int, dict] = {}
    for plan_id, section_id in (PlanSection.objects.filter(plan__in=list(out))
                                .order_by("order", "id").values_list("plan_id", "id")):
        by_section[section_id] = {"done": 0, "total": 0, "complete": False}
        out[plan_id]["sections"].append(by_section[section_id])
    rows = list(PlanItem.objects.filter(section__plan__in=list(out), problem__in=open_problems())
                .order_by("section__order", "section_id", "order", "id")
                .values_list("section__plan_id", "section_id", "problem_id"))
    solved = solved_ids(user, {r[2] for r in rows})
    for plan_id, section_id, problem_id in rows:
        by_section[section_id]["total"] += 1
        if problem_id in solved:
            by_section[section_id]["done"] += 1
        elif out[plan_id]["next_id"] is None:
            out[plan_id]["next_id"] = problem_id
    for s in by_section.values():
        s["complete"] = s["total"] > 0 and s["done"] == s["total"]
    return out


def plan_nav(user, plan_slug: str, problem_id: int) -> dict | None:
    """The plan strip on a problem page opened from a plan (?plan=<slug>): the plan, its
    progress, and the open problems before and after this one. None when the slug is
    unknown, the plan is hidden from this user, or the problem is not open in it."""
    from apps.problems.models import Problem

    from .models import StudyPlan

    if not plan_slug:
        return None
    plans = StudyPlan.objects.all() if user.is_staff else StudyPlan.objects.filter(is_public=True)
    plan = plans.filter(slug=plan_slug).first()
    if plan is None:
        return None
    ids = plan_problem_ids([plan])[plan.pk]
    if problem_id not in ids:
        return None
    i = ids.index(problem_id)
    near = Problem.objects.in_bulk([x for x in (ids[i - 1] if i else None, ids[i + 1] if i + 1 < len(ids) else None)
                                    if x is not None])
    done = len(solved_ids(user, ids))
    return {"plan": plan, "done": done, "total": len(ids), "position": i + 1,
            "prev": near.get(ids[i - 1]) if i else None,
            "next": near.get(ids[i + 1]) if i + 1 < len(ids) else None}


def save_menu(user, problem) -> list | None:
    """The user's lists for the problem page's "Saqlash" menu, each with .has; None when
    the problem can't be saved (anonymous, or not an open problem)."""
    if not user.is_authenticated or not open_problems().filter(pk=problem.pk).exists():
        return None
    has = set(ProblemListItem.objects.filter(list__owner=user, problem=problem).values_list("list_id", flat=True))
    rows = list(user.problem_lists.all())
    for lst in rows:
        lst.has = lst.pk in has
    return rows
