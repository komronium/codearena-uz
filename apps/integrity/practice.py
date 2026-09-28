"""Practice solves that look copied from an AI, for the teacher's report.

Each practice AC (the first one, UserProblemSolved) is checked two ways.

What the browser reported (PracticeEvent) — can be switched off, so it only adds weight:
- paste: a long paste or drop into the editor was tried (blocked on Beginner/Easy);
- bulk: a large block of code appeared at once, or faster than anyone types;
- away then quick: 20 s+ in another window, and the AC within 3 minutes of coming back —
  the "ask the AI, come back, type it in" shape;
- too fast: solved sooner after opening the page than a read-think-type pass allows.

What the server knows on its own — blocking the script doesn't hide it:
- no tracking: the AC came with no sign of the problem page ever being open (script blocked,
  or the code sent from outside the site);
- not written here: the page was open, yet the accepted code never was in its editor;
- jump: 150+ characters appeared between two of the editor's 10-second snapshots;
- similar: 90%+ the same as another student's accepted code (AI answers look alike).

Nothing here is proof; a teacher looks at the code and decides (PracticeReview). Two things
are enforced, not just reported: a practice submission is accepted only if that code was in the
site's editor (written_in_editor, checked by the submit view), and a new solve scoring AUTO_HOLD
or more earns no points until a teacher clears it (auto_hold, from refresh_solves).
"""
import datetime

from django.utils import timezone

from apps.problems.models import Problem
from apps.submissions.models import UserProblemSolved

from .models import PracticeEvent, PracticeReview, PracticeSnapshot
from .similarity import MIN_LINES, THRESHOLD, similarity

MIN_AWAY_MS = 20_000
QUICK_AFTER_RETURN = datetime.timedelta(minutes=3)
# first open to AC that a genuine attempt doesn't beat (beginner: none, those can be that quick)
SPEED_LIMIT = {Problem.Difficulty.EASY: 90, Problem.Difficulty.MEDIUM: 240, Problem.Difficulty.HARD: 420}
JUMP_CHARS = 150
SNAPSHOT_WINDOW = datetime.timedelta(minutes=10)
SIMILAR_CAP = 60  # most recent solves per problem compared pairwise
MIN_SCORE = 3
AUTO_HOLD = 8  # held without waiting for a teacher: e.g. code not written here, or paste + quick return
RECENT_CODE = datetime.timedelta(minutes=10)


def _fmt(seconds: float) -> str:
    s = int(seconds)
    return f"{s} soniya" if s < 60 else f"{s // 60} daq {s % 60} s"


def _norm(source: str) -> str:
    return "\n".join(line.rstrip() for line in source.strip().splitlines())


def _browser_reasons(solve, before) -> tuple[int, list[str]]:
    ac_at = solve.first_ac_submission.created
    score, why = 0, []
    pastes = sum(e.kind == PracticeEvent.Kind.PASTE for e in before)
    if pastes:  # on Medium/Hard pasting from one's own editor is normal: little weight there
        locked = solve.problem.difficulty in (Problem.Difficulty.BEGINNER, Problem.Difficulty.EASY)
        score += (3 if locked else 1) * min(pastes, 3)
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


def _server_reasons(solve, before, snaps) -> tuple[int, list[str]]:
    sub = solve.first_ac_submission
    if not any(e.kind == PracticeEvent.Kind.VIEW for e in before):
        return 6, ["kuzatuv ishlamagan: sahifa ochilgani ko‘rinmaydi (skript o‘chirilgan yoki kod tashqaridan yuborilgan)"]
    score, why = 0, []
    near = [s for s in snaps if sub.created - SNAPSHOT_WINDOW <= s.at <= sub.created + datetime.timedelta(minutes=1)]
    want = _norm(sub.source)
    if not any(_norm(s.source) == want or similarity(sub.source, s.source) >= THRESHOLD for s in near):
        score += 8
        why.append("qabul qilingan kod muharrirda yozilmagan")
    grew = max((len(b.source) - len(a.source) for a, b in zip(snaps, snaps[1:]) if b.at <= sub.created), default=0)
    if grew >= JUMP_CHARS:
        score += 4
        why.append(f"{grew} belgi birdaniga paydo bo‘lgan")
    return score, why


def _similar(solves) -> dict[int, tuple[str, int]]:
    """solve pk -> (other student's username, % alike) for the closest match 90%+ on the same problem."""
    by_problem: dict[int, list] = {}
    for s in solves:
        if s.problem.difficulty != Problem.Difficulty.BEGINNER and len(s.first_ac_submission.source.strip().splitlines()) >= MIN_LINES:
            by_problem.setdefault(s.problem_id, []).append(s)
    best: dict[int, tuple[str, int]] = {}
    for group in by_problem.values():
        group = sorted(group, key=lambda s: s.first_ac_submission.created)[-SIMILAR_CAP:]
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                if a.user_id == b.user_id:
                    continue
                score = similarity(a.first_ac_submission.source, b.first_ac_submission.source)
                if score >= THRESHOLD:
                    pct = round(score * 100)
                    for me, other in ((a, b), (b, a)):
                        if pct > best.get(me.pk, ("", 0))[1]:
                            best[me.pk] = (other.user.username, pct)
    return best


def written_in_editor(user, problem, source: str) -> bool:
    """Was this exact code in the site's editor lately? The page saves it right before submitting."""
    want = _norm(source)
    recent = PracticeSnapshot.objects.filter(user=user, problem=problem, at__gte=timezone.now() - RECENT_CODE)
    return any(_norm(s) == want for s in recent.values_list("source", flat=True))


def _assess(solve, events, snaps, similar, tracking_since) -> tuple[int, list[str]]:
    ac_at = solve.first_ac_submission.created
    before = [e for e in events if ac_at - datetime.timedelta(days=1) <= e.at <= ac_at]
    score, why = _browser_reasons(solve, before)
    if tracking_since and ac_at > tracking_since:
        more, more_why = _server_reasons(solve, before, snaps)
        score, why = score + more, why + more_why
    if solve.pk in similar:
        name, pct = similar[solve.pk]
        score += 6
        why.append(f"{name} yechimi bilan {pct}% bir xil")
    return score, why


def _trails(user_ids, problem_ids, since):
    events: dict[tuple[int, int], list] = {}
    for e in PracticeEvent.objects.filter(user_id__in=user_ids, problem_id__in=problem_ids, at__gte=since):
        events.setdefault((e.user_id, e.problem_id), []).append(e)
    snaps: dict[tuple[int, int], list] = {}
    for s in PracticeSnapshot.objects.filter(user_id__in=user_ids, problem_id__in=problem_ids).order_by("at", "id"):
        snaps.setdefault((s.user_id, s.problem_id), []).append(s)
    return events, snaps


def _tracking_since():
    # the server-side checks only mean something for solves made after tracking was deployed
    return PracticeEvent.objects.order_by("at").values_list("at", flat=True).first()


def auto_hold(problem_id: int, user_ids) -> None:
    """New practice solves of `problem_id`: hold the points of any that score AUTO_HOLD or more
    (a PracticeReview with no reviewer) until a teacher clears it."""
    solves = list(UserProblemSolved.objects.filter(problem_id=problem_id, user_id__in=list(user_ids),
                                                   first_ac_submission__contest__isnull=True)
                  .exclude(user__is_staff=True).select_related("user", "problem", "first_ac_submission"))
    if not solves:
        return
    reviewed = set(PracticeReview.objects.filter(problem_id=problem_id, user_id__in=[s.user_id for s in solves])
                   .values_list("user_id", flat=True))
    solves = [s for s in solves if s.user_id not in reviewed]
    if not solves:
        return
    peers = list(UserProblemSolved.objects.filter(problem_id=problem_id, first_ac_submission__contest__isnull=True)
                 .exclude(user__is_staff=True).select_related("user", "problem", "first_ac_submission")
                 .order_by("-first_ac_submission__created")[:SIMILAR_CAP])
    similar = _similar({s.pk: s for s in [*peers, *solves]}.values())
    since = min(s.first_ac_submission.created for s in solves) - datetime.timedelta(days=1)
    events, snaps = _trails({s.user_id for s in solves}, {problem_id}, since)
    tracking_since = _tracking_since()
    for s in solves:
        score, _ = _assess(s, events.get((s.user_id, problem_id), []), snaps.get((s.user_id, problem_id), []),
                           similar, tracking_since)
        if score >= AUTO_HOLD:
            PracticeReview.objects.get_or_create(user_id=s.user_id, problem_id=problem_id,
                                                 defaults={"confirmed": True, "reviewer": None})


def suspicious_solves(users, days: int = 30) -> list[dict]:
    """Flagged practice solves of `users` (a queryset) in the last `days`, most suspicious first;
    ones still waiting for a teacher (never looked at, or held automatically) on top."""
    since = timezone.now() - datetime.timedelta(days=days)
    solves = list(UserProblemSolved.objects.filter(user__in=users, first_ac_submission__created__gte=since,
                                                   first_ac_submission__contest__isnull=True)
                  .select_related("user", "problem", "first_ac_submission"))
    if not solves:
        return []
    user_ids, problem_ids = {s.user_id for s in solves}, {s.problem_id for s in solves}
    events, snaps = _trails(user_ids, problem_ids, since - datetime.timedelta(days=1))
    reviews = {(r.user_id, r.problem_id): r for r in
               PracticeReview.objects.filter(user_id__in=user_ids, problem_id__in=problem_ids)}
    similar, tracking_since = _similar(solves), _tracking_since()

    rows = []
    for s in solves:
        key = (s.user_id, s.problem_id)
        score, why = _assess(s, events.get(key, []), snaps.get(key, []), similar, tracking_since)
        review = reviews.get(key)
        if score >= MIN_SCORE or review is not None:
            rows.append({"solve": s, "score": score, "why": why, "review": review,
                         "waiting": review is None or review.reviewer_id is None})
    rows.sort(key=lambda r: (not r["waiting"], -r["score"], -r["solve"].first_ac_submission.created.timestamp()))
    return rows
