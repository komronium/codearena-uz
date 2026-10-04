from django import template

from apps.accounts.tiers import is_legendary, rating_tier, tier_banner, tier_color as _tier_color

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
    return tier_banner(rating)[0]


@register.filter
def lg(rating: int) -> str:
    """' ca-lg' for a legendary rating, else '': append it to the class of a tier-coloured name."""
    return " ca-lg" if is_legendary(rating) else ""
