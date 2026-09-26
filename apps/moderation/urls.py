from django.urls import path

from . import views

app_name = "moderation"
urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("queue/", views.queue, name="queue"),
    path("<int:pk>/approve/", views.approve, name="approve"),
    path("<int:pk>/reject/", views.reject, name="reject"),

    path("problems/", views.problems, name="problems"),
    path("ai/", views.ai_generate, name="ai_generate"),
    path("submit/", views.submit, name="submit"),
    path("problems/<int:pk>/edit/", views.submit, name="problem_edit"),
    path("problems/<int:pk>/toggle/", views.problem_toggle, name="problem_toggle"),
    path("problems/<int:pk>/delete/", views.problem_delete, name="problem_delete"),
    path("problems/<int:pk>/rejudge/", views.problem_rejudge, name="problem_rejudge"),
    path("tags/", views.tags, name="tags"),
    path("tags/<int:pk>/delete/", views.tag_delete, name="tag_delete"),

    path("contests/", views.contests, name="contests"),
    path("contests/new/", views.contest_edit, name="contest_new"),
    path("contests/<int:pk>/edit/", views.contest_edit, name="contest_edit"),
    path("contests/<int:pk>/delete/", views.contest_delete, name="contest_delete"),
    path("contests/<int:pk>/apply-rating/", views.contest_apply_rating, name="contest_apply_rating"),
    path("contests/<int:pk>/publish/", views.contest_publish, name="contest_publish"),

    path("submissions/", views.submissions, name="submissions"),
    path("users/", views.users, name="users"),
    path("users/<int:pk>/edit/", views.user_edit, name="user_edit"),

    path("groups/", views.groups, name="groups"),
    path("groups/new/", views.group_edit, name="group_new"),
    path("groups/<int:pk>/edit/", views.group_edit, name="group_edit"),
    path("groups/<int:pk>/delete/", views.group_delete, name="group_delete"),
]
