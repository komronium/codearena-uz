from apps.submissions.models import Submission

from .models import Contest, VoidedProblem

# Only a judged wrong answer is a wrong try: compile errors and submissions still in
# the queue cost no penalty and are not shown as tries.
PENALIZED = {"WA", "TLE", "MLE", "RE", "OLE"}


def elapsed(minutes: int) -> str:
    """Minutes from the start as Codeforces prints a solve time: hh:mm."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def counts_as_wrong(contest, sub) -> bool:
    """A rejected try that costs. Codeforces' rules (cf and icpc) also forgive a failure on
    test 1, the statement's example; points contests keep the rule they were played under."""
    return sub.verdict in PENALIZED and (contest.type == Contest.Type.SCORE or sub.passed > 0)


def problem_points(contest, points: int, minutes: int, wrong: int) -> int:
    """What a solve is worth. Codeforces: max(0.3x, x - floor(120xt / 250d) - 50w), so the
    value falls to 52% by the end of a contest of d minutes, each wrong try costs 50 and nothing
    drops below 30%. ICPC counts solved problems; a points contest gives the full points."""
    if contest.type == Contest.Type.CF:
        d = max(1, int((contest.end - contest.start).total_seconds()) // 60)
        return max(3 * points // 10, points - 120 * points * minutes // (250 * d) - 50 * wrong)
    return 1 if contest.type == Contest.Type.ICPC else points


def cell(contest, cp, subs, start) -> dict:
    """One participant's cell for one problem, from their submissions to it (oldest first),
    timed from `start`: the contest's, or a virtual run's."""
    ac = next((s for s in subs if s.verdict == "AC"), None)
    wrong = sum(1 for s in subs if (ac is None or s.created < ac.created) and counts_as_wrong(contest, s))
    if ac is None:
        return {"solved": False, "wrong": wrong, "minutes": None, "ac_at": None}
    minutes = int((ac.created - start).total_seconds()) // 60
    points = problem_points(contest, cp.points, minutes, wrong)
    # what the board prints: ICPC marks a solve "+" with the wrong tries before it, the rest their points
    mark = (f"+{wrong}" if wrong else "+") if contest.type == Contest.Type.ICPC else str(points)
    return {"solved": True, "wrong": wrong, "minutes": minutes, "ac_at": ac.created,
            "time": elapsed(minutes), "points": points, "mark": mark}


def totals(contest, cells) -> tuple[int, int, int]:
    """(score, penalty, solved) of one row. Penalty: minutes to each solve plus the contest's
    minutes per wrong try before it; none under Codeforces rules, where tries cost points."""
    solved = [c for c in cells if c["solved"]]
    per_try = contest.wrong_try_minutes
    penalty = 0 if per_try is None else sum(c["minutes"] + per_try * c["wrong"] for c in solved)
    return sum(c["points"] for c in solved), penalty, len(solved)


def compute_standings(contest):
    """The board's rows, best first, by the contest's rules (Contest.Type): the higher score,
    then the lower penalty. Under ICPC the score is the number solved; under Codeforces rules
    the penalty is always 0, so equal points share a place."""
    problems = list(contest.contest_problems.select_related("problem"))
    participations = list(contest.participations.select_related("user"))

    subs_by_user_problem = {}
    for cp in problems:
        for s in Submission.objects.filter(contest=contest, problem=cp.problem).order_by("created"):
            subs_by_user_problem.setdefault((s.user_id, cp.id), []).append(s)

    # a voided problem counts as untried; a penalty strike counts as one wrong try
    # (the cancelled solution returned as a failed attempt) and is blocked from
    # resubmission; the participant still took part (attempted, below)
    voided = set(VoidedProblem.objects.filter(participation__contest=contest)
                 .values_list("participation_id", "contest_problem_id"))
    penalties = set(VoidedProblem.objects.filter(participation__contest=contest, penalty=True)
                    .values_list("participation_id", "contest_problem_id"))
    rows = []
    for p in participations:
        cells = []
        for cp in problems:
            void = (p.pk, cp.id) in voided
            penalty = (p.pk, cp.id) in penalties
            subs = subs_by_user_problem.get((p.user_id, cp.id), [])
            if penalty:
                # the struck solution is gone; the participant's other tries stay
                subs = [s for s in subs if s.verdict != "AC"]
            elif void:
                subs = []
            c = cell(contest, cp, subs, contest.start)
            if penalty:
                c["wrong"] += 1  # the cancelled solution, returned as a wrong try
            cells.append(c | {"voided": void, "penalty": penalty})
        score, penalty, solved = totals(contest, cells)
        delta = None
        if p.rating_after is not None and p.rating_before is not None:
            delta = p.rating_after - p.rating_before
        attempted = any(subs_by_user_problem.get((p.user_id, cp.id)) for cp in problems)
        # Out of the contest's division: on the board, never rated. Judged by the rating it
        # was rated from once applied, so a later climb doesn't relabel an old result.
        out = not contest.rates(p.user.rating if p.rating_before is None else p.rating_before)
        rows.append({"participation": p, "user": p.user, "solved": solved, "penalty": penalty,
                     "score": score, "cells": cells, "rating_delta": delta,
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
