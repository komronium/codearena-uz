from django.urls import path

from . import views

app_name = "api"

urlpatterns = [
    path("", views.index, name="index"),
    path("meta/", views.meta, name="meta"),
    path("contests/", views.contest_list, name="contests"),
    path("contests/<int:pk>/", views.contest_detail, name="contest"),
    path("contests/<int:pk>/standings/", views.standings, name="standings"),
    path("contests/<int:pk>/clist-standings/", views.clist_standings, name="clist_standings"),
    path("problems/", views.problem_list, name="problems"),
    path("problems/<slug:slug>/", views.problem_detail, name="problem"),
    path("users/", views.user_list, name="users"),
    path("users/<str:username>/", views.user_detail, name="user"),
    path("users/<str:username>/ratings/", views.user_ratings, name="user_ratings"),
]
