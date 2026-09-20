from django.urls import path

from . import views

app_name = "moderation"
urlpatterns = [
    path("", views.queue, name="queue"),
    path("submit/", views.submit, name="submit"),
    path("<int:pk>/approve/", views.approve, name="approve"),
    path("<int:pk>/reject/", views.reject, name="reject"),
]
