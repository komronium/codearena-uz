import json

from django import template
from django.utils.html import json_script

from apps.accounts.places import payload

register = template.Library()


@register.simple_tag
def places_data():
    """The cities and schools for the pickers (static/js/places.js), as a <script type="application/json">."""
    return json_script(json.loads(json.dumps(payload())), "places-data")


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
    name = COUNTRIES[code]
    label = title or ", ".join(p for p in (getattr(who, "location", ""), name) if p)
    return format_html('<img class="ca-flag" src="{}" alt="{}" title="{}" width="18" height="14" loading="lazy">',
                       static(f"flags/{code.lower()}.svg"), label, label)
