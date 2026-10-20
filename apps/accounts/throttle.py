"""Request limits for the pages anyone can reach: sign-in, sign-up, password reset and the confirmation mail. Each
mail costs a send from a small daily quota and each sign-in is a password guess, so they are counted per client
address and, for sign-in and reset, per account name or email as well. Counters live in the Django cache (a fixed
window). Schools share one address, so the per-address limits are generous; the per-account ones are tight."""
from django.core.cache import cache

TOO_MANY = "Juda ko‘p urinish. Biroz kutib, qayta urinib ko‘ring."


def client_ip(request) -> str:
    """The client's address: config.middleware.real_client_ip has already put the one nginx saw into REMOTE_ADDR
    (and only trusts the header from the local proxy), so a spoofed X-Forwarded-For does not count."""
    return request.META.get("REMOTE_ADDR", "")[:45]


def blocked(key: str, limit: int, window: int) -> bool:
    """Count one request under `key`; True once it is past `limit` within `window` seconds."""
    cache.add(key, 0, timeout=window)
    try:
        return cache.incr(key) > limit
    except ValueError:  # the key expired between the two calls
        cache.set(key, 1, timeout=window)
        return False


def ip_blocked(request, scope: str, limit: int, window: int) -> bool:
    return blocked(f"thr:{scope}:{client_ip(request)}", limit, window)
