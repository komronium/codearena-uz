from .base import *  # noqa: F401,F403

DEBUG = True
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Most tests post submissions directly; the editor rule has its own tests (override_settings).
PRACTICE_REQUIRE_EDITOR = False
