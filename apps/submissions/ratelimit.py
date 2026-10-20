"""Per-user request counters in the Django cache."""
from django.core.cache import cache

WINDOW_S = 60


def rate_limited(user_id: int, kind: str, limit: int) -> bool:
    """True once `user_id` has made `limit` requests of `kind` in the current window. The counter is added and
    incremented atomically in the cache, so a burst of parallel requests cannot all slip under the limit."""
    # ponytail: fixed window, not sliding: a burst can land 2x limit across a window boundary.
    key = f"{kind}-rl:{user_id}"
    cache.add(key, 0, timeout=WINDOW_S)
    try:
        return cache.incr(key) > limit
    except ValueError:  # expired between the two calls
        cache.set(key, 1, timeout=WINDOW_S)
        return False
