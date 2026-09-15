from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("django-rq/", include("django_rq.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("problems/", include("apps.problems.urls")),
    path("submissions/", include("apps.submissions.urls")),
    path("", RedirectView.as_view(pattern_name="problems:list", permanent=False)),
]
