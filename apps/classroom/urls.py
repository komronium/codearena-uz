from django.urls import path

from . import views

app_name = "classroom"

urlpatterns = [
    path("", views.assignment_list, name="list"),
    path("new/", views.assignment_edit, name="new"),
    path("<int:pk>/", views.assignment_detail, name="detail"),
    path("<int:pk>/edit/", views.assignment_edit, name="edit"),
    path("review/<int:pk>/", views.review, name="review"),
    path("duels/", views.duel_list, name="duels"),
    path("duels/<int:pk>/", views.duel_detail, name="duel"),
    path("duels/<int:pk>/answer/", views.duel_answer, name="duel_answer"),
]
