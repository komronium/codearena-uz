from django.urls import path

from . import views

app_name = "submissions"
urlpatterns = [
    path("", views.mine, name="mine"),
    path("submit/<slug:slug>/", views.submit, name="submit"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/status/", views.status, name="status"),
]
