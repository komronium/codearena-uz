"""/ : what to do next for a signed-in student, what CodeArena is for a guest."""
from django.contrib.staticfiles import finders
from django.db.models import Count, Q
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import cache_control

from apps.accounts.models import User
from apps.accounts.tiers import next_tier as _next_tier
from apps.classroom import duels
from apps.classroom.models import Assignment, Duel
from apps.contests.models import Contest, Participation
from apps.contests.views import _standings  # cached, the standings page's own numbers
from apps.problems.daily import daily_for, streaks, week_strip
from apps.problems.models import DailySolve, Language, Problem
from apps.problems.progress import level_progress, solved_ring
from apps.problems.skills import next_problems, open_problems, shared_reason
from apps.submissions.models import Submission

from .context_processors import live_contest_for
from .templatetags.seo import SITE_DESCRIPTION, SITE_NAME


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


def _spark(user, w=300, h=64) -> dict | None:
    """The rating card's small line: the rating after each of the last ten rated rounds, oldest first."""
    history = list(Participation.objects.filter(user=user, rating_after__isnull=False)
                   .order_by("-contest__end").values_list("rating_after", flat=True)[:10])[::-1]
    if len(history) < 2:
        return None
    lo, hi = min(history), max(history)
    span, pad = (hi - lo) or 1, 6
    xs = [pad + i * (w - 2 * pad) / (len(history) - 1) for i in range(len(history))]
    ys = [pad + (hi - v) / span * (h - 2 * pad) for v in history]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    return {"w": w, "h": h, "line": line, "area": f"{xs[0]:.1f},{h} {line} {xs[-1]:.1f},{h}",
            "x": f"{xs[-1]:.1f}", "y": f"{ys[-1]:.1f}", "first": history[0], "n": len(history)}


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
        # the hero's first line: the round running now, else the next one, that anyone may enter
        next_round = next((c for c in running + upcoming if not c.require_group_id), None)
        return render(request, "home/landing.html", {
            "daily": daily, "running": running, "upcoming": upcoming, "next_round": next_round,
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
        "spark": _spark(user),
        # LeetCode's ring of solved problems per level, out of the open problems
        "ring": solved_ring(level_progress(user, open_problems())),
        "next_picks": next_picks, "picks_reason": shared_reason(next_picks),
        "recent": list(Submission.objects.filter(user=user).select_related("problem", "language")[:5]),
        "taught": list(Assignment.objects.filter(group__teacher=user).select_related("group")
                       .order_by("-deadline")[:3]),
    })


# staff tools, personal pages, sign-in plumbing and htmx/JSON endpoints: nothing a search should land on;
# and students' photos stay out of image search
_NOT_FOR_CRAWLERS = ["/moderation/", "/integrity/", "/submissions/", "/classroom/", "/django-rq/",
                     "/accounts/profile/edit/", "/accounts/password-", "/accounts/reset/", "/accounts/verify/",
                     "/accounts/logout/", "/accounts/teacher-request/", "/problems/suggest/", "/learn/search/",
                     "/media/avatars/"]
# a list's search, sorting, own-progress filter and random pick: endless addresses for the one list
# (its tag and level filters stay open; their canonical URL folds them into the list)
_LIST_PARAMS = ["q", "sort", "dir", "status", "kind", "random"]


def robots_txt(request):
    lines = ["User-agent: *", *(f"Disallow: {path}" for path in _NOT_FOR_CRAWLERS),
             *(f"Disallow: /*{sep}{param}=" for param in _LIST_PARAMS for sep in "?&"),
             "", f"Sitemap: {request.build_absolute_uri(reverse('sitemap'))}"]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


@cache_control(public=True, max_age=7 * 24 * 3600)
def favicon(request):
    """/favicon.ico: browsers, feed readers and crawlers ask the root for it whatever the head says."""
    return FileResponse(open(finders.find("img/favicon.ico"), "rb"), content_type="image/x-icon")


@cache_control(public=True, max_age=24 * 3600)
def manifest(request):
    """The web app manifest: the name and icons a phone shows for the site on its home screen."""
    icons = [{"src": static(f"img/{name}.png"), "sizes": f"{size}x{size}", "type": "image/png", "purpose": purpose}
             for name, size, purpose in (("icon-192", 192, "any"), ("icon-512", 512, "any"),
                                         ("icon-maskable-512", 512, "maskable"))]
    return JsonResponse({"name": SITE_NAME, "short_name": SITE_NAME, "description": SITE_DESCRIPTION, "lang": "uz",
                         "start_url": "/", "scope": "/", "display": "standalone",
                         "background_color": "#FFFFFF", "theme_color": "#FFFFFF", "icons": icons},
                        content_type="application/manifest+json", json_dumps_params={"ensure_ascii": False})
