from django.conf import settings
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
        EASY = "easy"
        MEDIUM = "medium"
        HARD = "hard"

    class Status(models.TextChoices):
        PENDING = "pending"    # user-submitted, awaiting staff approval — never public
        APPROVED = "approved"  # staff-created or approved; is_public controls visibility
        REJECTED = "rejected"  # reviewed and declined — never public

    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    statement_md = models.TextField()
    statement_image = models.ImageField(upload_to="statements/", blank=True, null=True)
    difficulty = models.CharField(max_length=10, choices=Difficulty.choices, default=Difficulty.EASY)
    tl_ms = models.IntegerField(default=1000)
    ml_mb = models.IntegerField(default=256)
    points = models.IntegerField(default=100)
    is_public = models.BooleanField(default=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.APPROVED)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="authored_problems")
    tags = models.ManyToManyField(Tag, blank=True)
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
        ordering = ["order", "id"]
