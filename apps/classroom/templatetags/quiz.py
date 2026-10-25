"""What the duel pages show of a bank question that is stored in one language: the "Xato" option and the explanation
(a msgid of the catalogue, like the interface's own text). The stored value stays what the answer is checked against."""
from django import template
from django.utils.translation import gettext

register = template.Library()


@register.filter
def quiz_label(value):
    """An answer or option as shown: only the error option has a word of its own."""
    return gettext("Xato") if value == "Xato" else value


@register.filter
def quiz_text(value):
    """The explanation of a question in the page language; one the catalogue doesn't know stays as written."""
    return gettext(value) if value else value
