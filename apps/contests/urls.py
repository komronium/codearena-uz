from django.urls import path

from . import views

app_name = "contests"

urlpatterns = [
    path("", views.contest_list, name="list"),
    path("<int:pk>/", views.contest_detail, name="detail"),
    path("<int:pk>/register/", views.register, name="register"),
    path("<int:pk>/standings/", views.standings, name="standings"),
    path("<int:pk>/disqualify/<int:user_id>/", views.disqualify, name="disqualify"),
    path("<int:pk>/clarifications/", views.clarifications, name="clarifications"),
    path("<int:pk>/clarifications/ask/", views.ask_clarification, name="ask_clarification"),
    path("<int:pk>/clarifications/<int:cid>/answer/", views.answer_clarification, name="answer_clarification"),
]
