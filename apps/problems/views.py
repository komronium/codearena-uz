import bleach
import markdown
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone

from apps.contests.models import ContestProblem
from apps.contests.services import active_contest_for, in_upcoming_contest
from apps.submissions.models import Submission, UserProblemSolved

from .models import (
    Language,
    Problem,
    Tag,
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
    problems = Problem.objects.filter(is_public=True).exclude(contests__start__gt=timezone.now()).order_by("id")
    q = request.GET.get("q", "").strip()
    if q:
        problems = problems.filter(title__icontains=q)
    tag = request.GET.get("tag", "").strip()
    if tag:
        problems = problems.filter(tags__name=tag)
    difficulty = request.GET.get("difficulty", "").strip()
    if difficulty in Problem.Difficulty.values:
        problems = problems.filter(difficulty=difficulty)
    status = request.GET.get("status", "").strip()
    if status in ("solved", "unsolved") and request.user.is_authenticated:
        solved_q = Q(userproblemsolved__user=request.user)
        problems = problems.filter(solved_q) if status == "solved" else problems.exclude(solved_q)
    problems = problems.prefetch_related("tags").annotate(
        attempts=Count("submissions", distinct=True),
        ac_count=Count("submissions", filter=Q(submissions__verdict="AC"), distinct=True),
    ).distinct()

    page = Paginator(problems, 30).get_page(request.GET.get("page"))
    solved_ids = set()
    if request.user.is_authenticated:
        solved_ids = set(
            UserProblemSolved.objects.filter(user=request.user, problem__in=page.object_list)
            .values_list("problem_id", flat=True)
        )
    for p in page.object_list:
        p.pass_rate = round(p.ac_count / p.attempts * 100) if p.attempts else 0
    return render(request, "problems/list.html", {
        "problems": page,
        "solved_ids": solved_ids,
        "all_tags": Tag.objects.order_by("name"),
        "q": q,
        "selected_tag": tag,
        "selected_difficulty": difficulty,
        "selected_status": status,
        "difficulties": Problem.Difficulty.choices,
    })


def problem_detail(request, slug):
    try:
        problem = Problem.objects.select_related("author").prefetch_related("tags").get(slug=slug)
    except Problem.DoesNotExist:
        raise Http404
    contest = active_contest_for(request.user, problem)
    is_owner_or_staff = request.user.is_authenticated and (
        request.user.is_staff or problem.author_id == request.user.id
    )
    if not is_owner_or_staff and ((not problem.is_public and contest is None) or in_upcoming_contest(problem)):
        raise Http404
    if problem.kind == Problem.Kind.SQL:
        languages = Language.objects.filter(is_active=True, code="sql")
    else:
        languages = Language.objects.filter(is_active=True).exclude(code="sql")
    my_subs = []
    if request.user.is_authenticated:
        my_subs = list(Submission.objects.filter(user=request.user, problem=problem)
                       .select_related("language")[:5])
    # Running contest that has this problem but the user hasn't joined: solving now
    # would count as practice, not for the standings — tell them before they submit.
    open_contest = None
    if contest is None and request.user.is_authenticated:
        now = timezone.now()
        cp = (ContestProblem.objects.filter(problem=problem, contest__start__lte=now, contest__end__gt=now)
              .select_related("contest").first())
        open_contest = cp.contest if cp else None
    public = Problem.objects.filter(is_public=True).exclude(contests__start__gt=timezone.now())
    return render(request, "problems/detail.html", {
        "open_contest": open_contest,
        "problem": problem,
        "my_subs": my_subs,
        "prev_problem": public.filter(id__lt=problem.id).order_by("-id").first(),
        "next_problem": public.filter(id__gt=problem.id).order_by("id").first(),
        "statement_html": _render_statement(problem.statement_md),
        "input_html": _render_statement(problem.input_md) if problem.input_md else "",
        "output_html": _render_statement(problem.output_md) if problem.output_md else "",
        "contest_problem": contest.contest_problems.filter(problem=problem).first() if contest else None,
        "languages": languages,
        "sql_dataset": getattr(problem, "sql_dataset", None),
        "contest": contest,
    })
