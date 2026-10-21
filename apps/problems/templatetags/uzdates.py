"""Uzbek weekday names for dates; Django's own "D" prints English ("Mon")."""
from django import template
from django.utils.translation import gettext as _t, gettext_lazy as _tl

register = template.Library()

WEEKDAYS = [_tl("Du"), _tl("Se"), _tl("Ch"), _tl("Pa"), _tl("Ju"), _tl("Sh"), _tl("Ya")]
WEEKDAYS_FULL = [_tl("Dushanba"), _tl("Seshanba"), _tl("Chorshanba"), _tl("Payshanba"), _tl("Juma"), _tl("Shanba"), _tl("Yakshanba")]
MONTHS = [_tl("Yan"), _tl("Fev"), _tl("Mar"), _tl("Apr"), _tl("May"), _tl("Iyn"), _tl("Iyl"), _tl("Avg"), _tl("Sen"), _tl("Okt"), _tl("Noy"), _tl("Dek")]


@register.filter
def weekday_uz(value) -> str:
    return str(WEEKDAYS[value.weekday()]) if value else ""


@register.filter
def month_uz(value) -> str:
    """Three letters of the month: Okt."""
    return str(MONTHS[value.month - 1]) if value else ""


@register.filter
def weekday_full(value) -> str:
    return str(WEEKDAYS_FULL[value.weekday()]) if value else ""


@register.filter
def ago_uz(value) -> str:
    """"5 daqiqa oldin", "3 soat oldin", "2 kun oldin": how long ago, in Uzbek (Django's timesince is English)."""
    from django.utils import timezone

    seconds = int((timezone.now() - value).total_seconds())
    if seconds < 60:
        return _t("hozirgina")
    for size, msg in ((86400, _tl("{n} kun oldin")), (3600, _tl("{n} soat oldin")), (60, _tl("{n} daqiqa oldin"))):
        if seconds >= size:
            return str(msg).format(n=seconds // size)
    return _t("hozirgina")
