"""Daily quests and the unified Olov (streak). Nothing is stored: a day counts as active when the user solved the
daily problem or did any one of the three quests that day, so each is read from what is already recorded (accepted
submissions, finished duels, "Tushundim" marks) and rejudges or deletions flow through by themselves.

A freeze is earned for every 7 active days in a row (at most MAX_FREEZES kept) and spends itself on a single missed
day, so one slip does not end a run. It is worked out by replaying the days, which keeps it deterministic."""
import datetime

from django.db.models import Case, When
from django.db.models.functions import TruncDate
from django.urls import reverse
from django.utils import timezone

MAX_FREEZES = 2
FREEZE_EVERY = 7
EASY_LEVELS = ("beginner", "easy")


def quest_dates(user, since: datetime.date | None = None) -> dict[str, set[datetime.date]]:
    """Quest key -> the days (local) it was done."""
    from apps.classroom.models import Duel
    from apps.learn.models import PlanRead
    from apps.submissions.models import Submission

    def days(qs, field):
        qs = qs.annotate(d=TruncDate(field))
        if since:
            qs = qs.filter(d__gte=since)
        return set(qs.values_list("d", flat=True).distinct())

    won_at = Case(When(challenger=user, then="ends_at"), default="opponent_ends_at")
    return {
        "easy": days(Submission.objects.filter(user=user, verdict=Submission.Verdict.AC,
                                               problem__difficulty__in=EASY_LEVELS), "created"),
        "duel": days(Duel.objects.filter(winner=user, status=Duel.Status.FINISHED).annotate(won_at=won_at), "won_at"),
        "course": days(PlanRead.objects.filter(user=user), "read_at"),
    }


def active_days(user) -> set[datetime.date]:
    from .models import DailySolve

    out = set(DailySolve.objects.filter(user=user).values_list("daily__date", flat=True))
    for found in quest_dates(user).values():
        out |= found
    return out


def streak_state(user) -> dict:
    """{"current", "best", "freezes", "frozen"}: the run through today (today still open keeps yesterday's alive),
    the best run, the freezes left and the days one covered."""
    days = sorted(active_days(user))
    today = timezone.localdate()
    one = datetime.timedelta(days=1)
    run = best = freezes = 0
    prev = None
    frozen: set[datetime.date] = set()
    for d in days:
        if prev is not None:
            gap = (d - prev).days
            if gap == 2 and freezes:
                freezes -= 1
                frozen.add(prev + one)
            elif gap > 1:
                run = 0
        run += 1
        best = max(best, run)
        if run % FREEZE_EVERY == 0:
            freezes = min(MAX_FREEZES, freezes + 1)
        prev = d
    current = 0
    if prev is not None:
        gap = (today - prev).days
        if gap <= 1:
            current = run
        elif gap == 2 and freezes:  # yesterday was missed: a freeze holds the run until today ends
            current, freezes = run, freezes - 1
            frozen.add(today - one)
    return {"current": current, "best": best, "freezes": freezes, "frozen": frozen}


def today_quests(user) -> dict:
    """The three quests with today's state, and whether the Olov is safe today."""
    from .daily import daily_for
    from .models import DailySolve

    today = timezone.localdate()
    since = today
    found = quest_dates(user, since=since)
    daily = daily_for()
    daily_done = bool(daily) and DailySolve.objects.filter(user=user, daily=daily).exists()
    rows = [
        {"key": "easy", "title": "Easy masala yeching", "hint": "Beginner yoki Easy darajali bitta masala", "icon": "code",
         "href": reverse("problems:list") + "?difficulty=easy&status=new", "done": today in found["easy"]},
        {"key": "duel", "title": "Duelda g‘alaba qozoning", "hint": "1 ga 1 savollar duelida yuting", "icon": "swords",
         "href": reverse("classroom:duels"), "done": today in found["duel"]},
        {"key": "course", "title": "Kurs nazariyasini o‘qing", "hint": "Kursda «Tushundim»ni bosing", "icon": "book-open",
         "href": reverse("learn:hub"), "done": today in found["course"]},
    ]
    done = sum(r["done"] for r in rows)
    return {"rows": rows, "done": done, "total": len(rows), "safe": bool(done) or daily_done}
