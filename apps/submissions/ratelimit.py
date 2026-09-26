"""Per-user request counters in the Django cache."""
from django.core.cache import cache

WINDOW_S = 60


def rate_limited(user_id: int, kind: str, limit: int) -> bool:
    """True once `user_id` has made `limit` requests of `kind` in the current window."""
    # ponytail: fixed window, not sliding — a burst can land 2x limit across a window
    # boundary. Good enough to stop a spam script; swap for a sliding/token-bucket
    # counter if that boundary burst becomes a problem.
    key = f"{kind}-rl:{user_id}"
    count = cache.get(key)
    if count is None:
        cache.set(key, 1, timeout=WINDOW_S)
        return False
    if count >= limit:
        return True
    cache.incr(key)
    return False
