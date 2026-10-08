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
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import TelegramLink, TelegramLinkToken, TelegramOutbox

log = logging.getLogger(__name__)
LINK_TOKEN_TTL = timedelta(minutes=10)
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
        data=json.dumps(payload).encode(),
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


def queue_notification(user_id: int, preference: str, event_key: str, text: str):
    """Persist once per user/event, then enqueue; the scheduled recovery command handles Redis outages."""
    if not bot_configured():
        return
    link = TelegramLink.objects.filter(
        user_id=user_id, is_active=True, **{preference: True}
    ).first()
    if link is None:
        return
    try:
        outbox, created = TelegramOutbox.objects.get_or_create(
            link=link, event_key=event_key,
            defaults={"preference": preference, "text": text[:4096]},
        )
    except IntegrityError:
        return  # a concurrent request created this same notification
    if created:
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


def notify_assignment(assignment_id: int):
    """Send a newly created group assignment to its students after the DB commit."""
    from apps.classroom.models import Assignment

    try:
        assignment = (Assignment.objects.select_related("group")
                      .filter(pk=assignment_id).first())
        if assignment is None:
            return
        when = timezone.localtime(assignment.deadline).strftime("%d.%m.%Y, %H:%M")
        url = f"{settings.SITE_URL.rstrip('/')}/classroom/{assignment.pk}/"
        text = (
            f"<b>📝 Yangi vazifa</b>\n\n"
            f"<b>{html.escape(assignment.title)}</b>\n"
            f"Guruh: {html.escape(assignment.group.name)}\n"
            f"Topshirish muddati: {when}\n\n"
            f'<a href="{url}">Vazifani ochish →</a>'
        )
        user_ids = (assignment.group.members.filter(is_active=True)
                    .exclude(pk=assignment.created_by_id)
                    .filter(telegram_link__is_active=True, telegram_link__notify_assignments=True)
                    .values_list("pk", flat=True))
        for user_id in user_ids.iterator():
            queue_notification(user_id, "notify_assignments", f"assignment:{assignment.pk}:created", text)
    except Exception:
        log.exception("Could not queue Telegram assignment notification for assignment %s", assignment_id)
