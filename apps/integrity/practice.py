"""Practice solves that look copied from an AI, for the teacher's report.

Each practice AC (the first one, UserProblemSolved) is checked against what the editor reported
for that student and problem before it:
- paste: a long paste or drop into the editor was tried (blocked on Beginner/Easy);
- bulk: a large block of code appeared at once, or faster than anyone types;
- away then quick: 20 s+ in another window, and the AC within 3 minutes of coming back —
  the "ask the AI, come back, type it in" shape;
- too fast: solved sooner after opening the page than a read-think-type pass allows.
Nothing here is proof; a teacher looks at the code and decides (PracticeReview).
"""
import datetime

from django.utils import timezone

from apps.problems.models import Problem
from apps.submissions.models import UserProblemSolved

from .models import PracticeEvent, PracticeReview

MIN_AWAY_MS = 20_000
QUICK_AFTER_RETURN = datetime.timedelta(minutes=3)
# first open to AC that a genuine attempt doesn't beat (beginner: none, those can be that quick)
SPEED_LIMIT = {Problem.Difficulty.EASY: 90, Problem.Difficulty.MEDIUM: 240, Problem.Difficulty.HARD: 420}
MIN_SCORE = 3


def _fmt(seconds: float) -> str:
    s = int(seconds)
    return f"{s} soniya" if s < 60 else f"{s // 60} daq {s % 60} s"


def _reasons(solve, events) -> tuple[int, list[str]]:
    ac_at = solve.first_ac_submission.created
    before = [e for e in events if e.at <= ac_at]
    score, why = 0, []
    pastes = sum(e.kind == PracticeEvent.Kind.PASTE for e in before)
    if pastes:
        score += 3 * min(pastes, 3)
        why.append(f"{pastes} marta uzun kod qo‘yishga urindi")
    if any(e.kind == PracticeEvent.Kind.BULK for e in before):
        score += 4
        why.append("kod bir zumda paydo bo‘ldi")
    back = [e for e in before if e.kind == PracticeEvent.Kind.AWAY and (e.away_ms or 0) >= MIN_AWAY_MS
            and ac_at - e.at <= QUICK_AFTER_RETURN]
    if back:
        e = max(back, key=lambda e: e.away_ms)
        score += 4
        why.append(f"{_fmt(e.away_ms / 1000)} boshqa oynada, qaytgach {_fmt((ac_at - e.at).total_seconds())} ichida yechdi")
    views = [e.at for e in before if e.kind == PracticeEvent.Kind.VIEW]
    limit = SPEED_LIMIT.get(solve.problem.difficulty)
    if views and limit and (ac_at - min(views)).total_seconds() < limit:
        score += 3
        why.append(f"sahifa ochilgach {_fmt((ac_at - min(views)).total_seconds())} ichida yechildi")
    return score, why


def suspicious_solves(users, days: int = 30) -> list[dict]:
    """Flagged practice solves of `users` (a queryset) in the last `days`, most suspicious first."""
    since = timezone.now() - datetime.timedelta(days=days)
    solves = list(UserProblemSolved.objects.filter(user__in=users, first_ac_submission__created__gte=since,
                                                   first_ac_submission__contest__isnull=True)
                  .select_related("user", "problem", "first_ac_submission"))
    if not solves:
        return []
    pairs = {(s.user_id, s.problem_id) for s in solves}
    events: dict[tuple[int, int], list] = {}
    for e in PracticeEvent.objects.filter(user_id__in={u for u, _ in pairs}, problem_id__in={p for _, p in pairs},
                                          at__gte=since - datetime.timedelta(days=1)):
        events.setdefault((e.user_id, e.problem_id), []).append(e)
    reviews = {(r.user_id, r.problem_id): r for r in
               PracticeReview.objects.filter(user_id__in={u for u, _ in pairs}, problem_id__in={p for _, p in pairs})}
    rows = []
    for s in solves:
        score, why = _reasons(s, events.get((s.user_id, s.problem_id), []))
        if score >= MIN_SCORE:
            rows.append({"solve": s, "score": score, "why": why, "review": reviews.get((s.user_id, s.problem_id))})
    rows.sort(key=lambda r: (r["review"] is not None, -r["score"], -r["solve"].first_ac_submission.created.timestamp()))
    return rows
