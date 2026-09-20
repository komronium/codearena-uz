from django.conf import settings
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from django.views.static import serve

urlpatterns = [
    path("django-rq/", include("django_rq.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("problems/", include("apps.problems.urls")),
    path("contests/", include("apps.contests.urls")),
    path("submissions/", include("apps.submissions.urls")),
    path("integrity/", include("apps.integrity.urls")),
    path("moderation/", include("apps.moderation.urls")),
    path("", RedirectView.as_view(pattern_name="problems:list", permanent=False)),
]

# ponytail: Django serves avatars itself in prod too; put nginx in front when traffic grows.
urlpatterns += [re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT})]
