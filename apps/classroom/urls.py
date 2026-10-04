from django.urls import path

from . import views

app_name = "classroom"

urlpatterns = [
    path("", views.assignment_list, name="list"),
    path("new/", views.assignment_edit, name="new"),
    path("groups/new/", views.group_create, name="group_new"),
    path("groups/join/", views.group_join, name="group_join"),
    path("groups/<int:pk>/remove/<int:user_id>/", views.group_remove_member, name="group_remove"),
    path("<int:pk>/", views.assignment_detail, name="detail"),
    path("<int:pk>/edit/", views.assignment_edit, name="edit"),
    path("review/<int:pk>/", views.review, name="review"),
    path("duels/", views.duel_list, name="duels"),
    path("duels/people/", views.duel_people, name="duel_people"),
    path("duels/<int:pk>/", views.duel_detail, name="duel"),
    path("duels/<int:pk>/answer/", views.duel_answer, name="duel_answer"),
]
