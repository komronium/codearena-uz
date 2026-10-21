"""Work that moves many ratings runs in the worker (the "default" queue), so a staff click returns at once."""
import django_rq
from django.conf import settings

from . import rating
from .models import Contest


def apply_rating(contest_id: int) -> bool:
    """Apply a finished rated contest's rating (rating.apply_rating is idempotent)."""
    return rating.apply_rating(Contest.objects.get(pk=contest_id))


def run(func, *args):
    """Queue `func(*args)` for the worker; with RQ_ASYNC off (tests, a dev box without a worker) run it now."""
    if getattr(settings, "RQ_ASYNC", True):
        return django_rq.get_queue("default").enqueue(func, *args, job_timeout=600)
    return func(*args)
