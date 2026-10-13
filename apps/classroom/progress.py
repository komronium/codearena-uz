"""Homework status per student and problem, read straight from submissions."""
from apps.contests.standings import PENALIZED
from apps.submissions.models import Submission


def cell(subs, deadline) -> dict:
    """subs: one user's submissions of one problem, oldest first."""
    ac = next((s for s in subs if s.verdict == Submission.Verdict.AC), None)
    before = [s for s in subs if ac is None or s.created < ac.created]
    tries = sum(1 for s in before if s.verdict in PENALIZED)
    if ac is None:
        return {"status": "tried" if subs else "none", "tries": tries, "at": None}
    return {"status": "ok" if ac.created <= deadline else "late", "tries": tries, "at": ac.created}


def grid(assignment) -> list[dict]:
    """One row per group member: cells in problem order, sorted by on-time solves."""
    problems = [ap.problem for ap in assignment.assignment_problems.select_related("problem")]
    members = list(assignment.group.members.order_by("username"))
    subs = {}
    for s in (Submission.objects.filter(user__in=members, problem__in=problems)
              .only("user_id", "problem_id", "verdict", "created").order_by("created", "id")):
        subs.setdefault((s.user_id, s.problem_id), []).append(s)
    rows = []
    for u in members:
        cells = [cell(subs.get((u.pk, p.pk), []), assignment.deadline) for p in problems]
        rows.append({"user": u, "cells": cells,
                     "on_time": sum(c["status"] == "ok" for c in cells),
                     "solved": sum(c["status"] in ("ok", "late") for c in cells),
                     "tried": sum(c["status"] != "none" for c in cells),
                     "finished": bool(cells) and all(c["status"] in ("ok", "late") for c in cells)})
    rows.sort(key=lambda r: (-r["on_time"], -r["solved"], -r["tried"], r["user"].username))
    return rows


def completion(assignments) -> dict[int, tuple[int, int]]:
    """For each assignment: (students who solved every problem, students in the group). Late solves count."""
    from django.db.models import Count
    out = {}
    for a in assignments:
        pids = [ap.problem_id for ap in a.assignment_problems.all()]
        members = list(a.group.members.values_list("pk", flat=True))
        if not pids or not members:
            out[a.pk] = (0, len(members))
            continue
        rows = (Submission.objects.filter(user_id__in=members, problem_id__in=pids, verdict=Submission.Verdict.AC)
                .values("user_id").annotate(n=Count("problem_id", distinct=True)))
        out[a.pk] = (sum(1 for r in rows if r["n"] == len(pids)), len(members))
    return out
