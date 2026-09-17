from django.urls import path

from . import views

app_name = "contests"

urlpatterns = [
    path("", views.contest_list, name="list"),
    path("<int:pk>/", views.contest_detail, name="detail"),
    path("<int:pk>/register/", views.register, name="register"),
    path("<int:pk>/standings/", views.standings, name="standings"),
]
