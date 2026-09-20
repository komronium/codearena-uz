from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("django-rq/", include("django_rq.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("problems/", include("apps.problems.urls")),
    path("contests/", include("apps.contests.urls")),
    path("submissions/", include("apps.submissions.urls")),
    path("integrity/", include("apps.integrity.urls")),
    path("moderation/", include("apps.moderation.urls")),
    path("", RedirectView.as_view(pattern_name="problems:list", permanent=False)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
