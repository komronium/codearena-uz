from .models import User
from .views import _RATING_TIERS, _TIER_BANNERS, rating_tier

_ORDER = {name: i for i, (_f, _c, name, _col) in enumerate(_RATING_TIERS)}


def tier_up(request):
    """{"tier_up": {...}} once, on the first full page after the user's rating tier went up.
    The first visit only records the tier; a drop is recorded silently. HTMX partials are skipped
    so a polled fragment can't swallow the moment."""
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated) or request.headers.get("HX-Request"):
        return {}
    now = rating_tier(user.rating)
    seen = user.seen_tier
    if seen == now:
        return {}
    user.seen_tier = now
    User.objects.filter(pk=user.pk).update(seen_tier=now)
    if seen and _ORDER.get(now, 0) > _ORDER.get(seen, 0):
        slug, picture = _TIER_BANNERS[now]
        return {"tier_up": {"name": now, "slug": slug, "picture": picture, "was": seen}}
    return {}
