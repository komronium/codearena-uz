from django.conf import settings
from django.contrib.sitemaps import views as sitemaps
from django.urls import include, path, re_path
from django.views.static import serve

from apps.home.sitemaps import SITEMAPS
from apps.accounts.language import set_language
from apps.home.views import favicon, healthz, home, manifest, robots_txt

urlpatterns = [
    path("django-rq/", include("django_rq.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("problems/", include("apps.problems.urls")),
    path("contests/", include("apps.contests.urls")),
    path("submissions/", include("apps.submissions.urls")),
    path("integrity/", include("apps.integrity.urls")),
    path("moderation/", include("apps.moderation.urls")),
    path("classroom/", include("apps.classroom.urls")),
    path("learn/", include("apps.learn.urls")),
    path("api/v1/", include("apps.api.urls")),
    path("robots.txt", robots_txt, name="robots"),
    # an index of one sitemap per kind of page, so Search Console reports each kind's indexing apart
    path("sitemap.xml", sitemaps.index, {"sitemaps": SITEMAPS, "sitemap_url_name": "sitemap_section"},
         name="sitemap"),
    path("sitemap-<section>.xml", sitemaps.sitemap, {"sitemaps": SITEMAPS}, name="sitemap_section"),
    path("favicon.ico", favicon, name="favicon"),
    path("healthz", healthz, name="healthz"),
    path("i18n/language/", set_language, name="set_language"),
    path("manifest.webmanifest", manifest, name="manifest"),
    path("", home, name="home"),
]

# ponytail: Django serves avatars itself in prod too; put nginx in front when traffic grows.
def _media(request, path):
    """Uploaded files (avatars, statement images) are data, never a page: a sandboxed, non-sniffed response, so an
    uploaded SVG cannot run script on the site's origin."""
    response = serve(request, path, document_root=settings.MEDIA_ROOT)
    response["Content-Security-Policy"] = "sandbox; default-src 'none'; img-src 'self'; style-src 'unsafe-inline'"
    response["X-Content-Type-Options"] = "nosniff"
    return response


urlpatterns += [re_path(r"^media/(?P<path>.*)$", _media)]
