"""AI translation in the worker (the "default" queue); with RQ_ASYNC off it runs in place."""
from apps.contests.jobs import run

from . import service


def translate_one(kind: str, pk: int) -> int:
    obj = service.model_of(kind).objects.get(pk=pk)
    return service.ai_translate(obj)


def enqueue_one(kind: str, pk: int):
    return run(translate_one, kind, pk)


def enqueue_missing(kind: str) -> int:
    """One job per object without a translation (a long list in one job would run out of time). Returns how many."""
    n = 0
    for obj in service.model_of(kind).objects.all().order_by("pk"):
        if service.status(obj) == "none":
            run(translate_one, kind, obj.pk)
            n += 1
    return n
