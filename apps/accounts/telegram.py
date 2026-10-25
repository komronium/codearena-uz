"""Telegram Bot API helpers, secure account linking, and a retryable message outbox."""
import hashlib
import html
import json

import logging
import secrets
import urllib.error
import urllib.request
from datetime import timedelta

import django_rq
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import TelegramLink, TelegramLinkToken, TelegramLoginRequest, TelegramOutbox
from django.utils import translation
from django.utils.translation import gettext as _t

log = logging.getLogger(__name__)
LINK_TOKEN_TTL = timedelta(minutes=10)
LOGIN_TTL = timedelta(minutes=5)
OUTBOX_LEASE = timedelta(minutes=10)
MAX_ATTEMPTS = 8


class TelegramAPIError(Exception):
    def __init__(self, message, *, retryable=True):
        super().__init__(message)
        self.retryable = retryable


def bot_configured():
    return bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_BOT_USERNAME)


def bot_api(method: str, payload: dict):
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        raise TelegramAPIError("Telegram bot token is not configured", retryable=False)
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=json.dumps(payload, cls=DjangoJSONEncoder).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            data = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        body = exc.read(1000).decode("utf-8", "replace")
        raise TelegramAPIError(f"Telegram HTTP {exc.code}: {body}", retryable=exc.code >= 500 or exc.code == 429) from exc
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise TelegramAPIError(str(exc)) from exc
    if not data.get("ok"):
        code = int(data.get("error_code", 500))
        raise TelegramAPIError(
            f"Telegram API {code}: {data.get('description', 'request failed')}",
            retryable=code >= 500 or code == 429,
        )
    return data.get("result")


def send_chat_message(chat_id: str, text: str):
    return bot_api("sendMessage", {
        "chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True,
    })


def issue_link_token(user):
    """Return a raw, short-lived token; only its SHA-256 digest is stored."""
    raw = secrets.token_urlsafe(32)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    now = timezone.now()
    TelegramLinkToken.objects.filter(user=user, consumed_at__isnull=True).delete()
    TelegramLinkToken.objects.create(user=user, token_hash=digest, expires_at=now + LINK_TOKEN_TTL)
    return raw


def consume_link_token(raw_token: str, chat_id: str, username: str = ""):
    """Atomically bind an unused token to a private chat, without stealing another account."""
    digest = hashlib.sha256(raw_token.encode()).hexdigest()
    now = timezone.now()
    try:
        with transaction.atomic():
            token = (TelegramLinkToken.objects.select_for_update()
                     .filter(token_hash=digest, consumed_at__isnull=True, expires_at__gt=now)
                     .select_related("user").first())
            if token is None:
                return None, "expired"
            if TelegramLink.objects.filter(chat_id=chat_id).exclude(user=token.user).exists():
                return None, "already_linked"
            link, _ = TelegramLink.objects.update_or_create(
                user=token.user,
                defaults={"chat_id": chat_id, "username": username[:64], "is_active": True, "last_error": ""},
            )
            token.consumed_at = now
            token.save(update_fields=["consumed_at"])
    except IntegrityError:
        return None, "already_linked"
    return link, "ok"


def issue_login_request() -> str:
    """A raw token for one "Telegram orqali kirish" attempt; the browser keeps it, the bot gets it in /start."""
    raw = secrets.token_urlsafe(32)
    now = timezone.now()
    TelegramLoginRequest.objects.filter(expires_at__lt=now).delete()
    TelegramLoginRequest.objects.create(token_hash=hashlib.sha256(raw.encode()).hexdigest(), expires_at=now + LOGIN_TTL)
    return raw


def login_code(raw_token: str) -> str:
    """The four digits the browser shows for a "Telegram orqali kirish" attempt. The bot asks for them back in the
    chat, so tapping a link somebody else sent is not enough to sign them in: the person has to type a code they
    can only have got from that other browser, and the bot says so."""
    return f"{int(hashlib.sha256(('code:' + raw_token).encode()).hexdigest()[:8], 16) % 10000:04d}"


def confirm_login_request(raw_token: str, chat_id: str) -> str:
    """The bot's side: tie an open attempt to the account linked to this chat. Staff accounts never sign in this way.
    Returns "ok", "expired", "unlinked" or "staff"."""
    digest = hashlib.sha256(raw_token.encode()).hexdigest()
    with transaction.atomic():
        req = (TelegramLoginRequest.objects.select_for_update()
               .filter(token_hash=digest, user__isnull=True, used_at__isnull=True, expires_at__gt=timezone.now()).first())
        if req is None:
            return "expired"
        link = TelegramLink.objects.select_related("user").filter(chat_id=chat_id, is_active=True).first()
        if link is None or not link.user.is_active:
            return "unlinked"
        if link.user.is_staff or link.user.is_superuser:
            return "staff"
        req.user = link.user
        req.save(update_fields=["user"])
    return "ok"


def claim_login_request(raw_token: str):
    """The browser's side: the user the bot confirmed for this token, once; None while it waits or after expiry."""
    digest = hashlib.sha256(raw_token.encode()).hexdigest()
    with transaction.atomic():
        req = (TelegramLoginRequest.objects.select_for_update().select_related("user")
               .filter(token_hash=digest, user__isnull=False, used_at__isnull=True, expires_at__gt=timezone.now()).first())
        if req is None:
            return None
        req.used_at = timezone.now()
        req.save(update_fields=["used_at"])
    return req.user


# What can wait: reminders of habits. A person gets at most SOFT_PER_DAY of them a day, and none at night (they wait for
# the morning). A friend's challenge, a contest starting and a rating change are not in the list: they go at once.
SOFT = ("notify_daily_problem", "notify_daily_tip", "notify_trending_problem", "notify_streak", "notify_badges", "notify_digest")
SOFT_PER_DAY = 2
QUIET_FROM, QUIET_TO = 22, 8  # local hours


def after_quiet(now):
    """`now`, or 08:00 when it is night."""
    local = timezone.localtime(now)
    if local.hour >= QUIET_FROM:
        return (local + timedelta(days=1)).replace(hour=QUIET_TO, minute=0, second=0, microsecond=0)
    if local.hour < QUIET_TO:
        return local.replace(hour=QUIET_TO, minute=0, second=0, microsecond=0)
    return now


def queue_notification(user_id: int, preference: str, event_key: str, text: str, quiet: bool | None = None):
    """Persist once per user/event, then enqueue; the scheduled recovery command handles Redis outages.
    `quiet` (default: for the SOFT kinds) keeps it out of the night; the SOFT kinds also stop at SOFT_PER_DAY a day."""
    if not bot_configured():
        return
    link = TelegramLink.objects.filter(
        user_id=user_id, is_active=True, **{preference: True}
    ).first()
    if link is None:
        return
    now = timezone.now()
    soft = preference in SOFT
    if soft:
        start = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
        today = (TelegramOutbox.objects.filter(link=link, preference__in=SOFT, created_at__gte=start)
                 .exclude(status=TelegramOutbox.Status.FAILED).exclude(event_key=event_key).count())
        if today >= SOFT_PER_DAY:
            return
    available = after_quiet(now) if (soft if quiet is None else quiet) else now
    try:
        outbox, created = TelegramOutbox.objects.get_or_create(
            link=link, event_key=event_key,
            defaults={"preference": preference, "text": text[:4096], "available_at": available},
        )
    except IntegrityError:
        return  # a concurrent request created this same notification
    if created and available <= now:  # a night message is left for recover_outbox, which sends it once it is due
        dispatch_outbox(outbox.pk)


def dispatch_outbox(outbox_id: int):
    if not settings.TELEGRAM_BOT_TOKEN:
        return
    try:
        django_rq.get_queue("notifications").enqueue(
            deliver_outbox, outbox_id,
            job_id=f"telegram-outbox-{outbox_id}-{secrets.token_hex(4)}", job_timeout=30
        )
    except Exception:
        log.exception("Could not enqueue Telegram outbox item %s", outbox_id)
        return
    TelegramOutbox.objects.filter(pk=outbox_id, status=TelegramOutbox.Status.PENDING).update(queued_at=timezone.now())


def deliver_outbox(outbox_id: int):
    now = timezone.now()
    with transaction.atomic():
        item = TelegramOutbox.objects.select_for_update().select_related("link").filter(pk=outbox_id).first()
        if item is None or item.status in (TelegramOutbox.Status.SENT, TelegramOutbox.Status.FAILED):
            return
        if not item.link.is_active or not getattr(item.link, item.preference, False):
            item.status = TelegramOutbox.Status.FAILED
            item.last_error = "Telegram link is paused or this notification type is disabled"
            item.save(update_fields=["status", "last_error"])
            return
        if item.available_at > now:
            return
        if item.status == TelegramOutbox.Status.SENDING and item.claimed_at and item.claimed_at > now - OUTBOX_LEASE:
            return
        item.status = TelegramOutbox.Status.SENDING
        item.claimed_at = now
        item.attempts += 1
        item.save(update_fields=["status", "claimed_at", "attempts"])

    try:
        send_chat_message(item.link.chat_id, item.text)
    except TelegramAPIError as exc:
        retry = exc.retryable and item.attempts < MAX_ATTEMPTS
        with transaction.atomic():
            item.refresh_from_db()
            if item.status != TelegramOutbox.Status.SENDING:
                return
            item.last_error = str(exc)[:300]
            item.claimed_at = None
            if retry:
                item.status = TelegramOutbox.Status.PENDING
                item.available_at = now + timedelta(seconds=min(21600, 30 * 2 ** (item.attempts - 1)))
                item.queued_at = None
            else:
                item.status = TelegramOutbox.Status.FAILED
                TelegramLink.objects.filter(pk=item.link_id).update(last_error=str(exc)[:200])
                if "Telegram API 403" in str(exc) or "Telegram API 400" in str(exc):
                    TelegramLink.objects.filter(pk=item.link_id).update(is_active=False)
            item.save(update_fields=["status", "available_at", "queued_at", "claimed_at", "last_error"])
    else:
        with transaction.atomic():
            TelegramOutbox.objects.filter(pk=outbox_id, status=TelegramOutbox.Status.SENDING).update(
                status=TelegramOutbox.Status.SENT, sent_at=timezone.now(), claimed_at=None, last_error=""
            )
            TelegramLink.objects.filter(pk=item.link_id).update(last_error="")


def recover_outbox(limit: int = 500):
    now = timezone.now()
    stale = now - OUTBOX_LEASE
    ids = list(TelegramOutbox.objects.filter(
        status__in=[TelegramOutbox.Status.PENDING, TelegramOutbox.Status.SENDING],
        available_at__lte=now,
    ).filter(queued_at__isnull=True).values_list("pk", flat=True)[:limit])
    ids += list(TelegramOutbox.objects.filter(
        status=TelegramOutbox.Status.PENDING, available_at__lte=now, queued_at__lt=stale,
    ).exclude(pk__in=ids).values_list("pk", flat=True)[:max(0, limit - len(ids))])
    ids += list(TelegramOutbox.objects.filter(
        status=TelegramOutbox.Status.SENDING, claimed_at__lt=stale,
    ).exclude(pk__in=ids).values_list("pk", flat=True)[:max(0, limit - len(ids))])
    for outbox_id in ids:
        dispatch_outbox(outbox_id)


def _site() -> str:
    return settings.SITE_URL.rstrip("/")


def notify_duel_challenge(duel_id: int):
    """A friend's challenge, to the one challenged: who, which language, and the way in."""
    from apps.classroom.models import Duel

    try:
        duel = Duel.objects.select_related("challenger", "opponent").filter(pk=duel_id).first()
        if duel is None or duel.opponent_id is None:
            return
        with translation.override(duel.opponent.language or settings.LANGUAGE_CODE):  # the message speaks the recipient's language
            text = ("<b>" + _t("⚔️ Sizni duelga chaqirishdi") + "</b>\n\n"
                    + _t("<b>{username}</b> — {language}: {n} ta savol, har biriga 20 soniya.").format(
                        username=html.escape(duel.challenger.username), language=duel.get_language_display(), n=len(duel.questions))
                    + "\n" + _t("3 kun ichida qabul qiling.")
                    + f'\n\n<a href="{_site()}/classroom/duels/{duel.pk}/">' + _t("Duelni ochish →") + "</a>")
        queue_notification(duel.opponent_id, "notify_duels", f"duel:{duel.pk}:challenge", text)
    except Exception:
        log.exception("Could not queue Telegram duel challenge %s", duel_id)


def notify_duel_result(duel_id: int):
    """How a duel ended, to both players: won, lost or drawn, the score and the rating change."""
    from apps.classroom import duels
    from apps.classroom.models import Duel

    try:
        duel = Duel.objects.select_related("challenger", "opponent").filter(pk=duel_id).first()
        if duel is None or duel.status != Duel.Status.FINISHED or duel.opponent is None:
            return
        if not duel.friend:
            return  # a quick match is told on the site (the bell), not in Telegram: too many of them a day
        right = {}
        for player in (duel.challenger, duel.opponent):
            r = duels.run(duel, player.pk)
            right[player.pk] = r.points if r else 0
        for me, them, delta in ((duel.challenger, duel.opponent, duel.challenger_delta),
                                (duel.opponent, duel.challenger, duel.opponent_delta)):
            with translation.override(me.language or settings.LANGUAGE_CODE):
                head = (_t("🏆 G‘alaba!") if duel.winner_id == me.pk else _t("Durang") if duel.winner_id is None else _t("Mag‘lubiyat"))
                text = (f"<b>{head}</b>\n\n"
                        + _t("{username} bilan duel: <b>{mine} : {theirs}</b>").format(
                            username=html.escape(them.username), mine=right[me.pk], theirs=right[them.pk])
                        + "\n" + (_t("Mashq duel: reyting o‘zgarmadi.") if duel.unranked else _t("Duel reytingi: {delta}").format(delta=f"{delta:+d}"))
                        + f'\n\n<a href="{_site()}/classroom/duels/{duel.pk}/">' + _t("Natija va savollar →") + "</a>")
            queue_notification(me.pk, "notify_duels", f"duel:{duel.pk}:result", text)
    except Exception:
        log.exception("Could not queue Telegram duel result %s", duel_id)


def notify_rating_changes(contest_id: int):
    """A rated round's new ratings, to each rated participant: the change, where they finished."""
    from apps.contests.models import Contest, Participation

    try:
        contest = Contest.objects.filter(pk=contest_id).first()
        if contest is None:
            return
        rows = (Participation.objects.filter(contest=contest, rating_after__isnull=False, disqualified=False)
                .select_related("user"))
        total = rows.count()
        for p in rows:
            before = p.rating_before or 0
            with translation.override(p.user.language or settings.LANGUAGE_CODE):
                text = ("<b>" + _t("📈 Reyting yangilandi") + "</b>\n\n"
                        + f"{html.escape(contest.title)}\n"
                        + _t("Reyting: <b>{before} → {after}</b> ({delta})").format(
                            before=before, after=p.rating_after, delta=f"{p.rating_after - before:+d}")
                        + ((" · " + _t("o‘rin {rank} / {total}").format(rank=p.rank, total=total)) if p.rank else "")
                        + f'\n\n<a href="{_site()}/contests/{contest.pk}/standings/">' + _t("Natijalar →") + "</a>")
            queue_notification(p.user_id, "notify_contests", f"rating:{contest.pk}", text)
    except Exception:
        log.exception("Could not queue Telegram rating changes for contest %s", contest_id)


def notify_badges(user_id: int, levels: list[tuple[str, int]]):
    """New badge levels (family, level), the highest per badge: one message."""
    from .badges import BY_KEY, titled

    try:
        best = {}
        for fam, tier in levels:
            if fam in BY_KEY and tier > best.get(fam, 0):
                best[fam] = tier
        if not best:
            return
        from django.contrib.auth import get_user_model
        lang = get_user_model().objects.filter(pk=user_id).values_list("language", flat=True).first() or settings.LANGUAGE_CODE
        with translation.override(lang):
            lines = "\n".join(f"• <b>{titled(BY_KEY[f].name, t)}</b> — {str(BY_KEY[f].unit).format(n=BY_KEY[f].levels[t - 1])}"
                              for f, t in sorted(best.items(), key=lambda x: -x[1]))
            key = ",".join(f"{f}{t}" for f, t in sorted(best.items()))
            text = ("<b>" + _t("🏅 Yangi nishon!") + "</b>\n\n" + lines + f'\n\n<a href="{_site()}/accounts/badges/">'
                    + _t("Nishonlaringiz →") + "</a>")
        queue_notification(user_id, "notify_badges", f"badges:{key}", text)
    except Exception:
        log.exception("Could not queue Telegram badges for user %s", user_id)
