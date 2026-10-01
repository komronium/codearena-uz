from django.conf import settings
from django.db import models

from apps.problems.models import Problem


# A fixed set: the lucide bundle only carries icon names quoted in the code (frontend/build.mjs).
ICONS = ["book-open", "footprints", "brackets", "route", "database", "graduation-cap", "binary", "network",
         "sigma", "code", "puzzle", "rocket", "target", "trophy", "brain", "layers"]


class StudyPlan(models.Model):
    """An ordered path through existing problems, in sections. Progress is never stored:
    it is read from solves against the problems open right now (apps.learn.progress)."""
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=120)
    summary = models.CharField(max_length=200, blank=True)  # one line on the card
    description_md = models.TextField(blank=True)
    level = models.CharField(max_length=10, choices=Problem.Difficulty.choices, default=Problem.Difficulty.BEGINNER)
    icon = models.CharField(max_length=40, default="book-open", choices=[(i, i) for i in ICONS])
    order = models.PositiveIntegerField(default=0)
    in_quest = models.BooleanField(default=False)  # a stage of the "Yo‘l"
    is_public = models.BooleanField(default=False)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


class PlanSection(models.Model):
    plan = models.ForeignKey(StudyPlan, on_delete=models.CASCADE, related_name="sections")
    title = models.CharField(max_length=120)
    intro_md = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]


class PlanItem(models.Model):
    section = models.ForeignKey(PlanSection, on_delete=models.CASCADE, related_name="items")
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name="+")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]


MAX_LISTS = 50


class ProblemList(models.Model):
    """A user's own collection of problems ("Ro‘yxatlarim"); private unless shared."""
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="problem_lists")
    name = models.CharField(max_length=80)
    is_public = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created", "-id"]

    def __str__(self):
        return self.name


class ProblemListItem(models.Model):
    list = models.ForeignKey(ProblemList, on_delete=models.CASCADE, related_name="items")
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name="+")
    added = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-added", "-id"]
        unique_together = ("list", "problem")
