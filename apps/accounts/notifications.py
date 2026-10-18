"""The bell in the top bar: notify() records an event for a user once (by key), the context processor gives the
top bar the unread count and the latest few, and opening one marks it read. Telegram (apps.accounts.telegram)
sends the same events out of the site for whoever linked it; the bell is for everyone."""
from django.db import IntegrityError

from .models import Notification

ICONS = {"duel": "swords", "assignment": "notebook-pen", "review": "message-square-text", "badge": "award"}
SHOWN = 8  # in the bell's menu


def notify(user_ids, kind: str, key: str, text: str, url: str) -> None:
    """Record the event for each user (an int or an iterable of them); one already told is skipped."""
    ids = [user_ids] if isinstance(user_ids, int) else list(user_ids)
    rows = [Notification(user_id=i, kind=kind, key=key[:160], text=text[:200], url=url[:300]) for i in ids]
    try:
        Notification.objects.bulk_create(rows, ignore_conflicts=True)
    except IntegrityError:
        pass


def bell(request) -> dict:
    """Context processor: {"bell": {"unread": n, "latest": [...]}} for a signed-in user, both lazy."""
    user = request.user
    if not user.is_authenticated:
        return {}
    mine = Notification.objects.filter(user=user)

    class _Bell:
        def unread(self):
            if not hasattr(self, "_n"):
                self._n = mine.filter(read_at__isnull=True).count()
            return self._n

        def latest(self):
            rows = list(mine[:SHOWN])
            for n in rows:
                n.icon = ICONS.get(n.kind, "bell")
            return rows

    return {"bell": _Bell()}
