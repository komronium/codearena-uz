import secrets

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "student"
        TEACHER = "teacher"
        ADMIN = "admin"

    rating = models.IntegerField(default=0, db_index=True)  # shown rating; see apps.contests.rating
    practice_points = models.IntegerField(default=0, db_index=True)
    duel_rating = models.IntegerField(default=1200)  # 1v1 duels only (apps.classroom.duels)
    # From supervised contests only (apps.contests.rating.recalc_official); None until the first one.
    official_rating = models.IntegerField(null=True, blank=True, db_index=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    location = models.CharField(max_length=100, blank=True)
    school = models.CharField(max_length=150, blank=True)
    invited_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="invited_users",
    )
    # "I'm a teacher" at sign-up or from the profile; staff approve it by giving the teacher role
    teacher_requested = models.BooleanField(default=False, db_index=True)
    # the tier the user was last shown; a higher one on the next page view gets a congratulation
    seen_tier = models.CharField(max_length=30, blank=True)
    # when the user promised to submit only their own work (accounts:honor); asked once
    honor_pledged_at = models.DateTimeField(null=True, blank=True)
    # A teacher or admin confirmed this is the real student; only verified users get an official rating
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="verified_users",
    )
    verified_note = models.CharField(max_length=200, blank=True)


class TelegramLink(models.Model):
    """A user's private Telegram chat and their notification preferences."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="telegram_link"
    )
    chat_id = models.CharField(max_length=32, unique=True)
    username = models.CharField(max_length=64, blank=True)
    connected_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    notify_daily_problem = models.BooleanField(default=True)
    notify_daily_tip = models.BooleanField(default=True)
    notify_trending_problem = models.BooleanField(default=True)
    notify_contests = models.BooleanField(default=True)
    notify_assignments = models.BooleanField(default=True)
    last_error = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"Telegram: {self.user.username}"


class TelegramLinkToken(models.Model):
    """Hashed, single-use deep-link credential with a short expiry."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="telegram_link_tokens"
    )
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class TelegramOutbox(models.Model):
    """Durable notification queue; Redis delivery is fast, this row allows retry after outages."""

    class Status(models.TextChoices):
        PENDING = "pending", "Kutilmoqda"
        SENDING = "sending", "Yuborilmoqda"
        SENT = "sent", "Yuborildi"
        FAILED = "failed", "Xato"

    link = models.ForeignKey(TelegramLink, on_delete=models.CASCADE, related_name="outbox")
    event_key = models.CharField(max_length=160)
    preference = models.CharField(max_length=32)
    text = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    available_at = models.DateTimeField(default=timezone.now)
    queued_at = models.DateTimeField(null=True, blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=300, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["link", "event_key"], name="telegram_outbox_event_once")]
        indexes = [models.Index(fields=["status", "available_at"], name="accounts_tg_status_avail_idx")]


_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def new_join_code() -> str:
    while True:
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))
        if not Group.objects.filter(join_code=code).exists():
            return code


class Group(models.Model):
    name = models.CharField(max_length=100)
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="taught_groups")
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="student_groups")
    # students join with this code; no ambiguous letters (0/O, 1/I/L) so it reads out loud in class
    join_code = models.CharField(max_length=8, unique=True, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.join_code:
            self.join_code = new_join_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
