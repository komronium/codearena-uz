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
    "django.contrib.sitemaps",
    "django_rq",
    "apps.accounts.apps.AccountsConfig",
    "apps.problems.apps.ProblemsConfig",
    "apps.contests.apps.ContestsConfig",
    "apps.submissions.apps.SubmissionsConfig",
    "apps.integrity.apps.IntegrityConfig",
    "apps.moderation.apps.ModerationConfig",
    "apps.classroom.apps.ClassroomConfig",
    "apps.learn.apps.LearnConfig",
    "apps.api.apps.ApiConfig",  # the public read-only JSON API (no models)
    "apps.translations.apps.TranslationsConfig",  # the other-language text of problems, courses and contests
    "apps.home",  # no models: the front page, sitemap and the head tags' template filters
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "apps.accounts.language.LanguageMiddleware",  # the page language: cookie, then the account, else Uzbek
    "apps.accounts.onboarding.OnboardingMiddleware",  # name, country, city and a confirmed email first
    "apps.classroom.switch.DuelSwitchMiddleware",  # the staff can close the duels for a lesson
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"builtins": ["apps.problems.templatetags.numbers", "django.templatetags.i18n", "apps.accounts.templatetags.jstrans"], "context_processors": [
        "django.template.context_processors.request",
        "django.template.context_processors.i18n",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "apps.problems.context_processors.streak",
        "apps.accounts.context_processors.tier_up",
        "apps.accounts.context_processors.new_badges",
        "apps.accounts.context_processors.gate_nudge",
        "apps.home.context_processors.analytics",
        "apps.accounts.notifications.bell",
        "apps.home.context_processors.nav",
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
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
# "run" = "Sinab ko'rish" trial runs, "rejudge" = staff rejudges; workers listen
# `default run rejudge`, so real submissions go first and a rejudge never delays them.
RQ_QUEUES = {"default": {"URL": REDIS_URL, "DEFAULT_TIMEOUT": 600},
             "run": {"URL": REDIS_URL, "DEFAULT_TIMEOUT": 120},
             "rejudge": {"URL": REDIS_URL, "DEFAULT_TIMEOUT": 600},
             "notifications": {"URL": REDIS_URL, "DEFAULT_TIMEOUT": 60}}
RQ_ASYNC = True  # staff actions that touch every rating (apply a contest's rating) run in the worker, not in the request
GUEST_CACHE_SECONDS = 60  # the landing page's figures and last podium: the same for every guest, so work them out once a minute
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
# Signed-in users fill in their profile and confirm their email before any page opens (apps.accounts.onboarding).
# Visitor statistics (privacy-friendly, no cookies): set ANALYTICS_DOMAIN to the site's host to switch the script on.
# ANALYTICS_SRC points at a self-hosted Plausible or Umami script if there is one.
ANALYTICS_DOMAIN = os.environ.get("ANALYTICS_DOMAIN", "")
ANALYTICS_SRC = os.environ.get("ANALYTICS_SRC", "https://plausible.io/js/script.js")

# Needs working mail in production: set the EMAIL_* above first, or ACCOUNT_GATE=0 holds it off.
ACCOUNT_GATE = os.environ.get("ACCOUNT_GATE", "1") == "1"
# an avatar is checked at 2 MB in ProfileEditForm; larger uploads spill to disk instead of memory
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
USERNAME_CHANGE_DAYS = 90  # a user may rename themselves once in this many days

# Telegram Bot API: create the bot with @BotFather, then configure its webhook after deploy.
# "Google bilan kirish": an OAuth client from the Google Cloud console (redirect URI: <site>/accounts/google/callback/).
# Unset, the buttons do not appear.
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME", "").lstrip("@")
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
SITE_URL = os.environ.get("SITE_URL", "https://codearena.uz").rstrip("/")

LANGUAGE_CODE = "uz"  # the language of the source strings (msgids); English is locale/en
LANGUAGES = [("uz", "O‘zbekcha"), ("en", "English")]
# locale: English; locale_uz: the Uzbek source strings in the new spelling (O‘ -> Ö, G‘ -> Ğ, Sh -> Ş, Ch -> Ç; tools/uz_alphabet.py).
# Take locale_uz out of the list to go back to the old spelling.
LOCALE_PATHS = [BASE_DIR / "locale", BASE_DIR / "locale_uz"]
FORMAT_MODULE_PATH = ["config.formats"]  # one decimal point in both languages: numbers also land in CSS and scripts
TIME_ZONE = "Asia/Tashkent"
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

PASSWORD_HASHERS = ["apps.accounts.hashers.PBKDF2Hasher300k",
                    "django.contrib.auth.hashers.PBKDF2PasswordHasher"]

# Search engines (apps/home/templatetags/seo.py). The HTML-tag codes of Google Search Console and Yandex
# Webmaster, printed in every page's head; a DNS record verifies the domain without them.
SITE_VERIFICATION = {
    "google-site-verification": os.environ.get("GOOGLE_SITE_VERIFICATION", ""),
    "yandex-verification": os.environ.get("YANDEX_VERIFICATION", ""),
}
# The site's own pages elsewhere (Telegram channel, Instagram, GitHub...), comma-separated: the
# Organization's sameAs, which ties them to the site in search.
SITE_SAME_AS = [u.strip() for u in os.environ.get("SITE_SAME_AS", "").split(",") if u.strip()]
