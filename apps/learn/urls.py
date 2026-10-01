from django.urls import path

from . import views

app_name = "learn"
urlpatterns = [
    path("", views.hub, name="hub"),
    path("plans/<slug:slug>/", views.plan_detail, name="plan"),
    path("topics/", views.topics, name="topics"),
    path("topics/<str:name>/", views.topic_detail, name="topic"),
    path("lists/", views.lists, name="lists"),
    path("lists/<int:pk>/", views.list_detail, name="list"),
    path("lists/<int:pk>/edit/", views.list_edit, name="list_edit"),
    path("lists/<int:pk>/delete/", views.list_delete, name="list_delete"),
    path("save/<slug:slug>/", views.save, name="save"),
]
