from django.urls import path

from . import views

app_name = "integrity"

urlpatterns = [
    path("event/", views.event, name="event"),
    path("contest/<int:pk>/", views.contest_report, name="contest_report"),
    path("flag/<int:pk>/review/", views.flag_review, name="flag_review"),
    path("contest/<int:pk>/flag-run/", views.flag_run, name="flag_run"),
]
