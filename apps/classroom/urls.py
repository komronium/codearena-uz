from django.urls import path

from . import views

app_name = "classroom"

urlpatterns = [
    path("", views.assignment_list, name="list"),
    path("new/", views.assignment_edit, name="new"),
    path("<int:pk>/", views.assignment_detail, name="detail"),
    path("<int:pk>/edit/", views.assignment_edit, name="edit"),
]
