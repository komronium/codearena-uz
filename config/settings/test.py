from .base import *  # noqa: F401,F403

DEBUG = True
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Most tests post submissions directly; the editor rule has its own tests (override_settings).
PRACTICE_REQUIRE_EDITOR = False
# The site's main language is English, but most tests were written against the Uzbek source strings (and their old
# spelling), so the suite runs as an Uzbek-first site: the plain path and "nothing chosen" are Uzbek, English is /en/.
# apps/translations/test_english_main.py turns the production setup (English main, new Uzbek spelling) on.
LANGUAGE_CODE = "uz"
LANGUAGES = [("uz", "O‘zbekcha"), ("en", "English")]
LOCALE_PATHS = [BASE_DIR / "locale"]
RQ_ASYNC = False  # jobs run inline, so a test sees their result
GUEST_CACHE_SECONDS = 0

# The account gate has its own tests (override_settings); everyone else's test users go straight in.
ACCOUNT_GATE = False

# Hundreds of tests create users with a password; the site's 300k-round hasher costs about a tenth of a second each time.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
