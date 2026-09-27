from django import template

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
