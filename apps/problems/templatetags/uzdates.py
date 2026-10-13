"""Uzbek weekday names for dates; Django's own "D" prints English ("Mon")."""
from django import template

register = template.Library()

WEEKDAYS = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]


@register.filter
def weekday_uz(value) -> str:
    return WEEKDAYS[value.weekday()] if value else ""


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
