from .base import *  # noqa: F401,F403

DEBUG = True
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Most tests post submissions directly; the editor rule has its own tests (override_settings).
PRACTICE_REQUIRE_EDITOR = False
# the tests read the old Uzbek spelling of the source strings; one test turns the new one on
LOCALE_PATHS = [BASE_DIR / "locale"]
RQ_ASYNC = False  # jobs run inline, so a test sees their result
GUEST_CACHE_SECONDS = 0

# The account gate has its own tests (override_settings); everyone else's test users go straight in.
ACCOUNT_GATE = False
