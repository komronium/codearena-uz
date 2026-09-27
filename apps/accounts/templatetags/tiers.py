from django import template

from apps.accounts.views import _tier_color, rating_tier

register = template.Library()


@register.filter
def tier_name(rating: int) -> str:
    return rating_tier(rating)


@register.filter
def tier_color(rating: int) -> str:
    return _tier_color(rating)


@register.filter
def tier_slug(rating: int) -> str:
    """CSS modifier of the tier's picture: .ca-banner-<slug> / .ca-art-<slug>."""
    from apps.accounts.views import _TIER_BANNERS
    return _TIER_BANNERS[rating_tier(rating)][0]
