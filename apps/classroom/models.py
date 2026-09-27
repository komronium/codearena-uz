from django.conf import settings
from django.db import models

from apps.accounts.models import Group
from apps.problems.models import Problem
from apps.submissions.models import Submission


class Assignment(models.Model):
    """Homework: a problem set a group's teacher gives with a deadline. Progress is read
    from submissions (apps.classroom.progress), so rejudges flow through by themselves."""
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="assignments")
    title = models.CharField(max_length=200)
    description_md = models.TextField(blank=True)
    start = models.DateTimeField()
    deadline = models.DateTimeField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-deadline", "-id"]

    def __str__(self):
        return self.title


class AssignmentProblem(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name="assignment_problems")
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name="+")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        unique_together = ("assignment", "problem")


class ReviewComment(models.Model):
    """A teacher's note on a student's code (line = None: on the whole submission), or
    the student's reply. `read` is for the student's unread badge."""
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="reviews")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    line = models.PositiveIntegerField(null=True, blank=True)
    body = models.TextField(max_length=2000)
    created = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

    class Meta:
        ordering = ["created", "id"]


class Duel(models.Model):
    """1v1 on one problem neither player tried, each on their own clock: the challenger's
    starts when they open the duel, the opponent's when they join. The faster AC wins
    (apps.classroom.duels). No opponent yet = an open duel: the next player who asks for
    a match at that level gets the same problem."""
    class Status(models.TextChoices):
        PENDING = "pending", "Raqib kutilmoqda"
        ACTIVE = "active", "Davom etmoqda"
        FINISHED = "finished", "Tugagan"
        DECLINED = "declined", "Rad etilgan"
        EXPIRED = "expired", "Muddati o‘tgan"

    challenger = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    opponent = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE,
                                 related_name="+")
    difficulty = models.CharField(max_length=10, choices=Problem.Difficulty.choices)
    problem = models.ForeignKey(Problem, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)  # the challenger's clock
    ends_at = models.DateTimeField(null=True, blank=True)
    opponent_started_at = models.DateTimeField(null=True, blank=True)
    opponent_ends_at = models.DateTimeField(null=True, blank=True)
    winner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="+")
    challenger_delta = models.IntegerField(null=True, blank=True)
    opponent_delta = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-created", "-id"]

    def clock(self, user_id):
        """(start, end) of that player's own time; None before it starts."""
        if user_id == self.challenger_id and self.started_at:
            return self.started_at, self.ends_at
        if user_id is not None and user_id == self.opponent_id and self.opponent_started_at:
            return self.opponent_started_at, self.opponent_ends_at
        return None

    def players(self):
        return (self.challenger_id, self.opponent_id)
