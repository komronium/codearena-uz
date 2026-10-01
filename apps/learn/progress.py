"""Derived learn data (course progress, the course strip, the save menu), read from solves over
the problems a user may see right now, so rejudges, publishes, retags and newly hidden problems
show up without anything stored."""
from apps.problems.models import Problem
from apps.problems.skills import open_problems
from apps.submissions.models import UserProblemSolved

from .models import ProblemListItem, StudyPlan

LEVELS = Problem.Difficulty.values  # easiest first


def course_rows(plans) -> dict[int, list[tuple[int, str]]]:
    """Course id -> (problem id, difficulty) of its open problems: any of the course's tags,
    easiest first, then oldest first. A problem may sit in several courses."""
    courses_of: dict[int, list[int]] = {}
    for plan_id, tag_id in (StudyPlan.tags.through.objects.filter(studyplan__in=[p.pk for p in plans])
                            .values_list("studyplan_id", "tag_id")):
        courses_of.setdefault(tag_id, []).append(plan_id)
    found: dict[int, dict[int, str]] = {p.pk: {} for p in plans}
    for tag_id, problem_id, difficulty in (Problem.tags.through.objects
                                           .filter(tag_id__in=list(courses_of), problem__in=open_problems())
                                           .values_list("tag_id", "problem_id", "problem__difficulty")):
        for plan_id in courses_of[tag_id]:
            found[plan_id][problem_id] = difficulty
    rank = {v: i for i, v in enumerate(LEVELS)}
    return {plan_id: sorted(rows.items(), key=lambda r: (rank.get(r[1], len(LEVELS)), r[0]))
            for plan_id, rows in found.items()}


def plan_problem_ids(plans) -> dict[int, list[int]]:
    """Course id -> its open problems' ids, in course order."""
    return {plan_id: [i for i, _ in rows] for plan_id, rows in course_rows(plans).items()}


def solved_ids(user, ids) -> set[int]:
    if not user.is_authenticated:
        return set()
    return set(UserProblemSolved.objects.filter(user=user, problem_id__in=list(ids))
               .values_list("problem_id", flat=True))


def plan_progress(user, plans) -> dict[int, dict]:
    """Course id -> {"done", "total", "pct", "completed"}; a course with nothing open is never completed."""
    ids = plan_problem_ids(plans)
    solved = solved_ids(user, {i for v in ids.values() for i in v})
    out = {}
    for plan_id, pids in ids.items():
        done, total = len(solved.intersection(pids)), len(pids)
        out[plan_id] = {"done": done, "total": total, "pct": round(100 * done / total) if total else 0,
                        "completed": total > 0 and done == total}
    return out


def plan_sections(user, plans) -> dict[int, dict]:
    """Course id -> {"sections": one {"level", "label", "done", "total", "complete"} per
    difficulty that has open problems, easiest first; "next_id": the first unsolved problem
    or None}. Drives the course card's dots and the "Keyingi" button."""
    rows = course_rows(plans)
    solved = solved_ids(user, {i for r in rows.values() for i, _ in r})
    labels = dict(Problem.Difficulty.choices)
    out = {}
    for plan_id, problems in rows.items():
        sections: dict[str, dict] = {}
        next_id = None
        for problem_id, level in problems:
            s = sections.setdefault(level, {"level": level, "label": labels.get(level, level), "done": 0, "total": 0})
            s["total"] += 1
            if problem_id in solved:
                s["done"] += 1
            elif next_id is None:
                next_id = problem_id
        for s in sections.values():
            s["complete"] = s["done"] == s["total"]
        out[plan_id] = {"sections": list(sections.values()), "next_id": next_id}
    return out


def plan_nav(user, plan_slug: str, problem_id: int) -> dict | None:
    """The course strip on a problem page opened from a course (?plan=<slug>): the course, its
    progress, and the open problems before and after this one. None when the slug is
    unknown, the course is hidden from this user, or the problem is not open in it."""
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
