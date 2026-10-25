import json

from django import template
from django.utils.html import json_script
from django.utils.translation import get_language

from apps.accounts.places import payload
from apps.api import english

register = template.Library()


@register.filter
def city_label(name):
    """A city (or region) as stored, in the page language: lists and profiles keep the Uzbek spelling, English pages
    show the English one. A name nobody mapped (a person's own text) stays as it is."""
    return english.city(name, get_language()) or name


@register.filter
def school_label(name):
    return english.school(name, get_language()) or name


@register.simple_tag
def places_data():
    """The cities and schools for the pickers (static/js/places.js), as a <script type="application/json">. On an
    English page `labels` says how to show each stored name; the stored value stays the Uzbek spelling."""
    data = json.loads(json.dumps(payload()))
    if get_language() == "en":
        names = {name for groups in data["cities"].values() for heading, cities in groups for name in [heading, *cities] if name}
        names |= {name for by_city in data["schools"].values() for heading, schools in by_city for name in [heading, *schools] if name}
        data["labels"] = {name: english.city(name, "en") or english.school(name, "en") or name for name in sorted(names)}
        data["labels"] = {k: v for k, v in data["labels"].items() if k != v}
    return json_script(data, "places-data")


@register.simple_tag
def flag(who, title=""):
    """A country's flag (static/flags/<code>.svg) for a user or an ISO code; nothing when there is no country.
    The tooltip and the alt text are the country (a user's: city first)."""
    from django.templatetags.static import static
    from django.utils.html import format_html

    from apps.accounts.countries import COUNTRIES

    code = getattr(who, "country", who) or ""
    if code not in COUNTRIES:
        return ""
    name = str(COUNTRIES[code])
    label = title or ", ".join(p for p in (city_label(getattr(who, "location", "")), name) if p)
    return format_html('<img class="ca-flag" src="{}" alt="{}" title="{}" width="18" height="14" loading="lazy">',
                       static(f"flags/{code.lower()}.svg"), label, label)
