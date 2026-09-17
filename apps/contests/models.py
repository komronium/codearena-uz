from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.accounts.models import Group
from apps.problems.models import Problem


class Contest(models.Model):
    class Type(models.TextChoices):
        ICPC = "icpc"
        SCORE = "score"

    title = models.CharField(max_length=200)
    description_md = models.TextField(blank=True)
    start = models.DateTimeField()
    end = models.DateTimeField()
    type = models.CharField(max_length=10, choices=Type.choices, default=Type.ICPC)
    is_rated = models.BooleanField(default=False)
    allowed_ip_prefix = models.CharField(max_length=50, blank=True)
    require_group = models.ForeignKey(Group, null=True, blank=True, on_delete=models.SET_NULL)
    rating_applied = models.BooleanField(default=False)
    problems = models.ManyToManyField(Problem, through="ContestProblem", related_name="contests")

    def __str__(self):
        return self.title

    @property
    def is_running(self) -> bool:
        now = timezone.now()
        return self.start <= now < self.end

    @property
    def has_ended(self) -> bool:
        return timezone.now() >= self.end

    @property
    def has_started(self) -> bool:
        return timezone.now() >= self.start


class ContestProblem(models.Model):
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name="contest_problems")
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE)
    label = models.CharField(max_length=2)
    order = models.IntegerField(default=0)
    points = models.IntegerField(default=100)

    class Meta:
        ordering = ["order"]
        unique_together = ("contest", "label")

    def __str__(self):
        return f"{self.contest} / {self.label}"


class Participation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="participations")
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name="participations")
    score = models.IntegerField(default=0)
    penalty = models.IntegerField(default=0)
    rank = models.IntegerField(null=True, blank=True)
    rating_before = models.IntegerField(null=True, blank=True)
    rating_after = models.IntegerField(null=True, blank=True)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "contest")
