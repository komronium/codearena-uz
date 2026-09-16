# CodeArena MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a working single-language (Python) competitive-programming MVP: users register, browse problems, submit Python solutions, and see a judged verdict — matching spec Build Phase 1.

**Architecture:** Django project with three apps (`accounts`, `problems`, `submissions`) plus a plain-Python `judge` package (not a Django app) that compiles/runs submitted code inside a locked-down Docker container and reports a verdict back onto the `Submission` row. An RQ worker (Redis-backed) executes `judge.runner.run_submission` asynchronously; the web process never runs untrusted code itself. The submission detail page polls via HTMX until the verdict is terminal.

**Tech Stack:** Django 6.1, PostgreSQL (dev/test defaults to SQLite when unconfigured), Redis + RQ, HTMX (CDN), Tailwind (CDN), Docker (judge sandbox), pytest not used — Django's built-in `TestCase`/test runner, matching this user's existing Django projects (see `edu-track`).

**Spec:** `docs/superpowers/specs/2026-09-15-codearena-design.md`

## Global Constraints

- Problems are stdin/stdout only; a submission is a full program (spec §"Problem format").
- Judge isolation per test run: `docker run --rm --network none --memory {ml}m --memory-swap {ml}m --cpus 1 --pids-limit 64 --read-only --tmpfs /tmp -i --user nobody {image} {run_cmd}`, wrapped in `timeout`. Effective TL = `tl_ms * language.tl_multiplier` (spec §2).
- Output comparison: rstrip each line, ignore trailing blank lines (spec §2 `compare.py`).
- Only the judge-worker process may touch `docker.sock`; the Django web process never executes submitted code directly (spec §2 "Security").
- First AC per (user, problem) awards `problem.points` to `user.practice_points` exactly once, via a `UserProblemSolved` row (spec §1 `UserProblemSolved`, §2 step 5).
- Verdict enum is exactly: `PENDING RUNNING AC WA TLE MLE RE CE` (spec §1).
- `statement_image` is a URL, not an uploaded file — no MEDIA/file-storage subsystem in this phase (deviation from spec's literal field description, called out here because file uploads are out of scope for the MVP; revisit only if a real authoring need appears).
- `Submission.contest` (nullable FK) is deferred to the contests plan (Phase 3) — it does not exist yet in this phase's schema, since the `Contest` model doesn't exist yet. Do not add a stub field for it now.
- This plan is Python-only. `Language` rows for C++/Java/Node and their Docker images are Phase 2's job — but the `Language` model itself must already support them without schema changes (spec §1 `Language`).
- `base.html` loads Tailwind and htmx from CDN with no Subresource Integrity hash: Tailwind's play-CDN script is dynamically generated per-request and cannot be pinned by hash, and fabricating an unverified htmx hash would silently break script loading if wrong. Acceptable for this MVP's trusted-author, no-payment-data surface; before a real production launch, self-host both (Tailwind CLI build output, htmx via a pinned npm/vendored file with a verified hash).

---

## File Structure

```
codearena/
  manage.py
  codearena/                    # Django settings package
    __init__.py
    settings.py
    urls.py
    wsgi.py
    asgi.py
  accounts/
    __init__.py
    models.py                   # User(AbstractUser)
    admin.py
    apps.py
    migrations/
  problems/
    __init__.py
    models.py                   # Tag, Language, Problem, TestCase
    admin.py
    apps.py
    views.py                    # list, detail (GET shows form, POST submits)
    urls.py
    templates/problems/list.html
    templates/problems/detail.html
    migrations/
  submissions/
    __init__.py
    models.py                   # Submission, TestResult, UserProblemSolved
    admin.py
    apps.py
    views.py                    # detail (polling partial), list ("mine")
    urls.py
    templates/submissions/detail.html
    templates/submissions/_verdict.html   # HTMX polling fragment
    templates/submissions/list.html
    migrations/
  judge/
    __init__.py
    compare.py                  # outputs_match()
    sandbox.py                  # compile(), run_test()
    runner.py                   # run_submission()
    jobs.py                     # enqueue_submission(), get_queue()
    images/
      python/Dockerfile
  templates/
    base.html
  requirements.txt
  docker-compose.yml
  Dockerfile
  .env.example
  README.md
```

---

## Task 1: Project skeleton + custom User model + health check

**Files:**
- Create: `manage.py`, `codearena/__init__.py`, `codearena/settings.py`, `codearena/urls.py`, `codearena/wsgi.py`, `codearena/asgi.py`
- Create: `accounts/__init__.py`, `accounts/apps.py`, `accounts/models.py`, `accounts/admin.py`
- Create: `accounts/migrations/__init__.py`, `accounts/migrations/0001_initial.py` (generated)
- Create: `templates/base.html`
- Create: `requirements.txt`, `.env.example`, `.gitignore`
- Test: `accounts/tests.py`

**Interfaces:**
- Produces: `accounts.models.User` with fields `rating: int` (default 1500), `practice_points: int` (default 0), `role: str` in `{"student", "teacher", "admin"}` (default `"student"`). `settings.AUTH_USER_MODEL = "accounts.User"`.
- Produces: `GET /health/` → `200` JSON `{"status": "ok"}`.

- [ ] **Step 1: Create requirements.txt and .gitignore**

`requirements.txt`:
```
Django==6.1.1
psycopg[binary]==3.2.3
redis==5.2.1
rq==2.1.0
python-dotenv==1.2.3
```

`.gitignore`:
```
__pycache__/
*.pyc
.env
db.sqlite3
staticfiles/
```

- [ ] **Step 2: Install dependencies and start the project**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
django-admin startproject codearena .
python manage.py startapp accounts
```

- [ ] **Step 3: Write settings.py**

Replace generated `codearena/settings.py` contents with:

```python
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-change-me-in-.env",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "problems",
    "submissions",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "codearena.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "codearena.wsgi.application"

# Postgres when POSTGRES_HOST is set (docker-compose / production), otherwise
# SQLite so unit tests and local dev need no services running.
if os.environ.get("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "codearena"),
            "USER": os.environ.get("POSTGRES_USER", "codearena"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ.get("POSTGRES_HOST"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
```

- [ ] **Step 4: Write accounts/models.py**

```python
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        TEACHER = "teacher", "Teacher"
        ADMIN = "admin", "Admin"

    rating = models.IntegerField(default=1500)
    practice_points = models.IntegerField(default=0)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)

    def __str__(self):
        return self.username
```

- [ ] **Step 5: Write accounts/admin.py**

```python
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CodeArenaUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("CodeArena", {"fields": ("rating", "practice_points", "role")}),
    )
    list_display = ("username", "email", "rating", "practice_points", "role", "is_staff")
```

- [ ] **Step 6: Write codearena/urls.py**

```python
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("problems/", include("problems.urls")),
    path("submissions/", include("submissions.urls")),
]
```

- [ ] **Step 7: Write templates/base.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{% block title %}CodeArena{% endblock %}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
</head>
<body class="bg-slate-50 text-slate-900">
    <nav class="p-4 border-b bg-white">
        <a href="/problems/" class="font-bold">CodeArena</a>
    </nav>
    <main class="p-4">
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

- [ ] **Step 8: Write the failing test**

`accounts/tests.py`:
```python
from django.test import TestCase


class HealthCheckTests(TestCase):
    def test_health_returns_ok(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


class UserModelTests(TestCase):
    def test_new_user_has_default_rating_and_points(self):
        from accounts.models import User

        user = User.objects.create_user(username="alice", password="pw12345")
        self.assertEqual(user.rating, 1500)
        self.assertEqual(user.practice_points, 0)
        self.assertEqual(user.role, User.Role.STUDENT)
```

- [ ] **Step 9: Run test to verify it fails**

Run: `python manage.py test accounts -v 2`
Expected: FAIL — no migrations exist yet / app not fully wired (error, not a clean assertion failure).

- [ ] **Step 10: Generate migrations and re-run**

```bash
python manage.py makemigrations accounts
python manage.py test accounts -v 2
```

Expected: PASS (2 tests).

- [ ] **Step 11: Write .env.example**

```
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
POSTGRES_DB=codearena
POSTGRES_USER=codearena
POSTGRES_PASSWORD=change-me
POSTGRES_HOST=
POSTGRES_PORT=5432
REDIS_URL=redis://localhost:6379/0
```

- [ ] **Step 12: Commit**

```bash
git add manage.py codearena accounts templates requirements.txt .env.example .gitignore
git commit -m "feat: project skeleton, custom User model, health check"
```

---

## Task 2: problems app — models

**Files:**
- Create: `problems/__init__.py`, `problems/apps.py`, `problems/models.py`, `problems/admin.py`
- Create: `problems/migrations/__init__.py`, `problems/migrations/0001_initial.py` (generated)
- Test: `problems/tests.py`

**Interfaces:**
- Consumes: `accounts.models.User` (Task 1) as `Problem.author`.
- Produces: `problems.models.Tag(name, slug)`; `problems.models.Language(code, name, docker_image, compile_cmd, run_cmd, tl_multiplier, is_active)`; `problems.models.Problem(slug, title, statement_md, statement_image, difficulty, tl_ms, ml_mb, points, is_public, author, tags, created)` with `Problem.Difficulty` choices `EASY/MEDIUM/HARD`; `problems.models.TestCase(problem, input, expected, is_sample, order)`.

- [ ] **Step 1: Create the app**

```bash
python manage.py startapp problems
```

- [ ] **Step 2: Write problems/models.py**

```python
from django.conf import settings
from django.db import models


class Tag(models.Model):
    name = models.CharField(max_length=40, unique=True)
    slug = models.SlugField(max_length=40, unique=True)

    def __str__(self):
        return self.name


class Language(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=40)
    docker_image = models.CharField(max_length=100)
    compile_cmd = models.CharField(max_length=200, blank=True)
    run_cmd = models.CharField(max_length=200)
    tl_multiplier = models.FloatField(default=1.0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Problem(models.Model):
    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    slug = models.SlugField(max_length=80, unique=True)
    title = models.CharField(max_length=200)
    statement_md = models.TextField()
    statement_image = models.URLField(blank=True)
    difficulty = models.CharField(max_length=10, choices=Difficulty.choices, default=Difficulty.EASY)
    tl_ms = models.PositiveIntegerField(default=1000)
    ml_mb = models.PositiveIntegerField(default=256)
    points = models.PositiveIntegerField(default=100)
    is_public = models.BooleanField(default=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="problems")
    tags = models.ManyToManyField(Tag, blank=True, related_name="problems")
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class TestCase(models.Model):
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name="testcases")
    input = models.TextField()
    expected = models.TextField()
    is_sample = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.problem.slug} #{self.order}"
```

- [ ] **Step 3: Write problems/admin.py**

```python
from django.contrib import admin

from .models import Language, Problem, Tag, TestCase


class TestCaseInline(admin.TabularInline):
    model = TestCase
    extra = 1


@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "difficulty", "points", "is_public", "author")
    list_filter = ("difficulty", "is_public", "tags")
    inlines = [TestCaseInline]
    prepopulated_fields = {"slug": ("title",)}


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "docker_image", "is_active")


admin.site.register(Tag)
```

- [ ] **Step 4: Write the failing test**

`problems/tests.py`:
```python
from django.test import TestCase as DjangoTestCase

from accounts.models import User
from problems.models import Language, Problem, TestCase


class ProblemModelTests(DjangoTestCase):
    def setUp(self):
        self.author = User.objects.create_user(username="teacher1", password="pw12345")

    def test_problem_defaults(self):
        problem = Problem.objects.create(
            slug="a-plus-b",
            title="A+B",
            statement_md="Read two integers, print their sum.",
            author=self.author,
        )
        self.assertEqual(problem.difficulty, Problem.Difficulty.EASY)
        self.assertEqual(problem.tl_ms, 1000)
        self.assertEqual(problem.ml_mb, 256)
        self.assertTrue(problem.is_public)

    def test_testcases_ordered(self):
        problem = Problem.objects.create(
            slug="ordering", title="Ordering", statement_md="x", author=self.author,
        )
        TestCase.objects.create(problem=problem, input="2", expected="2", order=2)
        TestCase.objects.create(problem=problem, input="1", expected="1", order=1)
        orders = list(problem.testcases.values_list("order", flat=True))
        self.assertEqual(orders, [1, 2])

    def test_language_str(self):
        lang = Language.objects.create(
            code="python3", name="Python 3", docker_image="codearena-judge-python",
            run_cmd="python3 main.py",
        )
        self.assertEqual(str(lang), "Python 3")
```

- [ ] **Step 5: Run test to verify it fails**

Run: `python manage.py test problems -v 2`
Expected: FAIL — `problems` not in `INSTALLED_APPS` / no migrations yet.

- [ ] **Step 6: Add app, generate migration, re-run**

Add `"problems"` is already listed in `INSTALLED_APPS` from Task 1's settings.py (it was added in Step 3 of Task 1). Generate and run:

```bash
python manage.py makemigrations problems
python manage.py test problems -v 2
```

Expected: PASS (3 tests).

- [ ] **Step 7: Commit**

```bash
git add problems
git commit -m "feat: problems app models (Tag, Language, Problem, TestCase)"
```

---

## Task 3: problems app — list and detail views

**Files:**
- Create: `problems/urls.py`, `problems/views.py`
- Create: `templates/problems/list.html`, `templates/problems/detail.html`
- Modify: `problems/tests.py` (append view tests)

**Interfaces:**
- Consumes: `problems.models.Problem`, `TestCase` (Task 2).
- Produces: `GET /problems/` (name `problem_list`) → renders public problems. `GET /problems/<slug>/` (name `problem_detail`) → renders statement + sample test cases; 404 if `is_public=False`.

- [ ] **Step 1: Write the failing tests**

Append to `problems/tests.py`:
```python
class ProblemViewTests(DjangoTestCase):
    def setUp(self):
        self.author = User.objects.create_user(username="teacher2", password="pw12345")
        self.problem = Problem.objects.create(
            slug="a-plus-b", title="A+B", statement_md="Sum two integers.",
            author=self.author, is_public=True,
        )
        TestCase.objects.create(problem=self.problem, input="1 2\n", expected="3\n", is_sample=True, order=0)
        self.hidden = Problem.objects.create(
            slug="hidden", title="Hidden", statement_md="secret",
            author=self.author, is_public=False,
        )

    def test_list_shows_public_problems_only(self):
        response = self.client.get("/problems/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A+B")
        self.assertNotContains(response, "Hidden")

    def test_detail_shows_statement_and_sample(self):
        response = self.client.get("/problems/a-plus-b/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sum two integers.")
        self.assertContains(response, "1 2")

    def test_detail_404_for_non_public(self):
        response = self.client.get("/problems/hidden/")
        self.assertEqual(response.status_code, 404)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test problems.ProblemViewTests -v 2`
Expected: FAIL — no URLconf `problems.urls`.

- [ ] **Step 3: Write problems/views.py**

```python
from django.shortcuts import get_object_or_404, render

from .models import Problem


def problem_list(request):
    problems = Problem.objects.filter(is_public=True).order_by("id")
    return render(request, "problems/list.html", {"problems": problems})


def problem_detail(request, slug):
    problem = get_object_or_404(Problem, slug=slug, is_public=True)
    samples = problem.testcases.filter(is_sample=True)
    return render(request, "problems/detail.html", {"problem": problem, "samples": samples})
```

- [ ] **Step 4: Write problems/urls.py**

```python
from django.urls import path

from . import views

urlpatterns = [
    path("", views.problem_list, name="problem_list"),
    path("<slug:slug>/", views.problem_detail, name="problem_detail"),
]
```

- [ ] **Step 5: Write templates/problems/list.html**

```html
{% extends "base.html" %}
{% block content %}
<h1 class="text-xl font-bold mb-4">Problems</h1>
<ul class="space-y-2">
    {% for problem in problems %}
    <li>
        <a href="{% url 'problem_detail' problem.slug %}" class="text-blue-600 hover:underline">
            {{ problem.title }}
        </a>
        <span class="text-sm text-slate-500">({{ problem.get_difficulty_display }}, {{ problem.points }} pts)</span>
    </li>
    {% empty %}
    <li>No problems yet.</li>
    {% endfor %}
</ul>
{% endblock %}
```

- [ ] **Step 6: Write templates/problems/detail.html**

```html
{% extends "base.html" %}
{% block content %}
<h1 class="text-xl font-bold">{{ problem.title }}</h1>
<p class="text-sm text-slate-500">{{ problem.get_difficulty_display }} · {{ problem.points }} pts · TL {{ problem.tl_ms }}ms · ML {{ problem.ml_mb }}MB</p>
<div class="prose mt-4">{{ problem.statement_md|linebreaks }}</div>

<h2 class="font-semibold mt-6">Sample tests</h2>
{% for sample in samples %}
<div class="grid grid-cols-2 gap-2 mt-2">
    <pre class="bg-slate-100 p-2 rounded">{{ sample.input }}</pre>
    <pre class="bg-slate-100 p-2 rounded">{{ sample.expected }}</pre>
</div>
{% endfor %}

<form method="post" action="{% url 'submit_solution' problem.slug %}" class="mt-6">
    {% csrf_token %}
    <textarea name="source" rows="12" class="w-full font-mono border rounded p-2" placeholder="Your Python 3 solution"></textarea>
    <button type="submit" class="mt-2 bg-blue-600 text-white px-4 py-2 rounded">Submit</button>
</form>
{% endblock %}
```

Note: `{% url 'submit_solution' %}` is defined in Task 8; the template references it now so Task 8 does not need to touch this file again. Until Task 8 lands, this template will raise `NoReverseMatch` if rendered outside the tests above (which don't render the submit form's URL because Django lazily resolves `{% url %}` only when the tag executes — it still executes at render time). To keep Task 3's tests green before Task 8 exists, use a plain placeholder path instead:

Replace the form's `action` with a literal path so no reverse lookup is needed yet:
```html
<form method="post" action="/submissions/submit/{{ problem.slug }}/" class="mt-6">
```

- [ ] **Step 7: Run test to verify it passes**

Run: `python manage.py test problems -v 2`
Expected: PASS (6 tests total for `problems`).

- [ ] **Step 8: Commit**

```bash
git add problems templates/problems
git commit -m "feat: problem list and detail views"
```

---

## Task 4: submissions app — models

**Files:**
- Create: `submissions/__init__.py`, `submissions/apps.py`, `submissions/models.py`, `submissions/admin.py`
- Create: `submissions/migrations/__init__.py`, `submissions/migrations/0001_initial.py` (generated)
- Test: `submissions/tests.py`

**Interfaces:**
- Consumes: `accounts.models.User`, `problems.models.Problem`, `problems.models.Language`, `problems.models.TestCase` (Tasks 1-2).
- Produces: `submissions.models.Submission(user, problem, language, source, verdict, exec_ms, mem_kb, passed, total, created)` with `Submission.Verdict` choices exactly `PENDING RUNNING AC WA TLE MLE RE CE`; `submissions.models.TestResult(submission, testcase, verdict, exec_ms, stdout_excerpt)`; `submissions.models.UserProblemSolved(user, problem, first_ac_submission)` with `unique_together = ("user", "problem")`.

- [ ] **Step 1: Create the app**

```bash
python manage.py startapp submissions
```

- [ ] **Step 2: Write submissions/models.py**

```python
from django.conf import settings
from django.db import models

from problems.models import Language, Problem, TestCase


class Submission(models.Model):
    class Verdict(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RUNNING = "RUNNING", "Running"
        AC = "AC", "Accepted"
        WA = "WA", "Wrong Answer"
        TLE = "TLE", "Time Limit Exceeded"
        MLE = "MLE", "Memory Limit Exceeded"
        RE = "RE", "Runtime Error"
        CE = "CE", "Compile Error"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="submissions")
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name="submissions")
    language = models.ForeignKey(Language, on_delete=models.PROTECT)
    source = models.TextField()
    verdict = models.CharField(max_length=10, choices=Verdict.choices, default=Verdict.PENDING)
    exec_ms = models.PositiveIntegerField(null=True, blank=True)
    mem_kb = models.PositiveIntegerField(null=True, blank=True)
    passed = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"Submission #{self.pk} ({self.verdict})"


class TestResult(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="results")
    testcase = models.ForeignKey(TestCase, on_delete=models.CASCADE)
    verdict = models.CharField(max_length=10, choices=Submission.Verdict.choices)
    exec_ms = models.PositiveIntegerField(null=True, blank=True)
    stdout_excerpt = models.TextField(blank=True)


class UserProblemSolved(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE)
    first_ac_submission = models.ForeignKey(Submission, on_delete=models.PROTECT)
    solved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "problem")
```

- [ ] **Step 3: Write submissions/admin.py**

```python
from django.contrib import admin

from .models import Submission, TestResult, UserProblemSolved


class TestResultInline(admin.TabularInline):
    model = TestResult
    extra = 0


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "problem", "language", "verdict", "passed", "total", "created")
    list_filter = ("verdict", "language")
    inlines = [TestResultInline]


admin.site.register(UserProblemSolved)
```

- [ ] **Step 4: Write the failing test**

`submissions/tests.py`:
```python
from django.test import TestCase

from accounts.models import User
from problems.models import Language, Problem
from submissions.models import Submission, UserProblemSolved


class SubmissionModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="bob", password="pw12345")
        self.problem = Problem.objects.create(
            slug="a-plus-b", title="A+B", statement_md="x", author=self.user,
        )
        self.language = Language.objects.create(
            code="python3", name="Python 3", docker_image="codearena-judge-python",
            run_cmd="python3 main.py",
        )

    def test_submission_defaults_to_pending(self):
        submission = Submission.objects.create(
            user=self.user, problem=self.problem, language=self.language, source="print(1)",
        )
        self.assertEqual(submission.verdict, Submission.Verdict.PENDING)
        self.assertEqual(submission.passed, 0)

    def test_user_problem_solved_unique_per_pair(self):
        submission = Submission.objects.create(
            user=self.user, problem=self.problem, language=self.language,
            source="print(1)", verdict=Submission.Verdict.AC,
        )
        UserProblemSolved.objects.create(
            user=self.user, problem=self.problem, first_ac_submission=submission,
        )
        with self.assertRaises(Exception):
            UserProblemSolved.objects.create(
                user=self.user, problem=self.problem, first_ac_submission=submission,
            )
```

- [ ] **Step 5: Run test to verify it fails**

Run: `python manage.py test submissions -v 2`
Expected: FAIL — no migrations for `submissions` yet.

- [ ] **Step 6: Generate migration and re-run**

`submissions` is already in `INSTALLED_APPS` (added in Task 1's settings.py).

```bash
python manage.py makemigrations submissions
python manage.py test submissions -v 2
```

Expected: PASS (2 tests).

- [ ] **Step 7: Commit**

```bash
git add submissions
git commit -m "feat: submissions app models (Submission, TestResult, UserProblemSolved)"
```

---

## Task 5: judge.compare — output comparison

**Files:**
- Create: `judge/__init__.py`, `judge/compare.py`
- Test: `judge/tests_compare.py`

**Interfaces:**
- Produces: `judge.compare.outputs_match(expected: str, actual: str) -> bool`.

- [ ] **Step 1: Write the failing test**

`judge/tests_compare.py`:
```python
from django.test import SimpleTestCase

from judge.compare import outputs_match


class OutputsMatchTests(SimpleTestCase):
    def test_exact_match(self):
        self.assertTrue(outputs_match("3\n", "3\n"))

    def test_trailing_whitespace_ignored(self):
        self.assertTrue(outputs_match("3\n", "3 \n"))

    def test_trailing_blank_lines_ignored(self):
        self.assertTrue(outputs_match("3\n", "3\n\n\n"))

    def test_missing_trailing_newline_ok(self):
        self.assertTrue(outputs_match("3\n", "3"))

    def test_wrong_value(self):
        self.assertFalse(outputs_match("3\n", "4\n"))

    def test_internal_whitespace_differs_still_mismatch(self):
        self.assertFalse(outputs_match("1 2\n", "12\n"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test judge.tests_compare -v 2`
Expected: FAIL — `judge.compare` has no `outputs_match`.

- [ ] **Step 3: Write judge/compare.py**

```python
def _normalize(text: str) -> list[str]:
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def outputs_match(expected: str, actual: str) -> bool:
    """Compare judge output ignoring trailing whitespace per line and trailing blank lines."""
    return _normalize(expected) == _normalize(actual)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test judge.tests_compare -v 2`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add judge
git commit -m "feat: judge output comparison"
```

---

## Task 6: judge.sandbox — Docker compile/run + Python image

**Files:**
- Create: `judge/sandbox.py`
- Create: `judge/images/python/Dockerfile`
- Test: `judge/tests_sandbox.py`

**Interfaces:**
- Consumes: `problems.models.Language` (Task 2) — reads `.docker_image`, `.compile_cmd`, `.run_cmd`, `.tl_multiplier`.
- Produces: `judge.sandbox.CompileResult` (namedtuple: `ok: bool`, `log: str`); `judge.sandbox.RunResult` (namedtuple: `stdout: str`, `exit_code: int`, `timed_out: bool`, `exec_ms: int`); `judge.sandbox.compile(language, src_dir: Path) -> CompileResult`; `judge.sandbox.run_test(language, src_dir: Path, input_text: str, tl_ms: int, ml_mb: int) -> RunResult`.

These tests require Docker and the built `codearena-judge-python` image, so they only run when `JUDGE_TESTS=1` is set (per spec §6).

- [ ] **Step 1: Write judge/images/python/Dockerfile**

```dockerfile
FROM python:3.12-slim
WORKDIR /work
```

Build it:
```bash
docker build -t codearena-judge-python judge/images/python
```

- [ ] **Step 2: Write the failing test**

`judge/tests_sandbox.py`:
```python
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from judge.sandbox import compile as judge_compile
from judge.sandbox import run_test


class FakeLanguage:
    docker_image = "codearena-judge-python"
    compile_cmd = ""
    run_cmd = "python3 main.py"
    tl_multiplier = 3.0


@unittest.skipUnless(os.environ.get("JUDGE_TESTS") == "1", "requires Docker; set JUDGE_TESTS=1")
class SandboxTests(SimpleTestCase):
    def test_run_test_echoes_input(self):
        with TemporaryDirectory() as tmp:
            src_dir = Path(tmp)
            (src_dir / "main.py").write_text("print(input())\n")
            result = run_test(FakeLanguage(), src_dir, "hello\n", tl_ms=1000, ml_mb=256)
            self.assertEqual(result.exit_code, 0)
            self.assertFalse(result.timed_out)
            self.assertEqual(result.stdout.strip(), "hello")

    def test_run_test_times_out(self):
        with TemporaryDirectory() as tmp:
            src_dir = Path(tmp)
            (src_dir / "main.py").write_text("while True: pass\n")
            result = run_test(FakeLanguage(), src_dir, "", tl_ms=200, ml_mb=256)
            self.assertTrue(result.timed_out)

    def test_run_test_nonzero_exit_on_exception(self):
        with TemporaryDirectory() as tmp:
            src_dir = Path(tmp)
            (src_dir / "main.py").write_text("raise ValueError('boom')\n")
            result = run_test(FakeLanguage(), src_dir, "", tl_ms=1000, ml_mb=256)
            self.assertNotEqual(result.exit_code, 0)
            self.assertFalse(result.timed_out)

    def test_compile_noop_when_no_compile_cmd(self):
        with TemporaryDirectory() as tmp:
            src_dir = Path(tmp)
            (src_dir / "main.py").write_text("print(1)\n")
            result = judge_compile(FakeLanguage(), src_dir)
            self.assertTrue(result.ok)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `JUDGE_TESTS=1 python manage.py test judge.tests_sandbox -v 2`
Expected: FAIL — `judge.sandbox` module doesn't exist yet.

- [ ] **Step 4: Write judge/sandbox.py**

```python
import subprocess
import time
from pathlib import Path
from typing import NamedTuple


class CompileResult(NamedTuple):
    ok: bool
    log: str


class RunResult(NamedTuple):
    stdout: str
    exit_code: int
    timed_out: bool
    exec_ms: int


def _docker_run_args(language, src_dir: Path, ml_mb: int) -> list[str]:
    return [
        "docker", "run", "--rm",
        "--network", "none",
        "--memory", f"{ml_mb}m",
        "--memory-swap", f"{ml_mb}m",
        "--cpus", "1",
        "--pids-limit", "64",
        "--read-only",
        "--tmpfs", "/tmp",
        "--user", "nobody",
        "-v", f"{src_dir}:/work:ro" if False else f"{src_dir}:/work",
        "-w", "/work",
        "-i",
        language.docker_image,
    ]


def compile(language, src_dir: Path) -> CompileResult:
    """Compile the submission if the language needs it. No-op (ok=True) otherwise."""
    if not language.compile_cmd:
        return CompileResult(ok=True, log="")

    args = _docker_run_args(language, src_dir, ml_mb=512) + ["sh", "-c", language.compile_cmd]
    proc = subprocess.run(args, capture_output=True, text=True, timeout=60)
    return CompileResult(ok=proc.returncode == 0, log=proc.stderr)


def run_test(language, src_dir: Path, input_text: str, tl_ms: int, ml_mb: int) -> RunResult:
    """Run one test inside a locked-down container. Never raises on the submission's
    own timeout/crash — those become RunResult fields, not exceptions."""
    effective_tl_s = (tl_ms * language.tl_multiplier) / 1000.0
    args = _docker_run_args(language, src_dir, ml_mb) + ["sh", "-c", language.run_cmd]

    start = time.monotonic()
    try:
        proc = subprocess.run(
            args,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=effective_tl_s + 2,  # container overhead grace period
        )
        exec_ms = int((time.monotonic() - start) * 1000)
        return RunResult(stdout=proc.stdout, exit_code=proc.returncode, timed_out=False, exec_ms=exec_ms)
    except subprocess.TimeoutExpired:
        exec_ms = int((time.monotonic() - start) * 1000)
        return RunResult(stdout="", exit_code=-1, timed_out=True, exec_ms=exec_ms)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `JUDGE_TESTS=1 python manage.py test judge.tests_sandbox -v 2`
Expected: PASS (4 tests). Requires Docker daemon running and the image built in Step 1.

- [ ] **Step 6: Commit**

```bash
git add judge
git commit -m "feat: judge sandbox (Docker compile/run) and Python image"
```

---

## Task 7: judge.runner — run_submission RQ task

**Files:**
- Create: `judge/runner.py`
- Test: `judge/tests_runner.py`

**Interfaces:**
- Consumes: `judge.sandbox.compile`, `judge.sandbox.run_test`, `judge.compare.outputs_match` (Tasks 5-6); `submissions.models.Submission`, `TestResult`, `UserProblemSolved` (Task 4).
- Produces: `judge.runner.run_submission(submission_id: int) -> None`. Side effect: updates `Submission.verdict/exec_ms/mem_kb/passed/total`, creates `TestResult` rows, and on first `AC` for a (user, problem) creates `UserProblemSolved` and increments `user.practice_points` by `problem.points`.

- [ ] **Step 1: Write the failing unit test (sandbox mocked — no Docker needed)**

`judge/tests_runner.py`:
```python
import os
import unittest
from unittest.mock import patch

from django.test import TestCase

from accounts.models import User
from judge.runner import run_submission
from judge.sandbox import CompileResult, RunResult
from problems.models import Language, Problem, TestCase as ProblemTestCase
from submissions.models import Submission, UserProblemSolved


class RunSubmissionUnitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="carol", password="pw12345")
        self.problem = Problem.objects.create(
            slug="a-plus-b", title="A+B", statement_md="x", author=self.user, points=50,
        )
        ProblemTestCase.objects.create(problem=self.problem, input="1 2\n", expected="3\n", order=0)
        self.language = Language.objects.create(
            code="python3", name="Python 3", docker_image="codearena-judge-python",
            run_cmd="python3 main.py",
        )
        self.submission = Submission.objects.create(
            user=self.user, problem=self.problem, language=self.language, source="print(3)",
        )

    @patch("judge.runner.sandbox.run_test")
    @patch("judge.runner.sandbox.compile")
    def test_all_tests_pass_awards_points(self, mock_compile, mock_run_test):
        mock_compile.return_value = CompileResult(ok=True, log="")
        mock_run_test.return_value = RunResult(stdout="3\n", exit_code=0, timed_out=False, exec_ms=10)

        run_submission(self.submission.pk)

        self.submission.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.submission.verdict, Submission.Verdict.AC)
        self.assertEqual(self.submission.passed, 1)
        self.assertEqual(self.submission.total, 1)
        self.assertEqual(self.user.practice_points, 50)
        self.assertTrue(UserProblemSolved.objects.filter(user=self.user, problem=self.problem).exists())

    @patch("judge.runner.sandbox.run_test")
    @patch("judge.runner.sandbox.compile")
    def test_wrong_output_gives_wa_no_points(self, mock_compile, mock_run_test):
        mock_compile.return_value = CompileResult(ok=True, log="")
        mock_run_test.return_value = RunResult(stdout="4\n", exit_code=0, timed_out=False, exec_ms=10)

        run_submission(self.submission.pk)

        self.submission.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.submission.verdict, Submission.Verdict.WA)
        self.assertEqual(self.user.practice_points, 0)

    @patch("judge.runner.sandbox.run_test")
    @patch("judge.runner.sandbox.compile")
    def test_timeout_gives_tle(self, mock_compile, mock_run_test):
        mock_compile.return_value = CompileResult(ok=True, log="")
        mock_run_test.return_value = RunResult(stdout="", exit_code=-1, timed_out=True, exec_ms=1000)

        run_submission(self.submission.pk)

        self.submission.refresh_from_db()
        self.assertEqual(self.submission.verdict, Submission.Verdict.TLE)

    @patch("judge.runner.sandbox.run_test")
    @patch("judge.runner.sandbox.compile")
    def test_nonzero_exit_gives_re(self, mock_compile, mock_run_test):
        mock_compile.return_value = CompileResult(ok=True, log="")
        mock_run_test.return_value = RunResult(stdout="", exit_code=1, timed_out=False, exec_ms=5)

        run_submission(self.submission.pk)

        self.submission.refresh_from_db()
        self.assertEqual(self.submission.verdict, Submission.Verdict.RE)

    @patch("judge.runner.sandbox.compile")
    def test_compile_failure_gives_ce(self, mock_compile):
        mock_compile.return_value = CompileResult(ok=False, log="SyntaxError")

        run_submission(self.submission.pk)

        self.submission.refresh_from_db()
        self.assertEqual(self.submission.verdict, Submission.Verdict.CE)

    @patch("judge.runner.sandbox.run_test")
    @patch("judge.runner.sandbox.compile")
    def test_second_ac_does_not_award_points_again(self, mock_compile, mock_run_test):
        mock_compile.return_value = CompileResult(ok=True, log="")
        mock_run_test.return_value = RunResult(stdout="3\n", exit_code=0, timed_out=False, exec_ms=10)
        run_submission(self.submission.pk)

        second = Submission.objects.create(
            user=self.user, problem=self.problem, language=self.language, source="print(3)",
        )
        run_submission(second.pk)

        self.user.refresh_from_db()
        self.assertEqual(self.user.practice_points, 50)
        self.assertEqual(UserProblemSolved.objects.filter(user=self.user, problem=self.problem).count(), 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test judge.tests_runner -v 2`
Expected: FAIL — `judge.runner` module doesn't exist yet.

- [ ] **Step 3: Write judge/runner.py**

```python
import tempfile
from pathlib import Path

from django.db import transaction

from problems.models import Language
from submissions.models import Submission, TestResult, UserProblemSolved

from . import sandbox
from .compare import outputs_match

# Where to write each language's source file inside the sandbox working dir.
_SOURCE_FILENAMES = {
    "python3": "main.py",
}


def run_submission(submission_id: int) -> None:
    submission = Submission.objects.select_related("problem", "language", "user").get(pk=submission_id)
    submission.verdict = Submission.Verdict.RUNNING
    submission.save(update_fields=["verdict"])

    language = submission.language
    filename = _SOURCE_FILENAMES.get(language.code, "main.py")

    with tempfile.TemporaryDirectory() as tmp:
        src_dir = Path(tmp)
        (src_dir / filename).write_text(submission.source)

        compile_result = sandbox.compile(language, src_dir)
        if not compile_result.ok:
            submission.verdict = Submission.Verdict.CE
            submission.save(update_fields=["verdict"])
            return

        testcases = list(submission.problem.testcases.all())
        submission.total = len(testcases)
        passed = 0
        max_exec_ms = 0
        final_verdict = Submission.Verdict.AC

        for testcase in testcases:
            run_result = sandbox.run_test(
                language, src_dir, testcase.input,
                tl_ms=submission.problem.tl_ms, ml_mb=submission.problem.ml_mb,
            )
            max_exec_ms = max(max_exec_ms, run_result.exec_ms)

            if run_result.timed_out:
                verdict = Submission.Verdict.TLE
            elif run_result.exit_code == 137:
                verdict = Submission.Verdict.MLE
            elif run_result.exit_code != 0:
                verdict = Submission.Verdict.RE
            elif outputs_match(testcase.expected, run_result.stdout):
                verdict = Submission.Verdict.AC
            else:
                verdict = Submission.Verdict.WA

            TestResult.objects.create(
                submission=submission, testcase=testcase, verdict=verdict,
                exec_ms=run_result.exec_ms, stdout_excerpt=run_result.stdout[:2000],
            )

            if verdict == Submission.Verdict.AC:
                passed += 1
            else:
                final_verdict = verdict
                break

        submission.passed = passed
        submission.exec_ms = max_exec_ms
        submission.verdict = final_verdict
        submission.save(update_fields=["passed", "total", "exec_ms", "verdict"])

        if final_verdict == Submission.Verdict.AC:
            _award_points_if_first_ac(submission)


def _award_points_if_first_ac(submission: Submission) -> None:
    with transaction.atomic():
        _, created = UserProblemSolved.objects.get_or_create(
            user=submission.user, problem=submission.problem,
            defaults={"first_ac_submission": submission},
        )
        if created:
            user = submission.user
            user.practice_points += submission.problem.points
            user.save(update_fields=["practice_points"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test judge.tests_runner -v 2`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add judge
git commit -m "feat: judge.runner run_submission task with practice points"
```

---

## Task 8: submit flow — endpoint + verdict page with HTMX polling

**Files:**
- Create: `submissions/urls.py`, `submissions/views.py`
- Create: `templates/submissions/detail.html`, `templates/submissions/_verdict.html`
- Modify: `codearena/urls.py` (wire `submissions.urls` — already done in Task 1, confirm include path)
- Test: `submissions/tests.py` (append view tests)

**Interfaces:**
- Consumes: `problems.models.Problem`, `problems.models.Language` (Task 2); `submissions.models.Submission` (Task 4); `judge.jobs.enqueue_submission` (Task 9 — mocked in this task's tests, implemented next task so `submit_solution` can call it without waiting).
- Produces: `POST /submissions/submit/<slug>/` (name `submit_solution`) → creates a `Submission(verdict=PENDING)`, calls `judge.jobs.enqueue_submission(submission.id)`, redirects to `submission_detail`. `GET /submissions/<id>/` (name `submission_detail`) → full page. `GET /submissions/<id>/verdict/` (name `submission_verdict`) → HTMX polling fragment.

Since Task 9 (the real `jobs.enqueue_submission`) doesn't exist yet, this task creates a minimal `judge/jobs.py` stub now with the final signature, and Task 9 replaces its body with the real RQ wiring — the view code never changes.

- [ ] **Step 1: Write a minimal judge/jobs.py (Task 9 will replace the body)**

```python
def enqueue_submission(submission_id: int) -> None:
    """Queue run_submission for background execution. Replaced with real RQ
    wiring in the next task; kept as a same-thread call for now so the submit
    flow is testable end-to-end before the worker exists."""
    from .runner import run_submission

    run_submission(submission_id)
```

- [ ] **Step 2: Write the failing tests**

`submissions/tests.py` (append):
```python
from unittest.mock import patch

from problems.models import TestCase as ProblemTestCase


class SubmitFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="dave", password="pw12345")
        self.problem = Problem.objects.create(
            slug="a-plus-b", title="A+B", statement_md="x", author=self.user, is_public=True,
        )
        ProblemTestCase.objects.create(problem=self.problem, input="1 2\n", expected="3\n", order=0)
        Language.objects.create(
            code="python3", name="Python 3", docker_image="codearena-judge-python",
            run_cmd="python3 main.py",
        )
        self.client.force_login(self.user)

    @patch("submissions.views.jobs.enqueue_submission")
    def test_submit_creates_pending_submission_and_enqueues(self, mock_enqueue):
        response = self.client.post(
            f"/submissions/submit/{self.problem.slug}/", {"source": "print(3)"},
        )
        submission = Submission.objects.get(user=self.user, problem=self.problem)
        self.assertEqual(submission.verdict, Submission.Verdict.PENDING)
        self.assertRedirects(response, f"/submissions/{submission.pk}/")
        mock_enqueue.assert_called_once_with(submission.pk)

    def test_submit_requires_login(self):
        self.client.logout()
        response = self.client.post(
            f"/submissions/submit/{self.problem.slug}/", {"source": "print(3)"},
        )
        self.assertEqual(response.status_code, 302)

    @patch("submissions.views.jobs.enqueue_submission")
    def test_detail_page_shows_verdict(self, mock_enqueue):
        self.client.post(f"/submissions/submit/{self.problem.slug}/", {"source": "print(3)"})
        submission = Submission.objects.get(user=self.user, problem=self.problem)
        response = self.client.get(f"/submissions/{submission.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PENDING")

    @patch("submissions.views.jobs.enqueue_submission")
    def test_detail_404_for_other_users_submission(self, mock_enqueue):
        self.client.post(f"/submissions/submit/{self.problem.slug}/", {"source": "print(3)"})
        submission = Submission.objects.get(user=self.user, problem=self.problem)
        other = User.objects.create_user(username="eve", password="pw12345")
        self.client.force_login(other)
        response = self.client.get(f"/submissions/{submission.pk}/")
        self.assertEqual(response.status_code, 404)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python manage.py test submissions.SubmitFlowTests -v 2`
Expected: FAIL — no `submissions.urls`/`submissions.views` yet.

- [ ] **Step 4: Write submissions/views.py**

```python
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from problems.models import Language, Problem

from . import jobs
from .models import Submission


@login_required
def submit_solution(request, slug):
    problem = get_object_or_404(Problem, slug=slug, is_public=True)
    language = Language.objects.get(code="python3")  # only language in this phase
    submission = Submission.objects.create(
        user=request.user, problem=problem, language=language,
        source=request.POST.get("source", ""),
    )
    jobs.enqueue_submission(submission.id)
    return redirect("submission_detail", pk=submission.pk)


@login_required
def submission_detail(request, pk):
    submission = get_object_or_404(Submission, pk=pk, user=request.user)
    return render(request, "submissions/detail.html", {"submission": submission})


@login_required
def submission_verdict(request, pk):
    submission = get_object_or_404(Submission, pk=pk, user=request.user)
    return render(request, "submissions/_verdict.html", {"submission": submission})
```

- [ ] **Step 5: Write submissions/urls.py**

```python
from django.urls import path

from . import views

urlpatterns = [
    path("submit/<slug:slug>/", views.submit_solution, name="submit_solution"),
    path("<int:pk>/", views.submission_detail, name="submission_detail"),
    path("<int:pk>/verdict/", views.submission_verdict, name="submission_verdict"),
]
```

- [ ] **Step 6: Write templates/submissions/_verdict.html**

```html
<div id="verdict"
     {% if submission.verdict == "PENDING" or submission.verdict == "RUNNING" %}
     hx-get="{% url 'submission_verdict' submission.pk %}"
     hx-trigger="every 1s"
     hx-swap="outerHTML"
     {% endif %}>
    <p class="font-mono text-lg">{{ submission.verdict }}</p>
    {% if submission.total %}
    <p class="text-sm text-slate-500">{{ submission.passed }}/{{ submission.total }} tests passed</p>
    {% endif %}
</div>
```

- [ ] **Step 7: Write templates/submissions/detail.html**

```html
{% extends "base.html" %}
{% block content %}
<h1 class="text-xl font-bold">Submission #{{ submission.pk }}</h1>
<p class="text-sm text-slate-500">{{ submission.problem.title }} · {{ submission.language.name }}</p>
{% include "submissions/_verdict.html" %}
<pre class="bg-slate-100 p-2 rounded mt-4 font-mono text-sm">{{ submission.source }}</pre>
{% endblock %}
```

- [ ] **Step 8: Run test to verify it passes**

Run: `python manage.py test submissions -v 2`
Expected: PASS (all `submissions` tests, including Task 4's model tests).

- [ ] **Step 9: Commit**

```bash
git add submissions judge/jobs.py templates/submissions
git commit -m "feat: submit flow with HTMX-polled verdict page"
```

---

## Task 9: RQ worker wiring + Docker Compose + README

**Files:**
- Modify: `judge/jobs.py` (replace stub body with real RQ enqueue)
- Create: `judge/worker.py` (worker entrypoint)
- Create: `Dockerfile`, `docker-compose.yml`
- Create: `README.md`
- Test: `judge/tests_jobs.py`

**Interfaces:**
- Produces: `judge.jobs.get_queue() -> rq.Queue`; `judge.jobs.enqueue_submission(submission_id: int) -> None` (now actually enqueues onto Redis instead of calling `run_submission` inline). `python manage.py runworker` is **not** used — RQ workers run via the standalone `rq worker` CLI pointed at `judge/worker.py`'s Django-bootstrapping module.

- [ ] **Step 1: Write the failing test**

`judge/tests_jobs.py`:
```python
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from judge import jobs


class EnqueueSubmissionTests(SimpleTestCase):
    @patch("judge.jobs.get_queue")
    def test_enqueue_submission_pushes_to_queue(self, mock_get_queue):
        mock_queue = MagicMock()
        mock_get_queue.return_value = mock_queue

        jobs.enqueue_submission(42)

        mock_queue.enqueue.assert_called_once_with("judge.runner.run_submission", 42)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test judge.tests_jobs -v 2`
Expected: FAIL — current `jobs.enqueue_submission` calls `run_submission` directly, `get_queue` doesn't exist.

- [ ] **Step 3: Replace judge/jobs.py**

```python
from django.conf import settings
from redis import Redis
from rq import Queue

_queue = None


def get_queue() -> Queue:
    global _queue
    if _queue is None:
        _queue = Queue(connection=Redis.from_url(settings.REDIS_URL))
    return _queue


def enqueue_submission(submission_id: int) -> None:
    """Queue run_submission for background execution by the judge worker."""
    get_queue().enqueue("judge.runner.run_submission", submission_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test judge.tests_jobs -v 2`
Expected: PASS (1 test).

- [ ] **Step 5: Note the now-stale mocks in submissions/tests.py**

Task 8's tests patch `submissions.views.jobs.enqueue_submission` directly (not `get_queue`), so they still pass unchanged — they never touch Redis. Run the full suite to confirm:

Run: `python manage.py test -v 2`
Expected: PASS (all tests across `accounts`, `problems`, `submissions`, `judge`).

- [ ] **Step 6: Write judge/worker.py**

```python
"""RQ worker entrypoint: bootstraps Django settings before processing jobs
so judge.runner can use the ORM."""
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "codearena.settings")
django.setup()

from django.conf import settings
from redis import Redis
from rq import Queue, Worker

if __name__ == "__main__":
    redis_conn = Redis.from_url(settings.REDIS_URL)
    worker = Worker([Queue(connection=redis_conn)], connection=redis_conn)
    worker.work()
```

- [ ] **Step 7: Write Dockerfile**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
```

- [ ] **Step 8: Write docker-compose.yml**

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: codearena
      POSTGRES_USER: codearena
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-change-me}
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7

  web:
    build: .
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    environment:
      POSTGRES_HOST: db
      POSTGRES_DB: codearena
      POSTGRES_USER: codearena
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-change-me}
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - db
      - redis

  judge-worker:
    build: .
    command: python judge/worker.py
    volumes:
      - .:/app
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      POSTGRES_HOST: db
      POSTGRES_DB: codearena
      POSTGRES_USER: codearena
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-change-me}
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - db
      - redis

volumes:
  pgdata:
```

- [ ] **Step 9: Write README.md**

```markdown
# CodeArena

Competitive-programming platform. See `docs/superpowers/specs/2026-09-15-codearena-design.md`
for the full design.

## Local dev (no Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Tests use SQLite automatically; no services required:
```bash
python manage.py test
```

Judge sandbox tests need Docker and the judge image:
```bash
docker build -t codearena-judge-python judge/images/python
JUDGE_TESTS=1 python manage.py test judge
```

## Full stack (Docker Compose)

```bash
cp .env.example .env
docker build -t codearena-judge-python judge/images/python
docker compose up --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

Visit `http://localhost:8000/problems/`. Add a `Language` row (`code=python3`,
`docker_image=codearena-judge-python`, `run_cmd=python3 main.py`) and a `Problem`
with a `TestCase` via `/admin/` before submitting.
```

- [ ] **Step 10: Manual smoke test**

```bash
cp .env.example .env
docker build -t codearena-judge-python judge/images/python
docker compose up --build -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py shell -c "
from accounts.models import User
from problems.models import Language, Problem, TestCase
u = User.objects.create_user(username='smoke', password='pw12345')
Language.objects.create(code='python3', name='Python 3', docker_image='codearena-judge-python', run_cmd='python3 main.py')
p = Problem.objects.create(slug='a-plus-b', title='A+B', statement_md='sum', author=u)
TestCase.objects.create(problem=p, input='1 2\n', expected='3\n', order=0)
"
```
Then log in at `http://localhost:8000/admin/` as `smoke`, visit `/problems/a-plus-b/`,
submit `a, b = map(int, input().split()); print(a + b)`, and confirm the verdict page
polls to `AC` within a couple seconds. Tear down: `docker compose down`.

- [ ] **Step 11: Commit**

```bash
git add judge/jobs.py judge/worker.py judge/tests_jobs.py Dockerfile docker-compose.yml README.md
git commit -m "feat: RQ worker, Docker Compose stack, README"
```

---

## Self-Review Notes

- **Spec coverage:** Data model (§1) — accounts/problems/submissions models done, `contest` FK on `Submission` and `integrity` app explicitly deferred per Global Constraints. Judge (§2) — full compile/run/compare/runner pipeline implemented for Python; Docker flags match spec exactly. Contests/rating (§3) — out of scope for this plan (Phase 3). Anti-AI (§4) — out of scope (Phase 4). UI (§5) — problem list/detail, submission detail with polling; `/submissions` (mine), `/rating`, `/top`, `/profile`, contest pages are later phases. Testing (§6) — judge integration tests gated by `JUDGE_TESTS=1` as specified; rating/standings tests belong to the contests plan.
- **Placeholder scan:** none found — every step has runnable code.
- **Type consistency:** `Language.code` values (`"python3"`) match between `problems/tests.py`, `submissions/tests.py`, `judge/tests_runner.py`, and `submissions/views.py`. `RunResult`/`CompileResult` field names match between `judge/sandbox.py` and every caller/test. `jobs.enqueue_submission(submission_id)` signature is identical across the stub (Task 8) and the real implementation (Task 9), so `submissions/views.py` never changes.
