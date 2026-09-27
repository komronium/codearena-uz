"""/ : what to do next for a signed-in student, what CodeArena is for a guest."""
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone

from apps.accounts.models import User
from apps.classroom.models import Assignment, Duel
from apps.contests.models import Contest
from apps.contests.views import _standings  # cached, the standings page's own numbers
from apps.problems.daily import daily_for, streaks, week_strip
from apps.problems.models import DailySolve, Language, Problem
from apps.problems.skills import next_problems, open_problems, shared_reason
from apps.submissions.models import Submission


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
    mine = Duel.objects.filter(Q(challenger=user) | Q(opponent=user)).select_related("challenger", "opponent", "problem")
    current, best = streaks(user)
    next_picks = next_problems(user, exclude=(daily.problem_id,) if daily else ())
    return render(request, "home/dashboard.html", {
        "daily": daily,
        "daily_done": bool(daily) and DailySolve.objects.filter(user=user, daily=daily).exists(),
        "streak": current, "best_streak": best, "week": week_strip(user),
        # the profile's count: public problems solved (what the practice points are made of)
        "solved_count": Problem.objects.filter(userproblemsolved__user=user, is_public=True).count(),
        "homework": homework,
        "challenges": list(mine.filter(status=Duel.Status.PENDING, opponent=user)[:3]),
        "active_duels": [d for d in mine.filter(status=Duel.Status.ACTIVE) if d.ends_at and d.ends_at > now],
        "running": running, "upcoming": upcoming,
        "next_picks": next_picks, "picks_reason": shared_reason(next_picks),
        "recent": list(Submission.objects.filter(user=user).select_related("problem", "language")[:5]),
        "taught": list(Assignment.objects.filter(group__teacher=user).select_related("group")
                       .order_by("-deadline")[:3]),
    })
