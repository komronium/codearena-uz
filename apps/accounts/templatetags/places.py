import json

from django import template
from django.utils.html import json_script

from apps.accounts.places import payload

register = template.Library()


@register.simple_tag
def places_data():
    """The cities and schools for the pickers (static/js/places.js), as a <script type="application/json">."""
    return json_script(json.loads(json.dumps(payload())), "places-data")
