from django.urls import path

from . import views

app_name = "integrity"

urlpatterns = [
    path("event/", views.event, name="event"),
    path("snapshot/", views.snapshot, name="snapshot"),
    path("beat/", views.beat, name="beat"),
    path("practice/event/", views.practice_event, name="practice_event"),
    path("practice/snapshot/", views.practice_snapshot, name="practice_snapshot"),
    path("practice/", views.practice_report, name="practice_report"),
    path(
        "practice/<int:user_id>/<int:problem_id>/",
        views.practice_decide,
        name="practice_decide",
    ),
    path("audit/", views.audit_log, name="audit"),
    path("contest/<int:pk>/", views.contest_report, name="contest_report"),
    path(
        "contest/<int:pk>/replay/<int:user_id>/<int:problem_id>/",
        views.replay,
        name="replay",
    ),
    path("flag/<int:pk>/review/", views.flag_review, name="flag_review"),
    path("contest/<int:pk>/flag-run/", views.flag_run, name="flag_run"),
]
