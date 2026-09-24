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
