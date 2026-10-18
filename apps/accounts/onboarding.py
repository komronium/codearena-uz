"""The account gate: before any page opens, a signed-in user fills in their name, country and city and
confirms their email by the link we send. Staff are never held. Turned off with ACCOUNT_GATE=0 (the
test settings do, so other apps' tests need no profile).

The link is a signed (user, email) pair, so it only confirms the address it was sent to: change the
email and the old link stops working."""

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.core.mail import send_mail
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

_SALT = "accounts.verify-email"
MAX_AGE = 3 * 24 * 3600  # a link works for three days
RESEND_EVERY = 60  # seconds between two mails to one user

# what the gate asks for, in the welcome form's order: (field, label)
REQUIRED = [("first_name", "Ism"), ("last_name", "Familiya"), ("country", "Davlat"), ("location", "Shahar"),
            ("email", "Email")]


def missing(user) -> list[str]:
    """Labels of the profile fields still empty."""
    return [label for field, label in REQUIRED if not (getattr(user, field) or "").strip()]


def needs_gate(user) -> bool:
    if not getattr(settings, "ACCOUNT_GATE", True) or not user.is_authenticated or user.is_staff:
        return False
    return bool(missing(user)) or user.email_verified_at is None


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
    send_mail(
        "CodeArena: emailingizni tasdiqlang",
        f"Salom, {user.first_name or user.username}!\n\n"
        f"CodeArena hisobingizni faollashtirish uchun quyidagi havolani oching:\n{link}\n\n"
        "Havola 3 kun amal qiladi. Agar siz ro‘yxatdan o‘tmagan bo‘lsangiz, bu xatni e’tiborsiz qoldiring.",
        settings.DEFAULT_FROM_EMAIL, [user.email],
    )
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
    """Sends a user who still owes the gate to the welcome page, whatever they asked for, except the
    few pages the gate itself needs (and static files, sign-out, the Telegram webhook)."""

    _OPEN_NAMES = {"welcome", "verify_email", "logout", "telegram_webhook"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and needs_gate(user) and not self._open(request):
            return redirect("welcome")
        return self.get_response(request)

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
