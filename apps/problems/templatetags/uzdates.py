"""Uzbek weekday names for dates; Django's own "D" prints English ("Mon")."""
from django import template

register = template.Library()

WEEKDAYS = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]
WEEKDAYS_FULL = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
MONTHS = ["Yan", "Fev", "Mar", "Apr", "May", "Iyn", "Iyl", "Avg", "Sen", "Okt", "Noy", "Dek"]


@register.filter
def weekday_uz(value) -> str:
    return WEEKDAYS[value.weekday()] if value else ""


@register.filter
def month_uz(value) -> str:
    """Three letters of the month: Okt."""
    return MONTHS[value.month - 1] if value else ""


@register.filter
def weekday_full(value) -> str:
    return WEEKDAYS_FULL[value.weekday()] if value else ""


@register.filter
def ago_uz(value) -> str:
    """"5 daqiqa oldin", "3 soat oldin", "2 kun oldin": how long ago, in Uzbek (Django's timesince is English)."""
    from django.utils import timezone

    seconds = int((timezone.now() - value).total_seconds())
    if seconds < 60:
        return "hozirgina"
    for size, unit in ((86400, "kun"), (3600, "soat"), (60, "daqiqa")):
        if seconds >= size:
            return f"{seconds // size} {unit} oldin"
    return "hozirgina"
