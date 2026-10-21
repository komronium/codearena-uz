"""Telegram bot webhook and authenticated account-linking actions."""
import hmac
import json
import logging
from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.contrib.auth import login as auth_login
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.utils.http import url_has_allowed_host_and_scheme
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import TelegramLink, TelegramLinkToken
from .telegram import (bot_configured, claim_login_request, confirm_login_request, consume_link_token, issue_link_token,
                       login_code,
                       issue_login_request, send_chat_message)
from django.utils.translation import gettext as _t

log = logging.getLogger(__name__)


@login_required
@require_POST
def connect(request):
    if not bot_configured():
        messages.error(request, _t("Telegram bot hali sozlanmagan. Keyinroq urinib ko‘ring."))
        return redirect("profile_edit")
    token = issue_link_token(request.user)
    username = settings.TELEGRAM_BOT_USERNAME.lstrip("@")
    return redirect(f"https://t.me/{quote(username)}?start={quote(token)}")


@require_POST
def login_start(request):
    """"Telegram orqali kirish", step 1: remember a fresh token in this browser's session and send the user to the bot."""
    if request.user.is_authenticated or not bot_configured():
        return redirect("login")
    request.session["tg_login"] = issue_login_request()
    request.session["tg_login_next"] = request.POST.get("next", "")
    username = settings.TELEGRAM_BOT_USERNAME.lstrip("@")
    return render(request, "registration/telegram_login.html", {
        "bot_url": f"https://t.me/{quote(username)}?start=login_{quote(request.session['tg_login'])}", "bot": username,
        "code": login_code(request.session["tg_login"])})


def login_status(request):
    """Step 3: the waiting page asks until the bot has confirmed; then this browser is signed in."""
    raw = request.session.get("tg_login", "")
    user = claim_login_request(raw) if raw else None
    if user is None:
        return JsonResponse({"ok": False, "waiting": bool(raw)})
    nxt = request.session.pop("tg_login_next", "")
    request.session.pop("tg_login", None)
    auth_login(request, user, backend="apps.accounts.backends.EmailOrUsernameBackend")
    if not url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        nxt = "/"
    return JsonResponse({"ok": True, "next": nxt})


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
        messages.error(request, _t("Bildirishnoma sozlamalari uchun avval Telegramni ulang."))
        return redirect("profile_edit")
    from .forms import TelegramPreferencesForm

    old_values = {
        "notify_daily_problem": link.notify_daily_problem,
        "notify_daily_tip": link.notify_daily_tip,
        "notify_trending_problem": link.notify_trending_problem,
        "notify_contests": link.notify_contests,
        "notify_duels": link.notify_duels,
        "notify_badges": link.notify_badges,
        "notify_streak": link.notify_streak,
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
        messages.error(request, _t("Sozlamalarni saqlab bo‘lmadi. Sahifani yangilab, qayta urinib ko‘ring."))
    return redirect("profile_edit")


def _handle_bot_message(message):
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat.get("type") != "private" or chat_id is None:
        return
    text = (message.get("text") or "").strip()
    parts = text.split(maxsplit=1)
    command = parts[0].split("@", 1)[0].lower() if parts else ""
    if command == "/start" and len(parts) == 2 and parts[1].startswith("login_"):
        # step 1: remember which attempt this chat was sent; the person confirms with the code their browser shows
        cache.set(f"tg-login-pending:{chat_id}", parts[1][len("login_"):][:64], 300)
        try:
            send_chat_message(str(chat_id), _t("Saytga kirish so‘rovi. Brauzeringizdagi <b>4 xonali kodni</b> shu yerga yozing. "
                                            "Agar bu havolani sizga boshqa kishi yuborgan bo‘lsa, hech narsa yozmang."))
        except Exception:
            log.exception("Could not send Telegram login prompt")
        return
    pending = cache.get(f"tg-login-pending:{chat_id}") if text.isdigit() and len(text) == 4 else None
    if pending:
        cache.delete(f"tg-login-pending:{chat_id}")
        if text != login_code(pending):
            send_chat_message(str(chat_id), "Kod mos kelmadi. Saytda «Telegram orqali kirish»ni qaytadan bosing.")
            return
        status = confirm_login_request(pending, str(chat_id))
        replies = {
            "ok": _t("Tayyor! Brauzerga qayting: u o‘zi kirib oladi."),
            "expired": _t("Kirish so‘rovi eskirgan. Saytda «Telegram orqali kirish»ni qaytadan bosing."),
            "unlinked": _t("Bu Telegram hech bir CodeArena profiliga ulanmagan. Avval parol bilan kirib, Sozlamalar → Telegram orqali ulang."),
            "staff": _t("Xodim hisoblari Telegram orqali kira olmaydi. Parol bilan kiring."),
        }
        try:
            send_chat_message(str(chat_id), replies[status])
        except Exception:
            log.exception("Could not send Telegram login reply")
        return
    if command == "/start" and len(parts) == 2:
        _link, status = consume_link_token(parts[1][:64], str(chat_id), (message.get("from") or {}).get("username", ""))
        replies = {
            "ok": _t("CodeArena Telegram bildirishnomalari ulandi. Xabar turlarini saytdagi Sozlamalar bo‘limidan sozlashingiz mumkin."),
            "expired": _t("Ulash kodi eskirgan yoki ishlatilgan. CodeArena profilidan yangi kod oling."),
            "already_linked": _t("Bu Telegram hisob boshqa CodeArena profiliga ulangan. Avval o‘sha profildan uzing."),
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
            send_chat_message(str(chat_id), _t("Bildirishnomalar to‘xtatildi. Qayta ulash uchun CodeArena profiliga kiring."))
        except Exception:
            log.exception("Could not send Telegram stop reply")
        return
    try:
        send_chat_message(str(chat_id), _t("CodeArena bildirishnomalari uchun saytdagi Sozlamalar → Telegram bo‘limidan hisobingizni ulang."))
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
