from django.conf import settings
from django.db import models

from apps.contests.models import Contest
from apps.submissions.models import Submission


class FocusEvent(models.Model):
    class Kind(models.TextChoices):
        BLUR = "blur"
        FOCUS = "focus"
        PASTE = "paste"
        COPY = "copy"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="focus_events")
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name="focus_events")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["contest", "user"])]


class SimilarityFlag(models.Model):
    submission_a = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="+")
    submission_b = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="+")
    score = models.FloatField()
    reviewed = models.BooleanField(default=False)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-score"]
