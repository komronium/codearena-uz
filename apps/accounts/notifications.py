"""The bell in the top bar: notify() records an event for a user once (by key), the context processor gives the
top bar the unread count and the latest few, and opening one marks it read. Telegram (apps.accounts.telegram)
sends the same events out of the site for whoever linked it; the bell is for everyone."""
from django.db import IntegrityError

from .models import Notification

ICONS = {"duel": "swords", "badge": "award"}
SHOWN = 8  # in the bell's menu


def notify(user_ids, kind: str, key: str, text: str, url: str) -> None:
    """Record the event for each user (an int or an iterable of them); one already told is skipped."""
    ids = [user_ids] if isinstance(user_ids, int) else list(user_ids)
    rows = [Notification(user_id=i, kind=kind, key=key[:160], text=text[:200], url=url[:300]) for i in ids]
    try:
        Notification.objects.bulk_create(rows, ignore_conflicts=True)
    except IntegrityError:
        pass


def notify_t(user_ids, kind: str, key: str, msgid, url: str, **fmt) -> None:
    """Like notify(), but the text is worked out in each recipient's own language (User.language, else Uzbek), not the
    language of whoever caused the event: `msgid` is a gettext_lazy string with {names}, `fmt` its values (a callable is
    called inside the recipient's language)."""
    from django.contrib.auth import get_user_model
    from django.utils import translation

    ids = [user_ids] if isinstance(user_ids, int) else list(user_ids)
    langs = dict(get_user_model().objects.filter(pk__in=ids).values_list("pk", "language"))
    rows = []
    for uid in ids:
        with translation.override(langs.get(uid) or "uz"):
            values = {k: (v() if callable(v) else v) for k, v in fmt.items()}
            text = str(msgid).format(**values)
        rows.append(Notification(user_id=uid, kind=kind, key=key[:160], text=text[:200], url=url[:300]))
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
