"""What the navigation shows besides the links: a running contest, waiting duel calls and, for
staff, the queue waiting on them. Lazy, so htmx fragments and pages without the shell pay nothing;
the list of running contests is cached for everyone for a few seconds."""
import datetime

from django.core.cache import cache
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
        live = [{"pk": c.pk, "title": c.title, "start": c.start, "end": c.end}
                for c in Contest.objects.filter(start__lte=soon, end__gt=now).order_by("end")
                .only("pk", "title", "start", "end")]
        cache.set(_LIVE_KEY, live, _LIVE_TTL)
    return live


def live_contest_for(user) -> dict | None:
    """The running contest to point at (the rail, the top bar, the palette and the home strip):
    one you are in first, else the one ending soonest."""
    now = timezone.now()
    live = [c for c in _running_contests() if c.get("start", now) <= now < c["end"]]
    if not live:
        return None
    joined = set()
    if user.is_authenticated:
        from apps.contests.models import Participation

        joined = set(Participation.objects.filter(user=user, contest_id__in=[c["pk"] for c in live])
                     .values_list("contest_id", flat=True))
    pick = next((c for c in live if c["pk"] in joined), live[0])
    return {**pick, "joined": pick["pk"] in joined, "count": len(live)}


def _staff_todo() -> dict:
    """Problems waiting in the review queue, cached for all staff."""
    todo = cache.get("nav-staff-todo")
    if todo is None:
        from apps.problems.models import Problem

        queue = Problem.objects.filter(status=Problem.Status.PENDING).count()
        todo = {"queue": queue, "total": queue}
        cache.set("nav-staff-todo", todo, 30)
    return todo


def _duel_calls(user) -> int:
    """Duel invites waiting on the user, for the phone tab bar's badge."""
    from apps.classroom.models import Duel
    return Duel.objects.filter(opponent=user, status=Duel.Status.PENDING).count()


def nav(request):
    if request.headers.get("HX-Request"):
        return {}
    user = request.user

    def build():
        signed_in = user.is_authenticated
        return {
            "live": live_contest_for(user),
            "duels": _duel_calls(user) if signed_in else 0,
            "staff": _staff_todo() if signed_in and user.is_staff else {"queue": 0, "total": 0},
        }

    return {"nav": SimpleLazyObject(build)}
