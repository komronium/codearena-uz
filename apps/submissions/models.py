from django.conf import settings
from django.db import models

from apps.contests.models import Contest
from apps.problems.models import Language, Problem, TestCase


class Submission(models.Model):
    class Verdict(models.TextChoices):
        PENDING = "PENDING"
        RUNNING = "RUNNING"
        AC = "AC"
        WA = "WA"
        TLE = "TLE"
        MLE = "MLE"
        OLE = "OLE"
        RE = "RE"
        CE = "CE"

    TERMINAL = {"AC", "WA", "TLE", "MLE", "OLE", "RE", "CE"}

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="submissions")
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name="submissions")
    contest = models.ForeignKey(Contest, null=True, blank=True, on_delete=models.SET_NULL, related_name="submissions")
    language = models.ForeignKey(Language, on_delete=models.PROTECT)
    source = models.TextField()
    verdict = models.CharField(max_length=8, choices=Verdict.choices, default=Verdict.PENDING)
    exec_ms = models.IntegerField(default=0)
    mem_kb = models.IntegerField(default=0)
    passed = models.IntegerField(default=0)
    total = models.IntegerField(default=0)
    compile_log = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "problem"])]
        ordering = ["-id"]

    @property
    def is_terminal(self) -> bool:
        return self.verdict in self.TERMINAL


class TestResult(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="results")
    testcase = models.ForeignKey(TestCase, on_delete=models.CASCADE)
    verdict = models.CharField(max_length=8)
    exec_ms = models.IntegerField(default=0)
    mem_kb = models.IntegerField(default=0)
    stdout_excerpt = models.TextField(blank=True)

    class Meta:
        ordering = ["id"]


class UserProblemSolved(models.Model):
    """Derived: the user's earliest eligible AC for the problem. Maintained by
    apps.submissions.solves.refresh_solves; practice points are computed from these rows."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE)
    first_ac_submission = models.ForeignKey(Submission, on_delete=models.PROTECT)
    solved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "problem")
