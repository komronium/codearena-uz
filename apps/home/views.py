"""/ : what to do next for a signed-in student, what CodeArena is for a guest."""
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.tiers import next_tier as _next_tier
from apps.classroom import duels
from apps.classroom.models import Assignment, Duel
from apps.contests.models import Contest, Participation
from apps.contests.views import _standings  # cached, the standings page's own numbers
from apps.problems.daily import daily_for, streaks, week_strip
from apps.problems.models import DailySolve, Language, Problem
from apps.problems.skills import next_problems, open_problems, shared_reason
from apps.submissions.models import Submission

from .context_processors import live_contest_for


_WEEKDAYS = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
_MONTHS = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]


def _rating_card(user) -> dict:
    """The rating block: the last rated change, the place among rated users, the next tier."""
    rated = Participation.objects.filter(rating_after__isnull=False)
    last = rated.filter(user=user).order_by("-contest__end").first()
    rated_users = User.objects.filter(is_active=True, participations__rating_after__isnull=False).distinct()
    return {
        "delta": last.rating_after - last.rating_before if last else None,
        "rank": rated_users.filter(rating__gt=user.rating).count() + 1 if last else None,
        "total": rated_users.count(),
        "next": _next_tier(user.rating),
    }


def _live(user, running) -> dict | None:
    """The running contest the navigation points at (yours first, else one you may enter), with
    your place and progress from its standings."""
    pick = live_contest_for(user)
    contest = pick and (next((c for c in running if c.pk == pick["pk"]), None)
                        or Contest.objects.filter(pk=pick["pk"]).first())
    if not contest:
        return None
    row = next((r for r in _standings(contest) if r["user"].pk == user.pk), None)
    return {"contest": contest, "joined": row is not None, "rank": row and row["rank"],
            "solved": row and row["solved"], "n_problems": contest.contest_problems.count()}


def home(request):
    now = timezone.now()
    daily = daily_for()
    contests = Contest.objects.annotate(n_participants=Count("participations"))  # contests/_row.html shows it
    running = list(contests.filter(start__lte=now, end__gt=now).order_by("end")[:3])
    upcoming = list(contests.filter(start__gt=now).order_by("start")[:3])
    if not request.user.is_authenticated:
        # the latest rated contest whose ratings are applied: its real top three, not a mock-up
        last_rated = (Contest.objects.filter(is_rated=True, end__lte=now, participations__rating_after__isnull=False)
                      .order_by("-end").distinct().first())
        podium = [r for r in _standings(last_rated) if not r["disqualified"]][:3] if last_rated else []
        return render(request, "home/landing.html", {
            "daily": daily, "running": running, "upcoming": upcoming,
            "last_rated": last_rated, "podium": podium,
            "languages": list(Language.objects.filter(is_active=True).order_by("id").values_list("name", flat=True)),
            "stats": {"problems": open_problems().count(), "users": User.objects.filter(is_active=True).count(),
                      "contests": Contest.objects.count(), "submissions": Submission.objects.count()},
        })

    user = request.user
    homework = list(Assignment.objects.filter(group__members=user, deadline__gt=now).select_related("group")
                    .prefetch_related("assignment_problems").order_by("deadline")[:3])
    solved = set(Submission.objects.filter(user=user, verdict=Submission.Verdict.AC).values_list("problem_id", flat=True))
    for a in homework:
        ids = [ap.problem_id for ap in a.assignment_problems.all()]
        a.my_total, a.my_solved = len(ids), sum(1 for i in ids if i in solved)
    duels.settle_open(user)
    mine = Duel.objects.filter(Q(challenger=user) | Q(opponent=user)).select_related("challenger", "opponent", "problem")
    live = list(mine.filter(status__in=duels.OPEN).exclude(status=Duel.Status.PENDING, opponent=user)[:3])
    for d in live:  # your own clock, if it still runs
        clock = d.clock(user.pk)
        d.my_end = clock[1] if clock and clock[1] > now else None
    current, best = streaks(user)
    next_picks = next_problems(user, exclude=(daily.problem_id,) if daily else ())
    today = timezone.localdate()
    return render(request, "home/dashboard.html", {
        "daily": daily,
        "daily_done": bool(daily) and DailySolve.objects.filter(user=user, daily=daily).exists(),
        "streak": current, "best_streak": best, "week": week_strip(user),
        # the profile's count: public problems solved (what the practice points are made of)
        "solved_count": Problem.objects.filter(userproblemsolved__user=user, is_public=True).count(),
        "homework": homework,
        "challenges": list(mine.filter(status=Duel.Status.PENDING, opponent=user)[:3]),
        "active_duels": live,
        "running": running, "upcoming": upcoming, "live": _live(user, running),
        "today_label": f"{_WEEKDAYS[today.weekday()]}, {today.day}-{_MONTHS[today.month - 1]}",
        "rating_card": _rating_card(user),
        "next_picks": next_picks, "picks_reason": shared_reason(next_picks),
        "recent": list(Submission.objects.filter(user=user).select_related("problem", "language")[:5]),
        "taught": list(Assignment.objects.filter(group__teacher=user).select_related("group")
                       .order_by("-deadline")[:3]),
    })


# staff tools, personal pages, sign-in plumbing and htmx/JSON endpoints: nothing a search should land on
_NOT_FOR_CRAWLERS = ["/moderation/", "/integrity/", "/submissions/", "/classroom/", "/django-rq/",
                     "/accounts/profile/edit/", "/accounts/password-", "/accounts/reset/", "/accounts/verify/",
                     "/accounts/logout/", "/accounts/teacher-request/", "/problems/suggest/", "/learn/search/"]


def robots_txt(request):
    lines = ["User-agent: *", *(f"Disallow: {path}" for path in _NOT_FOR_CRAWLERS),
             f"Sitemap: {request.build_absolute_uri(reverse('sitemap'))}"]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")
