from django.conf import settings
from django.db import models

from apps.problems.models import Problem, Tag
from django.utils.translation import gettext_lazy as _tl

from apps.translations.mixin import Translatable


# A fixed set: the lucide bundle only carries icon names quoted in the code (frontend/build.mjs).
ICONS = ["book-open", "footprints", "brackets", "route", "database", "graduation-cap", "binary", "network",
         "sigma", "code", "puzzle", "rocket", "target", "trophy", "brain", "layers",
         "terminal", "calculator", "git-branch", "repeat", "rotate-cw", "repeat-2", "hash", "type", "grid-3x3",
         "book-key", "square-function", "gauge", "arrow-down-up", "search", "arrow-left-right", "move-horizontal",
         "coins", "undo-2", "pyramid", "percent", "dices", "git-merge", "list-tree", "ruler", "text-search",
         "shapes", "arrow-down-a-z", "group", "combine", "table"]

# Course slugs live at /learn/<slug>/, next to these pages.
RESERVED_SLUGS = {"lists", "topics", "plans", "save", "search"}


class StudyPlan(Translatable, models.Model):
    """A course: one topic's theory and every open problem carrying any of its tags, easiest
    first. Progress is never stored: it is read from solves against the problems open right
    now (apps.learn.progress)."""

    class Stage(models.TextChoices):  # the path's chapters, in this order
        BASICS = "basics", _tl("Asoslar")
        PYTHON = "python", _tl("Python vositalari")
        ALGORITHMS = "algorithms", _tl("Algoritmlar")
        TECHNIQUES = "techniques", _tl("Texnikalar")
        STRUCTURES = "structures", _tl("Ma’lumot tuzilmalari")
        MATH = "math", _tl("Matematika")
        DP = "dp", _tl("Dinamik dasturlash")
        GRAPHS = "graphs", _tl("Graflar")
        ADVANCED = "advanced", _tl("Ilg‘or")
        SQL = "sql", "SQL"

    TRANSLATABLE = ("title", "summary", "description_md", "theory_md")
    SHORT = ("title", "summary")
    source_lang = models.CharField(max_length=2, default="uz", choices=[("uz", "O‘zbekcha"), ("en", "English")])

    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=120)
    summary = models.CharField(max_length=200, blank=True)  # one line on the card
    description_md = models.TextField(blank=True)
    theory_md = models.TextField(blank=True)
    stage = models.CharField(max_length=12, choices=Stage.choices, default=Stage.BASICS)
    tags = models.ManyToManyField(Tag, blank=True, related_name="courses")  # its problems: any of these
    level = models.CharField(max_length=10, choices=Problem.Difficulty.choices, default=Problem.Difficulty.BEGINNER)
    icon = models.CharField(max_length=40, default="book-open", choices=[(i, i) for i in ICONS])
    order = models.PositiveIntegerField(default=0)
    in_quest = models.BooleanField(default=False)  # unused since courses follow tags; dropped next
    is_public = models.BooleanField(default=False)
    updated = models.DateTimeField(auto_now=True)  # the sitemap's lastmod

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


class PlanSection(Translatable, models.Model):
    TRANSLATABLE = ("title", "intro_md")
    SHORT = ("title",)

    plan = models.ForeignKey(StudyPlan, on_delete=models.CASCADE, related_name="sections")
    title = models.CharField(max_length=120)
    intro_md = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    @property
    def source_lang(self):
        return self.plan.source_lang


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


class PlanDone(models.Model):
    """The first time a user finished a course with problems. A course is finished against the problems open that day;
    this row keeps it finished when problems are later added, hidden or retagged (apps.learn.progress.record_done)."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="plan_dones")
    plan = models.ForeignKey(StudyPlan, on_delete=models.CASCADE, related_name="dones")
    done_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "plan")


class PlanRead(models.Model):
    """"Tushundim": a user marked a course's theory as read. A course without problems is finished by it."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="plan_reads")
    plan = models.ForeignKey(StudyPlan, on_delete=models.CASCADE, related_name="reads")
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "plan")
