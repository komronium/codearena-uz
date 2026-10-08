"""The daily problem: one open problem a day for everyone, a streak for solving it on
its day, and a small practice-points bonus per such day."""
import datetime
import hashlib
import random

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import DailyProblem, DailySolve, Problem
from .skills import open_problems

DAILY_BONUS = 5
FRESH_DAYS = 60  # a problem isn't the daily problem twice within this many days
D = Problem.Difficulty
WEEKDAY_LEVEL = [D.EASY, D.EASY, D.MEDIUM, D.EASY, D.MEDIUM, D.HARD, D.BEGINNER]  # Monday first


def daily_for(day: datetime.date | None = None) -> DailyProblem | None:
    """The day's problem, picked on first need; None when the catalog is empty."""
    day = day or timezone.localdate()
    existing = DailyProblem.objects.filter(date=day).select_related("problem").first()
    if existing:
        return existing
    window = (day - datetime.timedelta(days=FRESH_DAYS), day + datetime.timedelta(days=FRESH_DAYS))
    recent = DailyProblem.objects.filter(date__range=window).values("problem_id")
    pool = open_problems().exclude(pk__in=recent)
    ids = (sorted(pool.filter(difficulty=WEEKDAY_LEVEL[day.weekday()]).values_list("pk", flat=True))
           or sorted(pool.values_list("pk", flat=True))
           or sorted(open_problems().values_list("pk", flat=True)))
    if not ids:
        return None
    pick = random.Random(day.toordinal()).choice(ids)  # the same pick whoever asks first
    try:
        with transaction.atomic():
            DailyProblem.objects.create(date=day, problem_id=pick)
    except IntegrityError:
        pass  # a concurrent request made it first
    return DailyProblem.objects.select_related("problem").get(date=day)


def daily_candidates(day: datetime.date, count: int = 5) -> list[Problem]:
    """Stable, varied choices for staff scheduling a future daily problem.

    Prefer the weekday's usual difficulty, fill any shortfall from other levels, and
    avoid problems used within the freshness window. If the catalog is exhausted, allow
    repeats just as the automatic picker does.
    """
    window = (
        day - datetime.timedelta(days=FRESH_DAYS),
        day + datetime.timedelta(days=FRESH_DAYS),
    )
    recent = DailyProblem.objects.filter(date__range=window).exclude(date=day).values("problem_id")
    pool = open_problems().exclude(pk__in=recent)
    rows = list(pool.order_by("pk").values_list("pk", "difficulty"))
    preferred = [pk for pk, difficulty in rows if difficulty == WEEKDAY_LEVEL[day.weekday()]]
    all_ids = [pk for pk, _difficulty in rows]
    preferred_set = set(preferred)
    fallback = [pk for pk in all_ids if pk not in preferred_set]
    if not all_ids:
        fallback = list(open_problems().order_by("pk").values_list("pk", flat=True))
    if not preferred and not fallback:
        return []
    # Hash ordering is stable across workers and page refreshes, unlike process-randomized hash().
    order = lambda pk: hashlib.sha256(f"{day.isoformat()}:{pk}".encode()).digest()
    preferred.sort(key=order)
    fallback.sort(key=order)
    chosen = (preferred + fallback)[:count]
    by_id = Problem.objects.filter(pk__in=chosen).select_related("author").prefetch_related("tags")
    problems = {problem.pk: problem for problem in by_id}
    return [problems[pk] for pk in chosen]


def _day_bounds(day: datetime.date):
    start = timezone.make_aware(datetime.datetime.combine(day, datetime.time.min))
    return start, start + datetime.timedelta(days=1)


def refresh_daily(problem_id: int, user_ids) -> None:
    """Make DailySolve rows follow the practice ACs on each day `problem_id` was the
    daily problem, for `user_ids` (None = everyone)."""
    from apps.submissions.models import Submission

    for daily in DailyProblem.objects.filter(problem_id=problem_id):
        start, end = _day_bounds(daily.date)
        acs = Submission.objects.filter(problem_id=problem_id, contest__isnull=True,
                                        verdict=Submission.Verdict.AC, created__gte=start, created__lt=end)
        rows = DailySolve.objects.filter(daily=daily)
        if user_ids is not None:
            acs, rows = acs.filter(user_id__in=user_ids), rows.filter(user_id__in=user_ids)
        want = set(acs.values_list("user_id", flat=True))
        have = set(rows.values_list("user_id", flat=True))
        rows.filter(user_id__in=have - want).delete()
        DailySolve.objects.bulk_create([DailySolve(user_id=u, daily=daily) for u in want - have],
                                       ignore_conflicts=True)


def streaks(user) -> tuple[int, int]:
    """(current, best) runs of consecutive days solved. Today not solved yet keeps
    yesterday's run alive."""
    days = set(DailySolve.objects.filter(user=user).values_list("daily__date", flat=True))
    best = run = 0
    prev = None
    for d in sorted(days):
        run = run + 1 if prev is not None and d - prev == datetime.timedelta(days=1) else 1
        best, prev = max(best, run), d
    today = timezone.localdate()
    cur, d = 0, today if today in days else today - datetime.timedelta(days=1)
    while d in days:
        cur, d = cur + 1, d - datetime.timedelta(days=1)
    return cur, best


WEEKDAYS_SHORT = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]
MONTHS = "Yanvar Fevral Mart Aprel May Iyun Iyul Avgust Sentabr Oktabr Noyabr Dekabr".split()


def week_strip(user) -> list[dict]:
    """This week, Monday to Sunday: which days' daily problem the user solved on its day."""
    today = timezone.localdate()
    monday = today - datetime.timedelta(days=today.weekday())
    days = [monday + datetime.timedelta(days=i) for i in range(7)]
    done = set(DailySolve.objects.filter(user=user, daily__date__range=(days[0], days[-1]))
               .values_list("daily__date", flat=True))
    return [{"label": WEEKDAYS_SHORT[i], "date": d, "done": d in done, "today": d == today, "future": d > today}
            for i, d in enumerate(days)]


def month_strip(user) -> dict:
    """This month as a calendar, Monday first and a week per row (with the neighbouring months' days to fill
    the rows): which days' daily problem the user solved on its day, and which day is today."""
    today = timezone.localdate()
    first = today.replace(day=1)
    last = (first + datetime.timedelta(days=32)).replace(day=1) - datetime.timedelta(days=1)
    start = first - datetime.timedelta(days=first.weekday())
    end = last + datetime.timedelta(days=6 - last.weekday())
    done = set(DailySolve.objects.filter(user=user, daily__date__range=(start, end))
               .values_list("daily__date", flat=True))
    days = [start + datetime.timedelta(days=i) for i in range((end - start).days + 1)]
    cells = [{"day": d.day, "date": d, "in_month": d.month == today.month, "done": d in done,
              "today": d == today, "future": d > today} for d in days]
    return {"label": f"{MONTHS[today.month - 1]}, {today.year}", "weekdays": WEEKDAYS_SHORT,
            "weeks": [cells[i:i + 7] for i in range(0, len(cells), 7)]}
