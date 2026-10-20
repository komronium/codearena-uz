"""The account gate: a signed-in user fills in their name, country and city and confirms their email by the link
we send before they join a contest or a duel. Practice, courses, ratings and profiles stay open meanwhile (a
slim banner asks for the rest, see `nudge`), so nobody meets a form before their first problem. Staff are never
held. Turned off with ACCOUNT_GATE=0 (the test settings do, so other apps' tests need no profile).

The link is a signed (user, email) pair, so it only confirms the address it was sent to: change the
email and the old link stops working."""

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import escape
from django.utils import timezone

_SALT = "accounts.verify-email"
MAX_AGE = 3 * 24 * 3600  # a link works for three days
RESEND_EVERY = 60  # seconds between two mails to one user

# what the gate asks for, in the welcome form's order: (field, label)
REQUIRED = [("first_name", "Ism"), ("country", "Davlat"), ("location", "Shahar"), ("email", "Email")]

# where the gate holds: duels, and anything that changes a contest (joining, starting a clock, a virtual run)
_WALLED_PREFIXES = ("/classroom/",)
_WALLED_WRITES = ("/contests/",)


def missing(user) -> list[str]:
    """Labels of the profile fields still empty."""
    return [label for field, label in REQUIRED if not (getattr(user, field) or "").strip()]


def needs_gate(user) -> bool:
    if not getattr(settings, "ACCOUNT_GATE", True) or not user.is_authenticated or user.is_staff:
        return False
    return bool(missing(user)) or user.email_verified_at is None


def needs_profile(user) -> bool:
    """Only the profile fields (name, country, city, email address) are missing, whatever the email's state: what a
    contest asks for. The mail link can wait; until it is clicked a round is joined but not rated, and duels wait."""
    if not getattr(settings, "ACCOUNT_GATE", True) or not user.is_authenticated or user.is_staff:
        return False
    return bool(missing(user))


def nudge(user) -> dict | None:
    """What the slim banner says to a signed-in user who still owes the gate: labels of the empty profile
    fields, or the pending email confirmation."""
    if not needs_gate(user):
        return None
    left = missing(user)
    return {"missing": left, "email_pending": not left}


def make_token(user) -> str:
    return signing.dumps({"u": user.pk, "e": user.email.lower()}, salt=_SALT)


def read_token(token: str):
    """(user_id, email) from a valid, unexpired link, else None."""
    try:
        data = signing.loads(token, salt=_SALT, max_age=MAX_AGE)
    except signing.BadSignature:
        return None
    return data.get("u"), data.get("e", "")


def send_verification(request, user, force: bool = False) -> bool:
    """Mail the confirmation link, at most once a minute per user unless forced (a new address).
    False when it was held back by that limit."""
    key = f"verify-mail:{user.pk}"
    if not force and cache.get(key):
        return False
    cache.set(key, 1, RESEND_EVERY)
    link = request.build_absolute_uri(reverse("verify_email", args=[make_token(user)]))
    name = user.first_name or user.username
    text = (f"Salom, {name}!\n\n"
            f"CodeArena hisobingizni faollashtirish uchun quyidagi havolani oching:\n{link}\n\n"
            "Havola 3 kun amal qiladi. Agar siz ro‘yxatdan o‘tmagan bo‘lsangiz, bu xatni e’tiborsiz qoldiring.")
    html = (f'<div style="font:16px/1.5 Arial,sans-serif;color:#14203A;max-width:480px">'
            f'<p>Salom, {escape(name)}!</p>'
            f'<p>CodeArena hisobingizni faollashtirish uchun emailingizni tasdiqlang:</p>'
            f'<p><a href="{escape(link)}" style="display:inline-block;background:#F2B53A;color:#1A1F33;font-weight:700;'
            f'padding:10px 18px;border-radius:8px;text-decoration:none">Emailni tasdiqlash</a></p>'
            f'<p style="color:#3E4A63;font-size:14px">Tugma ishlamasa, havolani brauzerga qo‘ying:<br>{escape(link)}</p>'
            f'<p style="color:#3E4A63;font-size:14px">Havola 3 kun amal qiladi. Agar siz ro‘yxatdan o‘tmagan bo‘lsangiz, '
            f'bu xatni e’tiborsiz qoldiring.</p></div>')
    message = EmailMultiAlternatives("CodeArena: emailingizni tasdiqlang", text, settings.DEFAULT_FROM_EMAIL, [user.email])
    message.attach_alternative(html, "text/html")
    message.send()
    return True


def confirm(user, email: str) -> bool:
    """Mark `email` confirmed if it is still the user's address."""
    if not email or user.email.lower() != email:
        return False
    if user.email_verified_at is None:
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at"])
    return True


class OnboardingMiddleware:
    """Sends a user who still owes the gate to the welcome page when they reach for a duel or a contest
    action (the few pages the gate itself needs stay open, and static files, sign-out, the Telegram webhook)."""

    _OPEN_NAMES = {"welcome", "verify_email", "logout", "telegram_webhook"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and self._walled(request) and not self._open(request) and (
                needs_profile(user) if request.path_info.startswith(_WALLED_WRITES) else needs_gate(user)):
            if request.method == "GET":
                request.session["gate_next"] = request.get_full_path()
            return redirect("welcome")
        return self.get_response(request)

    @staticmethod
    def _walled(request) -> bool:
        path = request.path_info
        return path.startswith(_WALLED_PREFIXES) or (
            path.startswith(_WALLED_WRITES) and request.method not in ("GET", "HEAD", "OPTIONS"))

    def _open(self, request) -> bool:
        path = request.path_info
        if path.startswith(("/" + settings.STATIC_URL.lstrip("/"), settings.MEDIA_URL, "/favicon")):
            return True
        match = getattr(request, "resolver_match", None)
        if match is None:
            from django.urls import Resolver404, resolve
            try:
                match = resolve(path)
            except Resolver404:
                return True  # a 404 is a 404 for everyone
        return match.url_name in self._OPEN_NAMES
