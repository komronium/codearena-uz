import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure")
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_rq",
    "apps.accounts.apps.AccountsConfig",
    "apps.problems.apps.ProblemsConfig",
    "apps.contests.apps.ContestsConfig",
    "apps.submissions.apps.SubmissionsConfig",
    "apps.integrity.apps.IntegrityConfig",
    "apps.moderation.apps.ModerationConfig",
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

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

if os.environ.get("POSTGRES_HOST"):
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": os.environ["POSTGRES_HOST"],
        "NAME": os.environ.get("POSTGRES_DB", "codearena"),
        "USER": os.environ.get("POSTGRES_USER", "codearena"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
    }}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["apps.accounts.backends.EmailOrUsernameBackend"]
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "problems:list"
LOGOUT_REDIRECT_URL = "problems:list"

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
# "run" = "Sinab ko'rish" trial runs; workers listen `default run`, so real submissions go first.
RQ_QUEUES = {"default": {"URL": REDIS_URL, "DEFAULT_TIMEOUT": 600},
             "run": {"URL": REDIS_URL, "DEFAULT_TIMEOUT": 120}}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}}

# Host path shared between worker container and docker daemon; must be identical on both sides.
JUDGE_WORK_DIR = os.environ.get("JUDGE_WORK_DIR", str(BASE_DIR / "work"))
JUDGE_IMAGE_PREFIX = "codearena-judge-"

# Console backend by default (prints to stdout/log) — set EMAIL_BACKEND to
# "django.core.mail.backends.smtp.EmailBackend" + EMAIL_HOST/PORT/... in prod.
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") == "1"
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@codearena.local")

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Tashkent"
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

PASSWORD_HASHERS = ["apps.accounts.hashers.PBKDF2Hasher300k",
                    "django.contrib.auth.hashers.PBKDF2PasswordHasher"]
