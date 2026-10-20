import os

from .base import *  # noqa: F401,F403
from .base import MIDDLEWARE

DEBUG = False
SECRET_KEY = os.environ["SECRET_KEY"]
ALLOWED_HOSTS = os.environ["ALLOWED_HOSTS"].split(",")
CSRF_TRUSTED_ORIGINS = [
    o for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o
]

# Static files served by whitenoise from STATIC_ROOT (collectstatic runs on container start).
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

# Secure cookies only make sense behind HTTPS; plain http://ip:port deploys must keep them off
# or every login silently fails.
if os.environ.get("USE_HTTPS", "0") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    MIDDLEWARE.insert(0, "config.middleware.real_client_ip")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # HSTS: set HSTS_SECONDS (e.g. 31536000) in .env once every subdomain is on HTTPS; 0 leaves it off.
    SECURE_HSTS_SECONDS = int(os.environ.get("HSTS_SECONDS", "0"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False

# Reuse DB connections across requests: with gthread every request would otherwise
# open a fresh Postgres connection, which dominates the 1s status-poll cost.
DATABASES["default"]["CONN_MAX_AGE"] = 60  # noqa: F405

# Error tracking: set SENTRY_DSN (and install sentry-sdk) to send unhandled errors to Sentry; unset, nothing happens.
if os.environ.get("SENTRY_DSN"):
    try:
        import sentry_sdk

        sentry_sdk.init(dsn=os.environ["SENTRY_DSN"], traces_sample_rate=0.0, send_default_pii=False)
    except ImportError:
        pass
