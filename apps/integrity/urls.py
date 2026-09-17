from django.urls import path

from . import views

app_name = "integrity"

urlpatterns = [
    path("event/", views.event, name="event"),
    path("contest/<int:pk>/", views.contest_report, name="contest_report"),
]
