from django.urls import path

from . import translations, views

app_name = "moderation"
urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("daily-problem/", views.daily_problem, name="daily_problem"),
    path("daily-problem/choose/", views.daily_problem_choose, name="daily_problem_choose"),
    path("daily-problem/clear/", views.daily_problem_clear, name="daily_problem_clear"),
    path("queue/", views.queue, name="queue"),
    path("<int:pk>/approve/", views.approve, name="approve"),
    path("<int:pk>/reject/", views.reject, name="reject"),

    path("problems/", views.problems, name="problems"),
    path("translations/", translations.index, name="translations"),
    path("translations/ai-all/<str:kind>/", translations.ai_all, name="translation_ai_all"),
    path("translations/confirm-all/<str:kind>/", translations.confirm_all, name="translation_confirm_all"),
    path("translations/<str:kind>/<int:pk>/", translations.edit, name="translation_edit"),
    path("translations/<str:kind>/<int:pk>/ai/", translations.ai_one, name="translation_ai"),
    path("translations/<str:kind>/<int:pk>/confirm/", translations.confirm_one, name="translation_confirm"),
    path("upload-image/", views.upload_image, name="upload_image"),
    path("ai/", views.ai_generate, name="ai_generate"),
    path("mine/", views.mine, name="mine"),
    path("submit/", views.submit, name="submit"),
    path("problems/bulk/", views.problems_bulk, name="problems_bulk"),
    path("problems/<int:pk>/edit/", views.submit, name="problem_edit"),
    path("problems/<int:pk>/toggle/", views.problem_toggle, name="problem_toggle"),
    path("problems/<int:pk>/delete/", views.problem_delete, name="problem_delete"),
    path("problems/<int:pk>/rejudge/", views.problem_rejudge, name="problem_rejudge"),
    path("tags/", views.tags, name="tags"),
    path("tags/<int:pk>/edit/", views.tag_edit, name="tag_edit"),
    path("tags/<int:pk>/delete/", views.tag_delete, name="tag_delete"),
    path("tags/<int:pk>/merge/", views.tag_merge, name="tag_merge"),

    path("plans/", views.plans, name="plans"),
    path("plans/new/", views.plan_edit, name="plan_new"),
    path("plans/<int:pk>/edit/", views.plan_edit, name="plan_edit"),
    path("plans/<int:pk>/delete/", views.plan_delete, name="plan_delete"),
    path("plans/<int:pk>/move/", views.plan_move, name="plan_move"),

    path("contests/", views.contests, name="contests"),
    path("contests/new/", views.contest_edit, name="contest_new"),
    path("contests/<int:pk>/edit/", views.contest_edit, name="contest_edit"),
    path("contests/<int:pk>/delete/", views.contest_delete, name="contest_delete"),
    path("contests/<int:pk>/apply-rating/", views.contest_apply_rating, name="contest_apply_rating"),
    path("contests/<int:pk>/publish/", views.contest_publish, name="contest_publish"),
    path("contests/<int:pk>/unpublish/", views.contest_unpublish, name="contest_unpublish"),
    path("contests/<int:pk>/draft-publish/", views.contest_draft_publish, name="contest_draft_publish"),
    path("contests/<int:pk>/rating-preview/", views.contest_rating_preview, name="contest_rating_preview"),

    path("submissions/", views.submissions, name="submissions"),
    path("duels/", views.duels, name="duels"),
    path("duels/switch/", views.duel_switch, name="duel_switch"),
    path("duels/<int:pk>/", views.duel_detail, name="duel_detail"),
    path("duels/<int:pk>/void/", views.duel_void, name="duel_void"),
    path("rating/", views.rating_stats, name="rating_stats"),
    path("search/", views.search, name="search"),
    path("users/", views.users, name="users"),
    path("users/<int:pk>/edit/", views.user_edit, name="user_edit"),
    path("users/<int:pk>/delete/", views.user_delete, name="user_delete"),

]
