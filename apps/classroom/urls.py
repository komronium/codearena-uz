from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "classroom"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="classroom:duels", permanent=True)),  # the old Sinf page
    path("duels/", views.duel_list, name="duels"),
    path("duels/people/", views.duel_people, name="duel_people"),
    path("duels/<int:pk>/", views.duel_detail, name="duel"),
    path("duels/<int:pk>/answer/", views.duel_answer, name="duel_answer"),
    path("duels/<int:pk>/play/", views.duel_play, name="duel_play"),
    path("duels/<int:pk>/rematch/", views.duel_rematch, name="duel_rematch"),
]
