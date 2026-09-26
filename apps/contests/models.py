from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.accounts.models import Group
from apps.problems.models import Problem


_UZ_MONTHS_SHORT = "Yan Fev Mar Apr May Iyn Iyl Avg Sen Okt Noy Dek".split()


class Contest(models.Model):
    class Type(models.TextChoices):
        # ponytail: single format kept as a field so old rows/migrations stay valid;
        # ICPC was dropped — equal points per problem gives the same ranking.
        SCORE = "score", "Ball"

    title = models.CharField(max_length=200)
    description_md = models.TextField(blank=True)
    start = models.DateTimeField()
    end = models.DateTimeField()
    type = models.CharField(max_length=10, choices=Type.choices, default=Type.SCORE)
    is_rated = models.BooleanField(default=False)
    allowed_ip_prefix = models.CharField(max_length=50, blank=True)
    require_group = models.ForeignKey(Group, null=True, blank=True, on_delete=models.SET_NULL)
    rating_applied = models.BooleanField(default=False)
    # Set by staff publishing the ended contest; from then on participants' contest ACs
    # count as practice solves (apps.submissions.solves).
    published_at = models.DateTimeField(null=True, blank=True)
    problems = models.ManyToManyField(Problem, through="ContestProblem", related_name="contests")

    def __str__(self):
        return self.title

    @property
    def is_running(self) -> bool:
        now = timezone.now()
        return self.start <= now < self.end

    @property
    def duration_label(self) -> str:
        minutes = int((self.end - self.start).total_seconds() // 60)
        h, m = divmod(minutes, 60)
        d, h = divmod(h, 24)
        parts = (f"{d} kun" if d else "", f"{h} soat" if h else "", f"{m} daq" if m else "")
        return " ".join(p for p in parts if p) or "0 daq"

    @property
    def start_month_short(self) -> str:
        return _UZ_MONTHS_SHORT[timezone.localtime(self.start).month - 1]

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
    # Set by staff for cheating: can't submit, ranked last (so rating drops), shown struck out.
    disqualified = models.BooleanField(default=False)
    disqualified_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = ("user", "contest")


class Clarification(models.Model):
    """Contest Q&A. An unanswered question is visible only to its asker and
    staff; once answered it's visible to every participant (standard CP
    clarification-board behavior — answers are shared, questions in flight
    aren't)."""
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name="clarifications")
    problem = models.ForeignKey(ContestProblem, null=True, blank=True, on_delete=models.CASCADE,
                                related_name="clarifications")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="clarifications")
    question = models.TextField()
    answer = models.TextField(blank=True)
    answered_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="+")
    created = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created"]

    @property
    def is_answered(self) -> bool:
        return bool(self.answered_at)
