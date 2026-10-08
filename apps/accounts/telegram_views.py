"""Telegram bot webhook and authenticated account-linking actions."""
import hmac
import json
import logging
from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import TelegramLink, TelegramLinkToken
from .telegram import bot_configured, consume_link_token, issue_link_token, send_chat_message

log = logging.getLogger(__name__)


@login_required
@require_POST
def connect(request):
    if not bot_configured():
        messages.error(request, "Telegram bot hali sozlanmagan. Keyinroq urinib ko‘ring.")
        return redirect("profile_edit")
    token = issue_link_token(request.user)
    username = settings.TELEGRAM_BOT_USERNAME.lstrip("@")
    return redirect(f"https://t.me/{quote(username)}?start={quote(token)}")


@login_required
@require_POST
def disconnect(request):
    TelegramLinkToken.objects.filter(user=request.user).delete()
    TelegramLink.objects.filter(user=request.user).delete()
    messages.success(request, "Telegram hisobingiz uzildi.")
    return redirect("profile_edit")


@login_required
@require_POST
def preferences(request):
    link = TelegramLink.objects.filter(user=request.user, is_active=True).first()
    if link is None:
        messages.error(request, "Bildirishnoma sozlamalari uchun avval Telegramni ulang.")
        return redirect("profile_edit")
    from .forms import TelegramPreferencesForm

    old_values = {
        "notify_submissions": link.notify_submissions,
        "notify_daily_problem": link.notify_daily_problem,
        "notify_contests": link.notify_contests,
    }
    form = TelegramPreferencesForm(request.POST, instance=link)
    if form.is_valid():
        link = form.save()
        for field, was_enabled in old_values.items():
            if was_enabled and not getattr(link, field):
                link.outbox.filter(preference=field, status__in=["pending", "sending"]).update(
                    status="failed", last_error="Notification type was disabled"
                )
        messages.success(request, "Telegram bildirishnoma sozlamalari saqlandi.")
    else:
        messages.error(request, "Sozlamalarni saqlab bo‘lmadi. Sahifani yangilab, qayta urinib ko‘ring.")
    return redirect("profile_edit")


def _handle_bot_message(message):
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat.get("type") != "private" or chat_id is None:
        return
    text = (message.get("text") or "").strip()
    parts = text.split(maxsplit=1)
    command = parts[0].split("@", 1)[0].lower() if parts else ""
    if command == "/start" and len(parts) == 2:
        _link, status = consume_link_token(parts[1][:64], str(chat_id), (message.get("from") or {}).get("username", ""))
        replies = {
            "ok": "CodeArena Telegram bildirishnomalari ulandi. Xabar turlarini saytdagi Profilni tahrirlash bo‘limidan sozlashingiz mumkin.",
            "expired": "Ulash kodi eskirgan yoki ishlatilgan. CodeArena profilidan yangi kod oling.",
            "already_linked": "Bu Telegram hisob boshqa CodeArena profiliga ulangan. Avval o‘sha profildan uzing.",
        }
        try:
            send_chat_message(str(chat_id), replies[status])
        except Exception:
            log.exception("Could not send Telegram account-link reply")
        return
    if command == "/stop":
        link = TelegramLink.objects.filter(chat_id=str(chat_id)).first()
        if link:
            link.is_active = False
            link.save(update_fields=["is_active"])
            link.outbox.filter(status__in=["pending", "sending"]).update(
                status="failed", last_error="Telegram link was paused"
            )
        try:
            send_chat_message(str(chat_id), "Bildirishnomalar to‘xtatildi. Qayta ulash uchun CodeArena profiliga kiring.")
        except Exception:
            log.exception("Could not send Telegram stop reply")
        return
    try:
        send_chat_message(str(chat_id), "CodeArena bildirishnomalari uchun saytdagi Profilni tahrirlash → Telegram bo‘limidan hisobingizni ulang.")
    except Exception:
        log.exception("Could not send Telegram help reply")


@csrf_exempt
@require_POST
def webhook(request):
    expected = settings.TELEGRAM_WEBHOOK_SECRET
    provided = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not expected or not hmac.compare_digest(expected, provided):
        return HttpResponse(status=403)
    if not settings.TELEGRAM_BOT_TOKEN:
        return HttpResponse(status=503)
    if len(request.body) > 32_768:
        return HttpResponseBadRequest("payload too large")
    try:
        update = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return HttpResponseBadRequest("invalid payload")
    if not isinstance(update, dict):
        return HttpResponseBadRequest("invalid payload")
    try:
        message = update.get("message")
        if isinstance(message, dict):
            _handle_bot_message(message)
    except Exception:
        log.exception("Telegram webhook update failed")
        return HttpResponse(status=500)
    return HttpResponse("ok")
