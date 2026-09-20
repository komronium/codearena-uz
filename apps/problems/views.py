import bleach
import markdown
from django.http import Http404
from django.shortcuts import render

from apps.contests.services import active_contest_for
from apps.submissions.models import UserProblemSolved

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
    solved_ids = set()
    if request.user.is_authenticated:
        solved_ids = set(
            UserProblemSolved.objects.filter(user=request.user, problem__in=problems)
            .values_list("problem_id", flat=True)
        )
    return render(request, "problems/list.html", {"problems": problems, "solved_ids": solved_ids})


def problem_detail(request, slug):
    try:
        problem = Problem.objects.get(slug=slug)
    except Problem.DoesNotExist:
        raise Http404
    contest = active_contest_for(request.user, problem)
    is_owner_or_staff = request.user.is_authenticated and (
        request.user.is_staff or problem.author_id == request.user.id
    )
    if not problem.is_public and contest is None and not is_owner_or_staff:
        raise Http404
    if problem.kind == Problem.Kind.SQL:
        languages = Language.objects.filter(is_active=True, code="sql")
    else:
        languages = Language.objects.filter(is_active=True).exclude(code="sql")
    return render(request, "problems/detail.html", {
        "problem": problem,
        "statement_html": _render_statement(problem.statement_md),
        "languages": languages,
        "sql_dataset": getattr(problem, "sql_dataset", None),
        "contest": contest,
    })
