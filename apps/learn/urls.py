from django.urls import path

from . import views

app_name = "learn"
urlpatterns = [
    path("", views.hub, name="hub"),
    path("search/", views.course_search, name="search"),
    path("plans/<slug:slug>/", views.plan_redirect, name="plan"),  # old course links
    path("topics/", views.topics, name="topics"),  # old Qo‘llanma links
    path("topics/<str:name>/", views.topic_redirect, name="topic"),
    path("lists/", views.lists, name="lists"),
    path("lists/<int:pk>/", views.list_detail, name="list"),
    path("lists/<int:pk>/edit/", views.list_edit, name="list_edit"),
    path("lists/<int:pk>/delete/", views.list_delete, name="list_delete"),
    path("save/<slug:slug>/", views.save, name="save"),
    path("<slug:slug>/", views.course_detail, name="course"),  # last: slugs in RESERVED_SLUGS never reach it
]
