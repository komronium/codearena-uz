from apps.submissions.models import Submission


def compute_standings(contest):
    """Per spec §3: ICPC = solved desc, penalty asc (penalty = minutes to
    first AC + 20 * wrong attempts on solved problems). Score = sum of
    ContestProblem.points for solved problems, ties by last AC time."""
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
        for cp in problems:
            subs = subs_by_user_problem.get((p.user_id, cp.id), [])
            ac = next((s for s in subs if s.verdict == "AC"), None)
            if ac is None:
                continue
            solved += 1
            score += cp.points
            wrong = sum(1 for s in subs if s.created < ac.created and s.verdict != "AC")
            minutes = int((ac.created - contest.start).total_seconds() // 60)
            penalty += minutes + 20 * wrong
            if last_ac is None or ac.created > last_ac:
                last_ac = ac.created
        rows.append({"participation": p, "user": p.user, "solved": solved, "penalty": penalty,
                     "score": score, "last_ac": last_ac})

    if contest.type == contest.Type.ICPC:
        rows.sort(key=lambda r: (-r["solved"], r["penalty"]))
    else:
        rows.sort(key=lambda r: (-r["score"], r["last_ac"] or contest.end))
    for i, r in enumerate(rows, start=1):
        r["rank"] = i
    return rows
