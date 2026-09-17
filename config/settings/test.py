from .base import *  # noqa: F401,F403

DEBUG = True
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
