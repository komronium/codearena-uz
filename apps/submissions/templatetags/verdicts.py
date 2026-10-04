from django import template

from apps.submissions.models import VERDICT_LABELS

register = template.Library()

# Accepted reads "Qabul qilindi", after Codeforces: the judge took the solution (the filter lists still say "To‘g‘ri").
_WORDS = {**VERDICT_LABELS, "AC": "Qabul qilindi"}


@register.filter
def verdict_words(code: str) -> str:
    """A verdict in Uzbek words: "WA" -> "Noto‘g‘ri javob"."""
    return _WORDS.get(code, "Tekshiruvchi xatosi")
