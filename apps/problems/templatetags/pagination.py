from django import template

register = template.Library()


@register.filter
def elided_pages(page):
    """1 … 4 5 [6] 7 8 … 20 — Paginator.ELLIPSIS marks the gaps."""
    return page.paginator.get_elided_page_range(page.number, on_each_side=2, on_ends=1)
