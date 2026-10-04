"""Virtual contests: replay a published contest on your own clock and see where you
would have placed among the real participants. Unrated."""
from apps.submissions.models import Submission

from .models import ContestProblem, Participation, VirtualParticipation
from .standings import cell, compute_standings, totals


def start_refusal(user, contest) -> str:
    """Why `user` can't start a virtual run of `contest`; "" when they can."""
    if contest.published_at is None:
        return "Musobaqa hali ochilmagan — virtual ishtirok nashrdan keyin mumkin."
    if Participation.objects.filter(user=user, contest=contest).exists():
        return "Siz bu musobaqada haqiqiy qatnashgansiz."
    if VirtualParticipation.objects.filter(user=user, contest=contest).exists():
        return "Virtual ishtirok bir marta."
    return ""


def active_virtual_for(user, problem):
    """The user's running virtual contest that includes `problem`, or None."""
    if not user.is_authenticated:
        return None
    contest_ids = ContestProblem.objects.filter(problem=problem).values("contest_id")
    for vp in VirtualParticipation.objects.filter(user=user, contest_id__in=contest_ids).select_related("contest"):
        if vp.is_running:
            return vp
    return None


def virtual_result(vp) -> dict:
    """Score, penalty and cells like the standings, by the contest's rules but timed from the
    virtual start, and the rank among the real, not disqualified participants."""
    contest = vp.contest
    problems = list(contest.contest_problems.select_related("problem"))
    subs = list(Submission.objects.filter(virtual=vp).order_by("created", "id"))
    cells = [{**cell(contest, cp, [s for s in subs if s.problem_id == cp.problem_id], vp.start), "cp": cp}
             for cp in problems]
    score, penalty, solved = totals(contest, cells)
    real = [r for r in compute_standings(contest) if not r["disqualified"] and r["attempted"]]
    rank = 1 + sum(1 for r in real if (-r["score"], r["penalty"]) < (-score, penalty))
    return {"score": score, "penalty": penalty, "solved": solved, "cells": cells, "rank": rank,
            "field": len(real), "running": vp.is_running, "end": vp.end}
