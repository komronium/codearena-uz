from django import template

from apps.accounts.views import _tier_color, rating_tier

register = template.Library()


@register.filter
def tier_name(rating: int) -> str:
    return rating_tier(rating)


@register.filter
def tier_color(rating: int) -> str:
    return _tier_color(rating)
