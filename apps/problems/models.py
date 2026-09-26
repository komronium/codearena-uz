from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class Language(models.Model):
    code = models.SlugField(unique=True)          # "python", "cpp"
    name = models.CharField(max_length=50)        # "Python 3"
    docker_image = models.CharField(max_length=100)
    compile_cmd = models.CharField(max_length=200, blank=True)
    run_cmd = models.CharField(max_length=200)
    tl_multiplier = models.FloatField(default=1.0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Problem(models.Model):
    class Difficulty(models.TextChoices):
        BEGINNER = "beginner", "Beginner"
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    class Status(models.TextChoices):
        PENDING = "pending"    # user-submitted, awaiting staff approval — never public
        APPROVED = "approved"  # staff-created or approved; is_public controls visibility
        REJECTED = "rejected"  # reviewed and declined — never public

    class Kind(models.TextChoices):
        CODE = "code", "Dasturlash"  # classic stdin/stdout program, judged via judge.runner + Docker sandbox
        SQL = "sql", "SQL"           # query problem, judged via judge.sql_judge against a SQLDataset

    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    statement_md = models.TextField()
    input_md = models.TextField(blank=True)   # "Kirish ma'lumotlari" section
    output_md = models.TextField(blank=True)  # "Chiqish ma'lumotlari" section
    statement_image = models.ImageField(upload_to="statements/", blank=True, null=True)
    difficulty = models.CharField(max_length=10, choices=Difficulty.choices, default=Difficulty.EASY)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.CODE)
    tl_ms = models.IntegerField(default=1000)
    ml_mb = models.IntegerField(default=256, validators=[MinValueValidator(6)])  # Docker's hard memory-limit floor
    points = models.IntegerField(default=100)
    is_public = models.BooleanField(default=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.APPROVED)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="authored_problems")
    tags = models.ManyToManyField(Tag, blank=True)
    # Shown to a user once they solved it (and to staff and the author).
    editorial_md = models.TextField(blank=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    @property
    def samples(self):
        return self.testcases.filter(is_sample=True)


class TestCase(models.Model):
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name="testcases")
    input = models.TextField()
    expected = models.TextField()
    is_sample = models.BooleanField(default=False)
    order = models.IntegerField(default=0)

    class Meta:
        # "Test 1" must stay the same test after an edit; the runner and the samples use this.
        ordering = ["order", "id"]


class SQLDataset(models.Model):
    """Fixture DB for a Problem.Kind.SQL problem. One dataset per problem — the
    submitted query runs once against it (see judge.sql_judge), so there's no
    per-testcase input/expected the way Kind.CODE problems have."""
    problem = models.OneToOneField(Problem, on_delete=models.CASCADE, related_name="sql_dataset")
    schema_sql = models.TextField(help_text="CREATE TABLE statements, run once per submission.")
    seed_sql = models.TextField(help_text="INSERT statements, run once per submission.")
    expected_result = models.TextField(
        help_text="Correct query's result, one row per line, tab-separated values, no header. "
                   "Row order doesn't matter (compared as a sorted set); column order does.")


class ProblemRating(models.Model):
    """1–5 stars a user gives a problem. Only solvers may rate (enforced in the view)."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="problem_ratings")
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name="ratings")
    stars = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "problem"], name="one_rating_per_user_problem"),
            models.CheckConstraint(condition=models.Q(stars__gte=1, stars__lte=5), name="stars_1_to_5"),
        ]


# A hint's cost is a share of the problem's price, paid only if it was opened before the
# user's first eligible AC (apps.submissions.solves). Total cost is capped at MAX_HINT_PCT.
MAX_HINT_PCT = 90


class ProblemHint(models.Model):
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name="hints")
    order = models.PositiveIntegerField(default=0)
    body_md = models.TextField()
    cost_pct = models.PositiveSmallIntegerField(default=10, validators=[MaxValueValidator(MAX_HINT_PCT)])

    class Meta:
        ordering = ["order", "id"]


class HintUnlock(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    hint = models.ForeignKey(ProblemHint, on_delete=models.CASCADE, related_name="unlocks")
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "hint")


class DailyProblem(models.Model):
    """One problem for everyone per (Tashkent) day; see apps.problems.daily."""
    date = models.DateField(unique=True)
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name="+")

    class Meta:
        ordering = ["-date"]


class DailySolve(models.Model):
    """Derived: a practice AC on the daily problem on its own day. Kept by
    apps.submissions.solves.refresh_solves like solves; worth a small bonus."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    daily = models.ForeignKey(DailyProblem, on_delete=models.CASCADE, related_name="solves")

    class Meta:
        unique_together = ("user", "daily")
