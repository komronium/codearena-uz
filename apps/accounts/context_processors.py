from django.utils.functional import SimpleLazyObject

from .models import User
from .tiers import TIER_BANNERS, TIER_ORDER, rating_tier


def _claim_tier_up(user) -> dict | None:
    """Record the user's current tier; a congratulation when it is higher than the one last
    shown. The UPDATE is conditional on the old value, so two tabs loading at once can't both
    congratulate; the first visit only records, a drop is recorded silently."""
    now, seen = rating_tier(user.rating), user.seen_tier
    if seen == now:
        return None
    claimed = User.objects.filter(pk=user.pk, seen_tier=seen).update(seen_tier=now)
    user.seen_tier = now
    if claimed and seen and TIER_ORDER.get(now, 0) > TIER_ORDER.get(seen, 0):
        slug, picture = TIER_BANNERS[now]
        return {"name": now, "slug": slug, "picture": picture, "was": seen}
    return None


def tier_up(request):
    """{"tier_up": ...}: lazy, so the tier is only claimed by a page that actually draws the
    dialog (base.html asks for it); django-rq's admin pages and htmx fragments never do."""
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated) or request.headers.get("HX-Request"):
        return {}
    return {"tier_up": SimpleLazyObject(lambda: _claim_tier_up(user))}
