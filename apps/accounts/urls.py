from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views
from . import telegram_views

urlpatterns = [
    path("login/", views.Login.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("register/", views.register, name="register"),
    path("top/", views.top, name="top"),
    path("rating/", views.rating, name="rating"),
    path("friends/", views.feed, name="feed"),
    path("profile/<str:username>/follow/", views.follow_toggle, name="follow"),
    path("rating/duels/", views.duel_board, name="duel_board"),
    path("rating/badges/", views.badge_board, name="badge_board"),
    path("badges/", views.badges_page, name="badges"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path("welcome/", views.welcome, name="welcome"),
    path("export/", views.export_data, name="export_data"),
    path("notifications/<int:pk>/", views.notification_open, name="notification_open"),
    path("notifications/read/", views.notifications_read, name="notifications_read"),
    path("verify-email/<str:token>/", views.verify_email, name="verify_email"),
    path("telegram/login/", telegram_views.login_start, name="telegram_login"),
    path("telegram/login/status/", telegram_views.login_status, name="telegram_login_status"),
    path("telegram/connect/", telegram_views.connect, name="telegram_connect"),
    path("telegram/disconnect/", telegram_views.disconnect, name="telegram_disconnect"),
    path("telegram/preferences/", telegram_views.preferences, name="telegram_preferences"),
    path("telegram/webhook/", telegram_views.webhook, name="telegram_webhook"),
    path("honor/", views.honor, name="honor"),
    path("verify/<int:user_id>/", views.verify_user, name="verify_user"),
    path("password-change/", views.PasswordChange.as_view(), name="password_change"),
    path("profile/<str:username>/", views.profile, name="profile"),
    path("password-reset/", views.PasswordReset.as_view(
        success_url=reverse_lazy("password_reset_done")), name="password_reset"),
    path("password-reset/done/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        success_url=reverse_lazy("password_reset_complete")), name="password_reset_confirm"),
    path("reset/done/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
]
