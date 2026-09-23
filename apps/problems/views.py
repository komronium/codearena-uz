import bleach
import mistune
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Case, Count, F, IntegerField, OuterRef, Q, Subquery, Value, When
from django.db.models.functions import Length
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.utils import timezone

from apps.contests.models import ContestProblem
from apps.contests.services import active_contest_for, in_running_contest, in_upcoming_contest
from apps.submissions.models import Submission, UserProblemSolved

from .models import (
    Language,
    Problem,
    ProblemRating,
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


_markdown = mistune.create_markdown(plugins=["table"])


def _render_statement(statement_md: str) -> str:
    # mistune (not python-markdown): CommonMark-compliant, so a list right after a
    # paragraph with no blank line — as the editor's own live preview renders it —
    # is recognized here too, instead of collapsing into the paragraph's text.
    html = _markdown(statement_md)
    return bleach.clean(html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS)


# Clickable column -> ordering expression. Difficulty sorts by level, not alphabetically.
_DIFFICULTY_RANK = Case(*(When(difficulty=d, then=Value(i)) for i, d in enumerate(Problem.Difficulty.values)),
                        output_field=IntegerField())
_SORTS = {
    "id": F("id"), "title": F("title"), "difficulty": _DIFFICULTY_RANK,
    "attempts": F("attempts"), "pass_rate": F("pass_rate"), "rating": F("avg_stars"),
}

_AVG_STARS = Subquery(ProblemRating.objects.filter(problem=OuterRef("pk")).values("problem")
                      .annotate(a=Avg("stars")).values("a")[:1])
_N_RATINGS = Subquery(ProblemRating.objects.filter(problem=OuterRef("pk")).values("problem")
                      .annotate(n=Count("id")).values("n")[:1])

# Leaderboard metric -> ordering of AC submissions (ties go to whoever got there first).
_LEADER_ORDER = {"time": ("exec_ms", "pk"), "length": ("code_len", "pk")}


def problem_list(request):
    problems = Problem.objects.filter(is_public=True).exclude(contests__start__gt=timezone.now())
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
        avg_stars=_AVG_STARS,
    ).annotate(
        pass_rate=Case(When(attempts=0, then=Value(0)), default=F("ac_count") * 100 / F("attempts"),
                       output_field=IntegerField()),
    ).distinct()
    sort = request.GET.get("sort", "id")
    if sort not in _SORTS:
        sort = "id"
    desc = request.GET.get("dir") == "desc"
    order = _SORTS[sort].desc(nulls_last=True) if desc else _SORTS[sort].asc(nulls_last=True)
    problems = problems.order_by(order, "id")

    page = Paginator(problems, 30).get_page(request.GET.get("page"))
    solved_ids = set()
    if request.user.is_authenticated:
        solved_ids = set(
            UserProblemSolved.objects.filter(user=request.user, problem__in=page.object_list)
            .values_list("problem_id", flat=True)
        )
    return render(request, "problems/list.html", {
        "problems": page,
        "sort": sort, "dir": "desc" if desc else "asc",
        "solved_ids": solved_ids,
        "all_tags": Tag.objects.order_by("name"),
        "q": q,
        "selected_tag": tag,
        "selected_difficulty": difficulty,
        "selected_status": status,
        "difficulties": Problem.Difficulty.choices,
    })


def _visible_problem(request, slug):
    """(problem, running contest the user is in or None); 404 when the user may not see it."""
    try:
        problem = (Problem.objects.select_related("author").prefetch_related("tags")
                   .annotate(avg_stars=_AVG_STARS, n_ratings=_N_RATINGS).get(slug=slug))
    except Problem.DoesNotExist:
        raise Http404
    contest = active_contest_for(request.user, problem)
    is_owner_or_staff = request.user.is_authenticated and (
        request.user.is_staff or problem.author_id == request.user.id
    )
    if not is_owner_or_staff and ((not problem.is_public and contest is None) or in_upcoming_contest(problem)):
        raise Http404
    return problem, contest


def leaders(problem, by: str, lang: str = "", limit: int = 20) -> list:
    """Best AC submission per user by `by` ("time" | "length"), optionally for one language."""
    qs = (Submission.objects.filter(problem=problem, verdict="AC")
          .select_related("user", "language").annotate(code_len=Length("source"))
          .defer("source", "compile_log").order_by(*_LEADER_ORDER[by]))
    if lang:
        qs = qs.filter(language__code=lang)
    # ponytail: dedupe per user in Python; scans AC rows until `limit` users — fine for thousands of ACs.
    best, seen = [], set()
    for s in qs.iterator(chunk_size=500):
        if s.user_id in seen:
            continue
        seen.add(s.user_id)
        best.append(s)
        if len(best) == limit:
            break
    return best


def problem_detail(request, slug):
    problem, contest = _visible_problem(request, slug)
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
    solved = request.user.is_authenticated and UserProblemSolved.objects.filter(
        user=request.user, problem=problem).exists()
    show_leaders = contest is None and not in_running_contest(problem)
    my_stars = (ProblemRating.objects.filter(user=request.user, problem=problem).values_list("stars", flat=True).first()
                if solved else None)
    return render(request, "problems/detail.html", {
        "solved": solved,
        "my_stars": my_stars,
        "star_range": range(1, 6),
        "fastest": leaders(problem, "time", limit=3) if show_leaders else [],
        "shortest": leaders(problem, "length", limit=3) if show_leaders else [],
        "show_leaders": show_leaders,
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


def problem_leaders(request, slug):
    problem, contest = _visible_problem(request, slug)
    if contest is not None or in_running_contest(problem):
        raise Http404  # solutions stay hidden while a contest with this problem runs
    by = request.GET.get("by") if request.GET.get("by") in _LEADER_ORDER else "time"
    languages = Language.objects.filter(is_active=True, submission__problem=problem,
                                        submission__verdict="AC").distinct().order_by("name")
    lang = request.GET.get("lang", "")
    if lang not in {lg.code for lg in languages}:
        lang = ""
    solved = request.user.is_authenticated and UserProblemSolved.objects.filter(
        user=request.user, problem=problem).exists()
    return render(request, "problems/leaders.html", {
        "problem": problem, "by": by, "lang": lang, "languages": languages,
        "rows": leaders(problem, by, lang, limit=50),
        "can_view_code": solved or request.user.is_staff,
    })


@login_required
@require_POST
def rate_problem(request, slug):
    problem, _contest = _visible_problem(request, slug)
    if not UserProblemSolved.objects.filter(user=request.user, problem=problem).exists():
        raise Http404  # only solvers rate — keeps the score about the problem, not about frustration
    try:
        stars = int(request.POST.get("stars", ""))
    except ValueError:
        stars = 0
    if 1 <= stars <= 5:
        ProblemRating.objects.update_or_create(user=request.user, problem=problem, defaults={"stars": stars})
    return redirect(reverse("problems:detail", args=[problem.slug]) + "#baho")
