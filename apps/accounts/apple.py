"""Sign in with Apple (iCloud): the OpenID Connect authorization-code flow, done by hand like apps.accounts.google.

  /accounts/apple/login/     -> Apple's sign-in page (state, nonce and `next` kept in a signed cookie)
  /accounts/apple/callback/  -> Apple POSTs the form back (response_mode=form_post), code -> id_token, then: the account
                                with that Apple id, else the account with that (Apple-verified) email, else a new one.

Apple's answer is a cross-site POST, which a SameSite=Lax session cookie would not travel with: the state lives in its own
SameSite=None cookie. The id_token comes straight from Apple's token endpoint over TLS, so its claims (issuer, audience,
expiry, nonce) are checked and its signature is not. The client secret Apple asks for is a short-lived ES256 token signed
with the .p8 key from the developer account. Apple gives the name only the first time, and may hand over a private relay
address (xxx@privaterelay.appleid.com): it is a real, verified address like any other. Staff accounts do not sign in this
way: they use their password."""
import base64
import hashlib
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.core import signing
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _t
from django.views.decorators.csrf import csrf_exempt

from . import throttle
from .google import _username_from
from .models import User

AUTH_URL = "https://appleid.apple.com/auth/authorize"
TOKEN_URL = "https://appleid.apple.com/auth/token"
ISSUER = "https://appleid.apple.com"
BACKEND = "apps.accounts.backends.EmailOrUsernameBackend"
COOKIE = "ca_apple"
MAX_AGE = 600


def configured() -> bool:
    return bool(settings.APPLE_CLIENT_ID and settings.APPLE_TEAM_ID and settings.APPLE_KEY_ID and settings.APPLE_PRIVATE_KEY)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _client_secret() -> str:
    """The ES256 token Apple takes as the client secret: valid five minutes, signed with the account's .p8 key."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

    now = int(time.time())
    head = {"alg": "ES256", "kid": settings.APPLE_KEY_ID, "typ": "JWT"}
    body = {"iss": settings.APPLE_TEAM_ID, "iat": now, "exp": now + 300, "aud": ISSUER, "sub": settings.APPLE_CLIENT_ID}
    signing_input = f"{_b64(json.dumps(head).encode())}.{_b64(json.dumps(body).encode())}"
    key = serialization.load_pem_private_key(settings.APPLE_PRIVATE_KEY.replace("\\n", "\n").encode(), password=None)
    r, s = decode_dss_signature(key.sign(signing_input.encode(), ec.ECDSA(hashes.SHA256())))
    return f"{signing_input}.{_b64(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"


def _post_form(url: str, data: dict) -> dict:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), method="POST")
    with urllib.request.urlopen(req, timeout=8) as resp:  # noqa: S310 - a fixed https URL
        return json.loads(resp.read().decode())


def _claims(id_token: str) -> dict:
    """The payload of an id_token received from Apple's token endpoint."""
    payload = id_token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))


def _redirect_uri(request) -> str:
    return request.build_absolute_uri(reverse("apple_callback"))


def login_start(request):
    if request.user.is_authenticated or not configured():
        return redirect("login")
    state, nonce = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    nxt = request.GET.get("next", "")
    nxt = nxt if url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}) else ""
    query = urllib.parse.urlencode({
        "client_id": settings.APPLE_CLIENT_ID, "redirect_uri": _redirect_uri(request), "response_type": "code",
        "response_mode": "form_post", "scope": "name email", "state": state, "nonce": nonce})
    response = redirect(f"{AUTH_URL}?{query}")
    secure = request.is_secure()  # SameSite=None needs Secure; plain http (local development) falls back to Lax
    response.set_cookie(COOKIE, signing.dumps({"s": state, "n": nonce, "next": nxt}, salt=COOKIE), max_age=MAX_AGE,
                        secure=secure, httponly=True, samesite="None" if secure else "Lax")
    return response


def _user_for(request, claims: dict, names: dict):
    """(user, error): the account this Apple identity belongs to, linking or creating it."""
    sub, email = claims["sub"], claims["email"].lower()
    user = User.objects.filter(apple_sub=sub).first()
    if user is None:
        owners = list(User.objects.filter(email__iexact=email).order_by("pk")[:2])
        if len(owners) == 1:  # the one account with this (Apple-verified) address: link it
            user = owners[0]
            user.apple_sub = sub
            if user.email_verified_at is None:
                user.email_verified_at = timezone.now()
            user.save(update_fields=["apple_sub", "email_verified_at"])
        elif len(owners) > 1:
            return None, _t("Bu email bir nechta hisobda. Parol bilan kiring.")
    if user is None:
        user = User(username=_username_from({"email": email}), email=email, first_name=(names.get("firstName") or "")[:150],
                    last_name=(names.get("lastName") or "")[:150], apple_sub=sub, email_verified_at=timezone.now())
        user.set_unusable_password()
        inviter = User.objects.filter(username__iexact=request.session.pop("ref", ""), is_active=True).first()
        if inviter:
            user.invited_by = inviter
        user.save()
    if not user.is_active:
        return None, "Bu hisob yopilgan."
    if user.is_staff or user.is_superuser:
        return None, _t("Xodim hisoblari Apple orqali kira olmaydi. Parol bilan kiring.")
    return user, ""


@csrf_exempt  # Apple posts the form from its own page: the signed state cookie stands in for the CSRF token
def callback(request):
    if not configured() or request.method != "POST":
        return redirect("login")
    try:
        saved = signing.loads(request.COOKIES.get(COOKIE, ""), salt=COOKIE, max_age=MAX_AGE)
    except signing.BadSignature:
        saved = {}
    state = request.POST.get("state", "")
    if request.POST.get("error") or not saved or not state or not secrets.compare_digest(state, saved["s"]):
        messages.error(request, _t("Apple orqali kirish bekor qilindi yoki eskirdi. Qaytadan urinib ko‘ring."))
        return redirect("login")
    if throttle.ip_blocked(request, "apple", 30, 600):
        messages.error(request, throttle.TOO_MANY)
        return redirect("login")
    try:
        token = _post_form(TOKEN_URL, {
            "code": request.POST.get("code", ""), "client_id": settings.APPLE_CLIENT_ID,
            "client_secret": _client_secret(), "redirect_uri": _redirect_uri(request), "grant_type": "authorization_code"})
        claims = _claims(token["id_token"])
    except (urllib.error.URLError, ValueError, KeyError, IndexError, OSError):
        messages.error(request, _t("Apple bilan aloqa bo‘lmadi. Birozdan keyin qayta urinib ko‘ring."))
        return redirect("login")
    nonce_ok = claims.get("nonce") in (saved["n"], hashlib.sha256(saved["n"].encode()).hexdigest())
    if claims.get("iss") != ISSUER or claims.get("aud") != settings.APPLE_CLIENT_ID or claims.get("exp", 0) < time.time() or not nonce_ok:
        messages.error(request, _t("Apple orqali kirish bekor qilindi yoki eskirdi. Qaytadan urinib ko‘ring."))
        return redirect("login")
    if not (claims.get("sub") and claims.get("email") and str(claims.get("email_verified")).lower() == "true"):
        messages.error(request, _t("Apple emailingizni tasdiqlanmagan deb ko‘rsatdi: boshqa usul bilan kiring."))
        return redirect("login")
    try:  # the name comes once, as a JSON field of the first sign-in
        names = json.loads(request.POST.get("user") or "{}").get("name") or {}
    except ValueError:
        names = {}
    user, error = _user_for(request, claims, names)
    if user is None:
        messages.error(request, error)
        return redirect("login")
    auth_login(request, user, backend=BACKEND)
    response = redirect(saved.get("next") or "home")
    response.delete_cookie(COOKIE, samesite="None" if request.is_secure() else "Lax")
    return response
