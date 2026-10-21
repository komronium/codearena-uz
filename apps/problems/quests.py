"""Daily quests and the unified Olov (streak). Nothing is stored: a day counts as active when the user solved the
daily problem or did any one of the three quests that day, so each is read from what is already recorded (accepted
submissions, finished duels, "Tushundim" marks) and rejudges or deletions flow through by themselves.

A freeze is earned for every 7 active days in a row (at most MAX_FREEZES kept) and spends itself on a single missed
day, so one slip does not end a run. It is worked out by replaying the days, which keeps it deterministic."""
import datetime

from django.db.models import Case, Count, F, Q, When
from django.db.models.functions import TruncDate
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _t
from django.utils.translation import gettext as _t

MAX_FREEZES = 2
FREEZE_EVERY = 7
EASY_LEVELS = ("beginner", "easy")


def quest_dates(user, since: datetime.date | None = None) -> dict[str, set[datetime.date]]:
    """Quest key -> the days (local) it was done."""
    from apps.classroom.models import Duel
    from apps.learn.models import PlanRead
    from apps.classroom.duel_badges import MIN_LOSER_ANSWERS
    from apps.submissions.models import UserProblemSolved

    def days(qs, field):
        qs = qs.annotate(d=TruncDate(field))
        if since:
            qs = qs.filter(d__gte=since)
        return set(qs.values_list("d", flat=True).distinct())

    won_at = Case(When(challenger=user, then="ends_at"), default="opponent_ends_at")
    # only a FIRST accepted solve counts (a re-submit, a contest AC and a virtual run do not make a day), and a duel
    # win only when the loser really played (answered at least MIN_LOSER_ANSWERS questions)
    answered_by_other = Count("answers", filter=Q(answers__answered_at__isnull=False) & ~Q(answers__user=user))
    return {
        "easy": days(UserProblemSolved.objects.filter(user=user, problem__difficulty__in=EASY_LEVELS)
                     .annotate(first_at=F("first_ac_submission__created")), "first_at"),
        "duel": days(Duel.objects.filter(winner=user, status=Duel.Status.FINISHED).annotate(won_at=won_at)
                     .annotate(played=answered_by_other).filter(played__gte=MIN_LOSER_ANSWERS), "won_at"),
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
        {"key": "easy", "title": _t("Easy masala yeching"), "hint": _t("Beginner yoki Easy darajali bitta masala"), "icon": "code",
         "href": reverse("problems:list") + "?difficulty=easy&status=new", "done": today in found["easy"]},
        {"key": "duel", "title": _t("Duelda g‘alaba qozoning"), "hint": "1 ga 1 savollar duelida yuting", "icon": "swords",
         "href": reverse("classroom:duels"), "done": today in found["duel"]},
        {"key": "course", "title": _t("Kurs nazariyasini o‘qing"), "hint": "Kursda «Tushundim»ni bosing", "icon": "book-open",
         "href": reverse("learn:hub"), "done": today in found["course"]},
    ]
    done = sum(r["done"] for r in rows)
    return {"rows": rows, "done": done, "total": len(rows), "safe": bool(done) or daily_done}
