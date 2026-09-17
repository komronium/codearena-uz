import bleach
import markdown
from django.http import Http404
from django.shortcuts import render

from apps.contests.services import active_contest_for

from .models import (
    Language,
    Problem,
)

# Markdown itself passes raw HTML straight through; sanitize the rendered
# output before any template marks it |safe, since statement_md is authored
# by teacher accounts and this is an open-registration platform.
_ALLOWED_TAGS = [
    "p", "br", "strong", "em", "b", "i", "del", "sup", "sub",
    "ul", "ol", "li", "blockquote", "code", "pre", "hr",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "table", "thead", "tbody", "tr", "th", "td",
    "a", "img",
]
_ALLOWED_ATTRS = {
    "a": ["href", "title"],
    "img": ["src", "alt", "title"],
    "code": ["class"],
}


def _render_statement(statement_md: str) -> str:
    html = markdown.markdown(statement_md, extensions=["tables", "fenced_code"])
    return bleach.clean(html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS)


def problem_list(request):
    problems = Problem.objects.filter(is_public=True).order_by("id")
    return render(request, "problems/list.html", {"problems": problems})


def problem_detail(request, slug):
    try:
        problem = Problem.objects.get(slug=slug)
    except Problem.DoesNotExist:
        raise Http404
    if not problem.is_public and active_contest_for(request.user, problem) is None:
        raise Http404
    return render(request, "problems/detail.html", {
        "problem": problem,
        "statement_html": _render_statement(problem.statement_md),
        "languages": Language.objects.filter(is_active=True),
    })
