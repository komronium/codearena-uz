from typing import ClassVar

from django.conf import settings
from django.db import models

from apps.contests.models import Contest
from apps.problems.models import Language, Problem
from apps.submissions.models import Submission


class FocusEvent(models.Model):
    class Kind(models.TextChoices):
        BLUR = "blur"
        FOCUS = "focus"
        PASTE = "paste"
        COPY = "copy"
        FAST = "fast"  # sustained abnormal typing speed (evades the single-bulk-insert threshold)
        VIEW = "view"  # a contest problem page was opened: start of that problem's clock

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="focus_events")
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name="focus_events")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    # the contest problem page it happened on; None on the contest's own page
    problem = models.ForeignKey(Problem, null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    # on FOCUS: how long the participant was away since the matching BLUR
    away_ms = models.PositiveIntegerField(null=True, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes: ClassVar[list[models.Index]] = [models.Index(fields=["contest", "user"])]


class SimilarityFlag(models.Model):
    submission_a = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="+")
    submission_b = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="+")
    score = models.FloatField()
    reviewed = models.BooleanField(default=False)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-score"]


class CodeSnapshot(models.Model):
    """Editor contents saved every few seconds during a contest, so staff can replay
    how a solution was written: typed and reworked, or transcribed top to bottom."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name="+")
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name="+")
    language = models.ForeignKey(Language, null=True, on_delete=models.SET_NULL, related_name="+")
    source = models.TextField()
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes: ClassVar[list[models.Index]] = [models.Index(fields=["contest", "user", "problem", "at"])]


class DeviceSeen(models.Model):
    """A browser (random id kept in its localStorage) a participant used during a contest,
    from the tracker heartbeat. Two users on one device, or one user on two devices at
    the same time, is evidence for staff."""
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name="+")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    device = models.CharField(max_length=64)
    ip = models.GenericIPAddressField(null=True, blank=True)  # the last one seen
    first_at = models.DateTimeField(auto_now_add=True)
    last_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("contest", "user", "device")


class AuditEntry(models.Model):
    """Who did what to a result, and why. Links are SET_NULL so the record outlives them."""
    class Action(models.TextChoices):
        DISQUALIFY = "disqualify", "Diskvalifikatsiya"
        REQUALIFY = "requalify", "Diskvalifikatsiya bekor"
        REJUDGE = "rejudge", "Qayta tekshiruv"
        PUBLISH = "publish", "Masalalar ochildi"
        RATING_APPLY = "rating_apply", "Reyting hisoblandi"
        RATING_RECOMPUTE = "rating_recompute", "Reyting qayta hisoblandi"
        FLAG_REVIEW = "flag_review", "O‘xshashlik ko‘rildi"
        PROBLEM_DELETE = "problem_delete", "Masala o‘chirildi"
        CONTEST_DELETE = "contest_delete", "Musobaqa o‘chirildi"

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=20, choices=Action.choices)
    contest = models.ForeignKey(Contest, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    subject = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="+")
    note = models.CharField(max_length=300, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-at", "-id"]
