from django.urls import path

from . import views

app_name = "contests"

urlpatterns = [
    path("", views.contest_list, name="list"),
    path("<int:pk>/", views.contest_detail, name="detail"),
    path("<int:pk>/register/", views.register, name="register"),
    path("<int:pk>/calendar.ics", views.calendar_ics, name="calendar"),
    path("<int:pk>/virtual/", views.virtual_start, name="virtual"),
    path("<int:pk>/standings/", views.standings, name="standings"),
    path("<int:pk>/submissions/", views.submissions, name="submissions"),
    path("<int:pk>/disqualify/<int:user_id>/", views.disqualify, name="disqualify"),
    path("<int:pk>/void/<int:user_id>/", views.void, name="void"),
    path("<int:pk>/clarifications/", views.clarifications, name="clarifications"),
    path("<int:pk>/clarifications/ask/", views.ask_clarification, name="ask_clarification"),
    path("<int:pk>/clarifications/<int:cid>/answer/", views.answer_clarification, name="answer_clarification"),
]
