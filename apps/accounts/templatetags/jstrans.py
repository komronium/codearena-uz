"""{% jt "Uzbek text" %}: the translation of a string for use inside inline JavaScript (any quoting: it is escaped for a
JS string or template literal). Static scripts ask for theirs through window.caT, fed by window.caStrings (base.html)."""
from django import template
from django.utils.html import escapejs
from django.utils.translation import gettext

register = template.Library()


@register.simple_tag
def jt(text: str) -> str:
    return escapejs(gettext(text))
