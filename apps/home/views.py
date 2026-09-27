"""/ : what to do next for a signed-in student, what CodeArena is for a guest."""
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone

from apps.accounts.models import User
from apps.classroom.models import Assignment, Duel
from apps.contests.models import Contest
from apps.problems.daily import daily_for, streaks
from apps.problems.models import DailySolve
from apps.problems.skills import next_problems, open_problems
from apps.submissions.models import Submission


# (icon, title, text) for the guest landing page
FEATURES = [
    ("list-checks", "Masalalar va 4 til",
     "Boshlang‘ichdan qiyingacha. Python, C++, Java, JavaScript — har bir yechim darhol testlanadi."),
    ("trophy", "Reytingli musobaqalar",
     "Jonli natijalar jadvali va Elo reyting. Reytingli musobaqada faqat hech kim ko‘rmagan masalalar."),
    ("notebook-pen", "Uy vazifalari",
     "O‘qituvchi guruhga muddatli vazifa beradi va kim qachon yechganini jadvalda ko‘radi."),
    ("swords", "Duellar",
     "Sinfdoshingizni chaqiring: ikkalangiz ham ko‘rmagan masala, 30 daqiqa, birinchi AC g‘olib."),
    ("flame", "Kun masalasi",
     "Har kuni bitta masala. Ketma-ket yechsangiz seriya o‘sadi va bonus ball olasiz."),
    ("shield-check", "Halol natijalar",
     "Ko‘chirilgan kod, begona qurilma va o‘chirilgan kuzatuv aniqlanadi; har bir qaror jurnalga yoziladi."),
]


def home(request):
    now = timezone.now()
    daily = daily_for()
    contests = Contest.objects.annotate(n_participants=Count("participations"))  # contests/_row.html shows it
    running = list(contests.filter(start__lte=now, end__gt=now).order_by("end")[:3])
    upcoming = list(contests.filter(start__gt=now).order_by("start")[:3])
    if not request.user.is_authenticated:
        return render(request, "home/landing.html", {
            "daily": daily, "running": running, "upcoming": upcoming, "features": FEATURES,
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
    return render(request, "home/dashboard.html", {
        "daily": daily,
        "daily_done": bool(daily) and DailySolve.objects.filter(user=user, daily=daily).exists(),
        "streak": current, "best_streak": best,
        "homework": homework,
        "challenges": list(mine.filter(status=Duel.Status.PENDING, opponent=user)[:3]),
        "active_duels": [d for d in mine.filter(status=Duel.Status.ACTIVE) if d.ends_at and d.ends_at > now],
        "running": running, "upcoming": upcoming,
        "next_picks": next_problems(user, exclude=(daily.problem_id,) if daily else ()),
        "recent": list(Submission.objects.filter(user=user).select_related("problem", "language")[:5]),
        "taught": list(Assignment.objects.filter(group__teacher=user).select_related("group")
                       .order_by("-deadline")[:3]),
    })
