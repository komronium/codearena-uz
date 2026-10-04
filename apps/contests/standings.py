from apps.submissions.models import Submission

# Only a judged wrong answer is a wrong try: compile errors and submissions still in
# the queue cost no penalty and are not shown as tries.
PENALIZED = {"WA", "TLE", "MLE", "RE", "OLE"}


def elapsed(minutes: int) -> str:
    """Minutes from the start as Codeforces prints a solve time: hh:mm."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def compute_standings(contest):
    """Score = sum of ContestProblem.points for solved problems; ties broken by
    penalty = minutes to first AC + 20 * wrong attempts, over solved problems
    (the ICPC rule). Equal points per problem reproduce plain ICPC ranking."""
    problems = list(contest.contest_problems.select_related("problem"))
    participations = list(contest.participations.select_related("user"))

    subs_by_user_problem = {}
    for cp in problems:
        for s in Submission.objects.filter(contest=contest, problem=cp.problem).order_by("created"):
            subs_by_user_problem.setdefault((s.user_id, cp.id), []).append(s)

    rows = []
    for p in participations:
        solved = penalty = score = 0
        last_ac = None
        cells = []
        for cp in problems:
            subs = subs_by_user_problem.get((p.user_id, cp.id), [])
            ac = next((s for s in subs if s.verdict == "AC"), None)
            if ac is None:
                wrong = sum(1 for s in subs if s.verdict in PENALIZED)
                cells.append({"solved": False, "wrong": wrong, "minutes": None, "ac_at": None})
                continue
            wrong = sum(1 for s in subs if s.created < ac.created and s.verdict in PENALIZED)
            minutes = int((ac.created - contest.start).total_seconds()) // 60
            cells.append({"solved": True, "wrong": wrong, "minutes": minutes, "ac_at": ac.created,
                          "time": elapsed(minutes), "points": cp.points})
            solved += 1
            score += cp.points
            penalty += minutes + 20 * wrong
            if last_ac is None or ac.created > last_ac:
                last_ac = ac.created
        delta = None
        if p.rating_after is not None and p.rating_before is not None:
            delta = p.rating_after - p.rating_before
        attempted = any(subs_by_user_problem.get((p.user_id, cp.id)) for cp in problems)
        # Out of the contest's division: on the board, never rated. Judged by the rating it
        # was rated from once applied, so a later climb doesn't relabel an old result.
        out = not contest.rates(p.user.rating if p.rating_before is None else p.rating_before)
        rows.append({"participation": p, "user": p.user, "solved": solved, "penalty": penalty,
                     "score": score, "last_ac": last_ac, "cells": cells, "rating_delta": delta,
                     "disqualified": p.disqualified, "attempted": attempted, "out": out})

    # Disqualified participants always sort below everyone else: they keep their cells
    # for the record but take the last ranks, which is what makes their rating drop.
    def key(r): return (r["disqualified"], -r["score"], r["penalty"])
    rows.sort(key=key)
    # Equal results share a rank ("1, 1, 3"): the order between them is arbitrary,
    # so distinct ranks would hand out arbitrary rating deltas.
    for i, r in enumerate(rows, start=1):
        r["rank"] = i if i == 1 or key(r) != key(rows[i - 2]) else rows[i - 2]["rank"]

    for col in range(len(problems)):
        times = [r["cells"][col]["ac_at"] for r in rows if r["cells"][col]["solved"] and not r["disqualified"]]
        first_at = min(times) if times else None
        for r in rows:
            r["cells"][col]["first"] = first_at is not None and r["cells"][col]["ac_at"] == first_at

    return rows
