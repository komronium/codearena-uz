"""What the navigation shows besides the links: a running contest, homework due soon and, for
staff, the queue waiting on them. Lazy, so htmx fragments and pages without the shell pay nothing;
the list of running contests is cached for everyone for a few seconds."""
import datetime

from django.core.cache import cache
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.functional import SimpleLazyObject

_LIVE_KEY = "nav-live-contests"
_LIVE_TTL = 15


def _running_contests() -> list[dict]:
    """Contests running now or starting within the cache's lifetime; each request checks the
    clock itself, so a contest shows up the moment it starts, not up to 15 s later."""
    live = cache.get(_LIVE_KEY)
    if live is None:
        from apps.contests.models import Contest

        now = timezone.now()
        soon = now + datetime.timedelta(seconds=_LIVE_TTL)
        live = [{"pk": c.pk, "title": c.title, "start": c.start, "end": c.end, "group": c.require_group_id}
                for c in Contest.objects.filter(start__lte=soon, end__gt=now).order_by("end")
                .only("pk", "title", "start", "end", "require_group")]
        cache.set(_LIVE_KEY, live, _LIVE_TTL)
    return live


def live_contest_for(user) -> dict | None:
    """The running contest to point at (the rail, the top bar, the palette and the home strip):
    one you are in first, else the one ending soonest that you may enter. A contest for one
    group is not advertised to students outside it."""
    now = timezone.now()
    live = [c for c in _running_contests() if c.get("start", now) <= now < c["end"]]
    if not live:
        return None
    joined, groups = set(), set()
    if user.is_authenticated:
        from apps.contests.models import Participation

        joined = set(Participation.objects.filter(user=user, contest_id__in=[c["pk"] for c in live])
                     .values_list("contest_id", flat=True))
        wanted = {c["group"] for c in live if c.get("group")}
        if wanted:
            groups = set(user.student_groups.filter(pk__in=wanted).values_list("pk", flat=True))
    live = [c for c in live if c["pk"] in joined or not c.get("group") or c["group"] in groups]
    if not live:
        return None
    pick = next((c for c in live if c["pk"] in joined), live[0])
    return {**pick, "joined": pick["pk"] in joined, "count": len(live)}


def _due_soon(user) -> int:
    """Homework that closes within two days and still has an unsolved problem."""
    from apps.classroom.models import Assignment
    from apps.submissions.models import Submission

    now = timezone.now()
    due = list(Assignment.objects.filter(group__members=user, start__lte=now, deadline__gt=now,
                                         deadline__lte=now + datetime.timedelta(hours=48))
               .prefetch_related("assignment_problems"))
    if not due:
        return 0
    ids = {ap.problem_id for a in due for ap in a.assignment_problems.all()}
    solved = set(Submission.objects.filter(user=user, verdict=Submission.Verdict.AC, problem_id__in=ids)
                 .values_list("problem_id", flat=True))
    return sum(1 for a in due if any(ap.problem_id not in solved for ap in a.assignment_problems.all()))


def _staff_todo() -> dict:
    """Problems waiting in the review queue and teacher requests, cached for all staff."""
    todo = cache.get("nav-staff-todo")
    if todo is None:
        from apps.accounts.models import User
        from apps.problems.models import Problem

        queue = Problem.objects.filter(status=Problem.Status.PENDING).count()
        requests = User.objects.aggregate(n=Count("pk", filter=Q(teacher_requested=True)))["n"]
        todo = {"queue": queue, "requests": requests, "total": queue + requests}
        cache.set("nav-staff-todo", todo, 30)
    return todo


def nav(request):
    if request.headers.get("HX-Request"):
        return {}
    user = request.user

    def build():
        signed_in = user.is_authenticated
        return {
            "live": live_contest_for(user),
            "due": _due_soon(user) if signed_in else 0,
            "staff": _staff_todo() if signed_in and user.is_staff else {"queue": 0, "requests": 0, "total": 0},
        }

    return {"nav": SimpleLazyObject(build)}
