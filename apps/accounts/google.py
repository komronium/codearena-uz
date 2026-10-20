"""Google sign-in and sign-up: the OAuth 2.0 authorization-code flow, done by hand (no extra library).

  /accounts/google/login/     -> Google's account chooser (state kept in the session)
  /accounts/google/callback/  -> code -> access token -> userinfo, then: the account with that Google id, else the
                                 account with that (Google-verified) email, else a new one.

Only an address Google says it verified is used, so linking to an existing account by email is as safe as the mail
link is. Staff accounts do not sign in this way (like Telegram): they use their password."""
import json
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from . import throttle
from .models import User

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
BACKEND = "apps.accounts.backends.EmailOrUsernameBackend"


def configured() -> bool:
    return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)


def _post_form(url: str, data: dict) -> dict:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), method="POST")
    with urllib.request.urlopen(req, timeout=8) as resp:  # noqa: S310 - a fixed https URL
        return json.loads(resp.read().decode())


def _get_json(url: str, token: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=8) as resp:  # noqa: S310
        return json.loads(resp.read().decode())


def _redirect_uri(request) -> str:
    return request.build_absolute_uri(reverse("google_callback"))


def login_start(request):
    if request.user.is_authenticated or not configured():
        return redirect("login")
    state = secrets.token_urlsafe(24)
    nxt = request.GET.get("next", "")
    request.session["g_state"] = state
    request.session["g_next"] = nxt if url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}) else ""
    query = urllib.parse.urlencode({
        "client_id": settings.GOOGLE_CLIENT_ID, "redirect_uri": _redirect_uri(request), "response_type": "code",
        "scope": "openid email profile", "state": state, "prompt": "select_account"})
    return redirect(f"{AUTH_URL}?{query}")


def _username_from(info: dict) -> str:
    """A free public handle from the address's local part: letters, digits and underscores, at least 3."""
    base = re.sub(r"[^A-Za-z0-9_]", "", info["email"].split("@", 1)[0])[:20] or "user"
    if len(base) < 3:
        base = (base + "user")[:8]
    name, n = base, 1
    while User.objects.filter(username__iexact=name).exists():
        n += 1
        name = f"{base}{n}"
    return name


def _user_for(request, info: dict):
    """(user, error): the account this Google identity belongs to, linking or creating it."""
    sub, email = info["sub"], info["email"].lower()
    user = User.objects.filter(google_sub=sub).first()
    if user is None:
        owners = list(User.objects.filter(email__iexact=email).order_by("pk")[:2])
        if len(owners) == 1:  # the one account with this (Google-verified) address: link it
            user = owners[0]
            user.google_sub = sub
            if user.email_verified_at is None:
                user.email_verified_at = timezone.now()
            user.save(update_fields=["google_sub", "email_verified_at"])
        elif len(owners) > 1:
            return None, "Bu email bir nechta hisobda. Parol bilan kiring."
    if user is None:
        user = User(username=_username_from(info), email=email, first_name=(info.get("given_name") or "")[:150],
                    last_name=(info.get("family_name") or "")[:150], google_sub=sub,
                    email_verified_at=timezone.now())
        user.set_unusable_password()
        inviter = User.objects.filter(username__iexact=request.session.pop("ref", ""), is_active=True).first()
        if inviter:
            user.invited_by = inviter
        user.save()
    if not user.is_active:
        return None, "Bu hisob yopilgan."
    if user.is_staff or user.is_superuser:
        return None, "Xodim hisoblari Google orqali kira olmaydi. Parol bilan kiring."
    return user, ""


def callback(request):
    if not configured():
        return redirect("login")
    state, expected = request.GET.get("state", ""), request.session.pop("g_state", "")
    nxt = request.session.pop("g_next", "")
    if request.GET.get("error") or not state or not expected or not secrets.compare_digest(state, expected):
        messages.error(request, "Google orqali kirish bekor qilindi yoki eskirdi. Qaytadan urinib ko‘ring.")
        return redirect("login")
    if throttle.ip_blocked(request, "google", 30, 600):
        messages.error(request, throttle.TOO_MANY)
        return redirect("login")
    try:
        token = _post_form(TOKEN_URL, {
            "code": request.GET.get("code", ""), "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET, "redirect_uri": _redirect_uri(request),
            "grant_type": "authorization_code"})
        info = _get_json(USERINFO_URL, token["access_token"])
    except (urllib.error.URLError, ValueError, KeyError, OSError):
        messages.error(request, "Google bilan aloqa bo‘lmadi. Birozdan keyin qayta urinib ko‘ring.")
        return redirect("login")
    if not (info.get("sub") and info.get("email") and info.get("email_verified")):
        messages.error(request, "Google emailingizni tasdiqlanmagan deb ko‘rsatdi: boshqa usul bilan kiring.")
        return redirect("login")
    user, error = _user_for(request, info)
    if user is None:
        messages.error(request, error)
        return redirect("login")
    auth_login(request, user, backend=BACKEND)
    return redirect(nxt or "home")
