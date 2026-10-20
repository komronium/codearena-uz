from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "student"
        ADMIN = "admin"

    rating = models.IntegerField(default=0, db_index=True)  # shown rating; see apps.contests.rating
    practice_points = models.IntegerField(default=0, db_index=True)
    duel_rating = models.IntegerField(default=1200)  # 1v1 duels only (apps.classroom.duels)
    duel_season = models.CharField(max_length=7, blank=True, default="")  # the month (YYYY-MM) its rating was last softened for
    # From supervised contests only (apps.contests.rating.recalc_official); None until the first one.
    official_rating = models.IntegerField(null=True, blank=True, db_index=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    country = models.CharField(max_length=2, blank=True)  # ISO 3166-1 alpha-2, see apps.accounts.countries
    location = models.CharField(max_length=100, blank=True)  # the city
    school = models.CharField(max_length=150, blank=True)
    # may write problems (moderation.submit): they land in the staff queue as pending and carry the author's name once
    # approved. Set by staff in the user's edit form.
    is_setter = models.BooleanField(default=False)
    # a school or club the person belongs to (accounts.clubs): one at a time, read-only pages, no teacher role
    club = models.ForeignKey("accounts.Club", null=True, blank=True, on_delete=models.SET_NULL, related_name="members")
    # Google's stable account id ("sub") once the person has signed in with Google (accounts.google); empty otherwise
    google_sub = models.CharField(max_length=64, null=True, blank=True, unique=True)
    invited_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="invited_users",
    )
    # the tier the user was last shown; a higher one on the next page view gets a congratulation
    seen_tier = models.CharField(max_length=30, blank=True)
    # when the user promised to submit only their own work (accounts:honor); asked once
    honor_pledged_at = models.DateTimeField(null=True, blank=True)
    # An admin confirmed this is the real student; only verified users get an official rating
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="verified_users",
    )
    verified_note = models.CharField(max_length=200, blank=True)
    # the address in `email` was confirmed by its link (apps.accounts.onboarding); None = not yet, so the
    # account waits on the welcome page
    email_verified_at = models.DateTimeField(null=True, blank=True)
    # the last time the user renamed themselves; once per USERNAME_CHANGE_DAYS
    username_changed_at = models.DateTimeField(null=True, blank=True)

    @property
    def country_name(self) -> str:
        from .countries import country_name
        return country_name(self.country)


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
    notify_duels = models.BooleanField(default=True)  # an invite, and how a duel ended
    notify_badges = models.BooleanField(default=True)  # a badge level reached
    notify_streak = models.BooleanField(default=True)  # the evening before a daily streak would break
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


class TelegramLoginRequest(models.Model):
    """"Telegram orqali kirish": a browser asks, the bot confirms for the linked account, the browser that asked
    (it holds the raw token in its session) then signs in. Hashed, short-lived, single-use."""

    token_hash = models.CharField(max_length=64, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
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


class UserBadge(models.Model):
    """One level (tier) of a badge family a user reached (apps.accounts.badges), kept for good: a level once
    earned stays even if what earned it changes later. `seen` is for the "new badge" toast."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="badges")
    family = models.CharField(max_length=30)
    tier = models.PositiveSmallIntegerField()
    earned_at = models.DateTimeField(auto_now_add=True)
    seen = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "family", "tier"], name="one_row_per_badge_tier")]


class Follow(models.Model):
    """"Kuzatish": the feed (apps.accounts.feed) shows what the people you follow did."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="following")
    target = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="followers")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "target"], name="one_follow_per_pair"),
                       models.CheckConstraint(condition=~models.Q(user=models.F("target")), name="no_self_follow")]


class Notification(models.Model):
    """One line in the top bar's bell (apps.accounts.notifications): something happened that is yours to see —
    a duel call or result, a badge. Made once per (user, key); read when opened."""

    class Kind(models.TextChoices):
        DUEL = "duel", "Duel"
        BADGE = "badge", "Nishon"
        REPORT = "report", "Murojaat"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    text = models.CharField(max_length=200)
    url = models.CharField(max_length=300)
    key = models.CharField(max_length=160)  # the event, so it is never told twice
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created", "-id"]
        constraints = [models.UniqueConstraint(fields=["user", "key"], name="one_notification_per_event")]


class Club(models.Model):
    """A school or club: a name, a page with its members and their results, a join link. Not a classroom: there are no
    assignments and no teacher role; the creator can only rename it and share the link."""
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True)
    join_code = models.CharField(max_length=16)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
