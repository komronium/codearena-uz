from django import template
from django.utils import dateformat, timezone
from django.utils.html import format_html

register = template.Library()


@register.filter
def compact(n) -> str:
    """A count for a stat tile, in Uzbek: 874, 1,3 ming, 12 ming, 2,4 mln."""
    n = int(n or 0)
    if n < 1000:
        return str(n)
    if n < 1_000_000:
        value, unit = n / 1000, "ming"
    else:
        value, unit = n / 1_000_000, "mln"
    text = f"{value:.1f}" if value < 10 else f"{round(value)}"
    return f"{text.replace('.', ',').removesuffix(',0')} {unit}"


@register.filter
def kplus(n) -> str:
    """A count for a table cell: 874, then 1K+, 12K+, 2M+; the exact number goes in the title."""
    n = int(n or 0)
    if n < 1000:
        return str(n)
    return f"{n // 1000}K+" if n < 1_000_000 else f"{n // 1_000_000}M+"


@register.filter
def signed(n) -> str:
    """A change with its sign, minus as a real minus: +12, −49, 0 (stringformat:"+d" prints a hyphen)."""
    n = int(n or 0)
    return f"+{n}" if n > 0 else f"\u2212{-n}" if n < 0 else "0"


@register.filter
def ztime(value, fmt="d.m.Y H:i") -> str:
    """A server time as <time datetime>, so static/js/localtime.js can add the viewer's own clock when it is not
    UTC+5 (contest times are Tashkent times)."""
    if not value:
        return ""
    return format_html('<time class="ca-zt" datetime="{}">{}</time>', value.isoformat(),
                       dateformat.format(timezone.localtime(value), fmt))
