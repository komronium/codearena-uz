"""The daily problem: one open problem a day for everyone, a streak for solving it on
its day, and a small practice-points bonus per such day."""
import datetime
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


def week_strip(user) -> list[dict]:
    """This week, Monday to Sunday: which days' daily problem the user solved on its day."""
    today = timezone.localdate()
    monday = today - datetime.timedelta(days=today.weekday())
    days = [monday + datetime.timedelta(days=i) for i in range(7)]
    done = set(DailySolve.objects.filter(user=user, daily__date__range=(days[0], days[-1]))
               .values_list("daily__date", flat=True))
    return [{"label": WEEKDAYS_SHORT[i], "date": d, "done": d in done, "today": d == today, "future": d > today}
            for i, d in enumerate(days)]
