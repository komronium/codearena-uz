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
    path("<int:pk>/remind/", views.assignment_remind, name="remind"),
    path("review/<int:pk>/", views.review, name="review"),
    path("live/", views.live_join, name="live_join"),
    path("live/new/", views.live_new, name="live_new"),
    path("live/<str:code>/host/", views.live_host, name="live_host"),
    path("live/<str:code>/host/state/", views.live_host_state, name="live_host_state"),
    path("live/<str:code>/host/act/", views.live_act, name="live_act"),
    path("live/<str:code>/play/", views.live_play, name="live_play"),
    path("live/<str:code>/play/state/", views.live_play_state, name="live_play_state"),
    path("live/<str:code>/play/answer/", views.live_answer, name="live_answer"),
    path("duels/", views.duel_list, name="duels"),
    path("duels/people/", views.duel_people, name="duel_people"),
    path("duels/<int:pk>/", views.duel_detail, name="duel"),
    path("duels/<int:pk>/answer/", views.duel_answer, name="duel_answer"),
    path("duels/<int:pk>/play/", views.duel_play, name="duel_play"),
    path("duels/<int:pk>/rematch/", views.duel_rematch, name="duel_rematch"),
]
