"""What search engines and link previews read in the page head."""
from html import unescape

from django import template
from django.utils.html import strip_tags
from django.utils.text import Truncator

register = template.Library()


@register.filter
def plain(html: str, length: int = 155) -> str:
    """Rendered markdown as one line of text for a meta description (about what a result shows)."""
    return Truncator(" ".join(unescape(strip_tags(html)).split())).chars(length)


@register.simple_tag(takes_context=True)
def canonical_url(context) -> str:
    """This page's address without filters or tracking: the path, plus the page of a plain paginated
    list (a filtered list's page 2 is another list's, so filtered views all point at the list itself)."""
    request = context["request"]
    page = request.GET.get("page", "")
    paged = page.isdigit() and page != "1" and set(request.GET) == {"page"}
    return request.build_absolute_uri(request.path) + (f"?page={page}" if paged else "")
