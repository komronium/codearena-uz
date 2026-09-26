from django.conf import settings
from django.db import models

from apps.accounts.models import Group
from apps.problems.models import Problem


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
