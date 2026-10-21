"""The page language: a cookie the language switch sets, else the language saved on the account, else Uzbek (the
source language). Not the browser's Accept-Language: the site is Uzbek-first and an English browser alone is no reason."""
from django.conf import settings
from django.http import HttpResponseRedirect
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

COOKIE = "ca_lang"
CODES = [code for code, _ in settings.LANGUAGES]


def pick(request) -> str:
    cookie = request.COOKIES.get(COOKIE, "")
    if cookie in CODES:
        return cookie
    user = getattr(request, "user", None)
    saved = getattr(user, "language", "") if user is not None and user.is_authenticated else ""
    return saved if saved in CODES else settings.LANGUAGE_CODE


class LanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        lang = pick(request)
        translation.activate(lang)
        request.LANGUAGE_CODE = lang
        try:
            response = self.get_response(request)
        finally:
            translation.deactivate()
        response.headers.setdefault("Content-Language", lang)
        from django.utils.cache import patch_vary_headers
        patch_vary_headers(response, ("Cookie",))
        return response


@require_POST
def set_language(request):
    """The language switch: remember the choice in a cookie (and on the account), go back where the person was."""
    lang = request.POST.get("language", "")
    nxt = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        nxt = "/"
    response = HttpResponseRedirect(nxt)
    if lang in CODES:
        response.set_cookie(COOKIE, lang, max_age=365 * 24 * 3600, samesite="Lax", secure=request.is_secure())
        if request.user.is_authenticated and request.user.language != lang:
            request.user.language = lang
            request.user.save(update_fields=["language"])
    return response
