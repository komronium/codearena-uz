"""The staff's switch that closes the duels (classroom.models.DuelSwitch): while it is closed everybody but the staff
sees a "closed" page instead of the duel pages, so a class is not distracted. It may close for a number of minutes
and opens by itself then, or stay closed until the staff open it."""
from datetime import timedelta

from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from .models import DuelSwitch

_KEY = "duels-switch"
_NEVER = "forever"


def _state() -> str:
    """"" when open, "forever", or the ISO time it reopens; cached for a few seconds (toggling clears it)."""
    value = cache.get(_KEY)
    if value is None:
        row = DuelSwitch.objects.filter(pk=1).first()
        value = "" if row is None or not row.closed else (row.until.isoformat() if row.until else _NEVER)
        cache.set(_KEY, value, 15)
    return value


def closed_until():
    """(closed, reopens_at or None): reopens_at is None for a switch with no end."""
    state = _state()
    if not state:
        return False, None
    if state == _NEVER:
        return True, None
    until = timezone.datetime.fromisoformat(state)
    return (until > timezone.now()), until


def is_closed() -> bool:
    return closed_until()[0]


def close(user, minutes: int | None) -> None:
    """Close the duels for `minutes`, or until opened when it is None."""
    until = timezone.now() + timedelta(minutes=minutes) if minutes else None
    DuelSwitch.objects.update_or_create(pk=1, defaults={"closed": True, "until": until, "changed_by": user})
    cache.delete(_KEY)


def open_up(user) -> None:
    DuelSwitch.objects.update_or_create(pk=1, defaults={"closed": False, "until": None, "changed_by": user})
    cache.delete(_KEY)


class DuelSwitchMiddleware:
    """While the duels are closed, the staff alone reach /classroom/."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path_info.startswith("/classroom/") and not getattr(request.user, "is_staff", False) and is_closed():
            if request.method == "GET" and "text/html" in request.headers.get("Accept", "") and not request.headers.get("X-Fetch"):
                _, until = closed_until()
                return render(request, "classroom/closed.html", {"until": until}, status=200)
            return JsonResponse({"closed": True}, status=403)
        return self.get_response(request)
