from django.urls import path

from . import views

app_name = "submissions"
urlpatterns = [
    path("", views.mine, name="mine"),
    path("submit/<slug:slug>/", views.submit, name="submit"),
    path("trial/<slug:slug>/", views.trial, name="trial"),
    path("trial-guest/<slug:slug>/", views.guest_trial, name="guest_trial"),
    path("trial-guest/job/<str:job_id>/", views.guest_trial_status, name="guest_trial_status"),
    path("trial/job/<str:job_id>/", views.trial_status, name="trial_status"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/status/", views.status, name="status"),
]
