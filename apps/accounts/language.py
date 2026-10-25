"""The page language. A page has one address per language so a search engine can index both: Uzbek (the source
language) at the plain path, every other language under its code (/en/problems/). Where the address names no
language (a script's hard-coded path, a file, the API) it is the cookie the language switch sets, else the language
saved on the account, else Uzbek. Not the browser's Accept-Language: the site is Uzbek-first and an English
browser alone is no reason."""
from django.conf import settings
from django.http import HttpResponsePermanentRedirect, HttpResponseRedirect
from django.urls import set_script_prefix
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

COOKIE = "ca_lang"
CODES = [code for code, _ in settings.LANGUAGES]
PATH_CODES = [code for code in CODES if code != settings.LANGUAGE_CODE]  # the languages with a prefix
# what exists once, whatever the language (files, machine endpoints, the crawlers' files): no prefix is added to these
# addresses by the switch or the redirect, though reverse() puts one on them in an English page and so they answer there too
NEUTRAL = ("api/", "media/", "static/", "django-rq/", "i18n/", "robots.txt", "sitemap", "healthz", "favicon.ico",
           "manifest.webmanifest")


def split_path(path: str) -> tuple[str, str]:
    """("en", "/problems/") for "/en/problems/"; ("", path) for a path without a language prefix."""
    for code in PATH_CODES:
        if path == f"/{code}":
            return code, "/"
        if path.startswith(f"/{code}/"):
            return code, path[len(code) + 1:]
    return "", path


def localize(path: str, lang: str) -> str:
    """The same address (path and query) in `lang`."""
    bare = split_path(path)[1]
    if lang in PATH_CODES and not bare[1:].startswith(NEUTRAL):
        return f"/{lang}{bare}"
    return bare


def preferred(request) -> str:
    """The language the person chose: the cookie, then the account."""
    cookie = request.COOKIES.get(COOKIE, "")
    if cookie in CODES:
        return cookie
    user = getattr(request, "user", None)
    saved = getattr(user, "language", "") if user is not None and user.is_authenticated else ""
    return saved if saved in CODES else settings.LANGUAGE_CODE


def pick(request) -> str:
    return getattr(request, "path_language", "") or preferred(request)


class LanguagePathMiddleware:
    """First in line: /en/problems/ is the site's /problems/ in English. The prefix leaves path_info, so the
    urlconf and every path check see the plain path; it stays in request.path (canonical and next= addresses) and
    in the script prefix, which puts it in front of every address reverse() builds."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        code, bare = split_path(request.path_info)
        if code:
            if request.path_info == f"/{code}":  # one address for the home page
                return HttpResponsePermanentRedirect(f"/{code}/" + (f"?{request.META['QUERY_STRING']}" if request.META.get("QUERY_STRING") else ""))
            request.path_info = bare
            request.path_language = code
            set_script_prefix(f"/{code}/")
        return self.get_response(request)


def _is_page_visit(request) -> bool:
    """A person's navigation to a page (not a script's request, a file or a crawler's list)."""
    return (request.method in ("GET", "HEAD") and "text/html" in request.headers.get("Accept", "")
            and "HX-Request" not in request.headers and not request.path_info[1:].startswith(NEUTRAL))


class LanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        lang = pick(request)
        # someone who chose another language is taken to the page's address in it; a crawler has no cookie and stays
        if lang != settings.LANGUAGE_CODE and not getattr(request, "path_language", "") and _is_page_visit(request):
            return HttpResponseRedirect(localize(request.get_full_path(), lang))
        translation.activate(lang)
        request.LANGUAGE_CODE = lang
        try:
            response = self.get_response(request)
        finally:
            translation.deactivate()
        if getattr(request, "path_language", "") and request.COOKIES.get(COOKIE) != lang:
            # following a link to the English page is a choice too: its other links and the scripts stay in it
            response.set_cookie(COOKIE, lang, max_age=365 * 24 * 3600, samesite="Lax", secure=request.is_secure())
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
    response = HttpResponseRedirect(localize(nxt, lang) if lang in CODES else nxt)
    if lang in CODES:
        response.set_cookie(COOKIE, lang, max_age=365 * 24 * 3600, samesite="Lax", secure=request.is_secure())
        if request.user.is_authenticated and request.user.language != lang:
            request.user.language = lang
            request.user.save(update_fields=["language"])
    return response
