import bleach
import mistune
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import (
    Avg,
    Case,
    Count,
    F,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Coalesce, Length
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.classroom.duels import active_duel_for
from apps.contests.models import ContestProblem, VoidedProblem
from apps.contests.services import (
    active_contest_for,
    in_running_contest,
    in_upcoming_contest,
)
from apps.learn.models import StudyPlan
from apps.learn.progress import plan_nav, plan_progress, save_menu
from apps.submissions.models import Submission, UserProblemSolved
from judge import sql_judge

from .daily import daily_for, streaks
from .progress import level_progress as levels_of, solved_ring
from .models import (
    DailySolve,
    HintUnlock,
    Language,
    Problem,
    ProblemRating,
    Tag,
)
from .skills import next_problems, shared_reason

# Markdown itself passes raw HTML straight through; sanitize the rendered
# output before any template marks it |safe, since statement_md is authored
# by teacher accounts and this is an open-registration platform.
_ALLOWED_TAGS = [
    "p",
    "br",
    "strong",
    "em",
    "b",
    "i",
    "del",
    "sup",
    "sub",
    "ul",
    "ol",
    "li",
    "blockquote",
    "code",
    "pre",
    "hr",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "a",
    "img",
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


# Clickable column -> ordering expression. Difficulty is the problem's rating (difficulty.py).
_SORTS = {
    "id": F("id"),
    "title": F("title"),
    "difficulty": F("rating"),
    "attempts": F("attempts"),
    "solvers": F("solvers"),
    "rating": F("avg_stars"),
}

# How many people solved it (one UserProblemSolved row each): the count Codeforces prints.
_SOLVERS = Coalesce(
    Subquery(
        UserProblemSolved.objects.filter(problem=OuterRef("pk"))
        .values("problem")
        .annotate(n=Count("id"))
        .values("n")[:1]
    ),
    0,
)

_AVG_STARS = Subquery(
    ProblemRating.objects.filter(problem=OuterRef("pk"))
    .values("problem")
    .annotate(a=Avg("stars"))
    .values("a")[:1]
)
_N_RATINGS = Subquery(
    ProblemRating.objects.filter(problem=OuterRef("pk"))
    .values("problem")
    .annotate(n=Count("id"))
    .values("n")[:1]
)

# Leaderboard metric -> ordering of AC submissions (ties go to whoever got there first).
_LEADER_ORDER = {"time": ("exec_ms", "pk"), "length": ("code_len", "pk")}


def suggest(request):
    """Instant search for the command palette: up to 8 of the problems the list would show,
    title-prefix and number matches first. Never more than the list reveals."""
    q = request.GET.get("q", "").strip()[:60]
    if not q:
        return JsonResponse({"results": []})
    visible = (
        Problem.objects.filter(is_public=True)
        .exclude(contests__start__gt=timezone.now())
        .distinct()
    )
    match = Q(title__icontains=q) | Q(slug__icontains=q.replace(" ", "-"))
    if q.lstrip("#").isdigit():
        match |= Q(pk=int(q.lstrip("#")))
    rows = list(
        visible.filter(match)
        .annotate(
            rank=Case(
                When(
                    pk=int(q.lstrip("#")) if q.lstrip("#").isdigit() else -1,
                    then=Value(0),
                ),
                When(title__istartswith=q, then=Value(1)),
                default=Value(2),
                output_field=IntegerField(),
            ),
        )
        .order_by("rank", "id")
        .values("id", "slug", "title", "difficulty")[:8]
    )
    solved = set()
    if request.user.is_authenticated and rows:
        solved = set(
            UserProblemSolved.objects.filter(
                user=request.user, problem_id__in=[r["id"] for r in rows]
            ).values_list("problem_id", flat=True)
        )
    labels = dict(Problem.Difficulty.choices)
    return JsonResponse(
        {
            "results": [
                {
                    "title": r["title"],
                    "url": reverse("problems:detail", args=[r["slug"]]),
                    "id": r["id"],
                    "difficulty": r["difficulty"],
                    "difficulty_label": labels.get(r["difficulty"], ""),
                    "solved": r["id"] in solved,
                }
                for r in rows
            ]
        }
    )


def _random_pick(request, problems, status):
    """ "Tasodifiy masala": one from what the filters leave, not yet solved (unless the
    solved ones were asked for), outside a running contest."""
    pool = problems.exclude(contests__end__gt=timezone.now())
    if request.user.is_authenticated and status != "solved":
        pool = pool.exclude(userproblemsolved__user=request.user)
    slug = pool.order_by("?").values_list("slug", flat=True).first()
    if slug:
        return redirect("problems:detail", slug)
    messages.info(request, "Bu filtrda yechilmagan masala qolmadi.")
    params = request.GET.copy()
    params.pop("random")
    return redirect(f"{reverse('problems:list')}?{params.urlencode()}")


def problem_list(request):
    visible = Problem.objects.filter(is_public=True).exclude(
        contests__start__gt=timezone.now()
    )
    problems = visible
    q = request.GET.get("q", "").strip()
    if q:
        problems = problems.filter(title__icontains=q)
    tag = request.GET.get("tag", "").strip()
    if tag:
        problems = problems.filter(tags__name=tag)
    kind = request.GET.get("kind", "").strip()
    if kind in Problem.Kind.values:
        problems = problems.filter(kind=kind)
    else:
        kind = ""
    status = request.GET.get("status", "").strip()
    if status in ("solved", "unsolved") and request.user.is_authenticated:
        solved_q = Q(userproblemsolved__user=request.user)
        problems = (
            problems.filter(solved_q)
            if status == "solved"
            else problems.exclude(solved_q)
        )
    # the difficulty chips count what the other filters leave, so each number is what a click shows
    by_level = dict(
        problems.order_by()
        .values("difficulty")
        .annotate(n=Count("id", distinct=True))
        .values_list("difficulty", "n")
    )
    level_chips = [
        {"value": v, "label": lbl, "n": by_level.get(v, 0)}
        for v, lbl in Problem.Difficulty.choices
    ]
    difficulty = request.GET.get("difficulty", "").strip()
    if difficulty in Problem.Difficulty.values:
        problems = problems.filter(difficulty=difficulty)
    if "random" in request.GET:
        return _random_pick(request, problems, status)
    problems = (
        problems.prefetch_related("tags")
        .annotate(
            attempts=Count("submissions", distinct=True),
            ac_count=Count(
                "submissions", filter=Q(submissions__verdict="AC"), distinct=True
            ),
            avg_stars=_AVG_STARS,
            solvers=_SOLVERS,
        )
        .distinct()
    )
    sort = request.GET.get("sort", "id")
    if sort not in _SORTS:
        sort = "id"
    desc = request.GET.get("dir") == "desc"
    order = (
        _SORTS[sort].desc(nulls_last=True)
        if desc
        else _SORTS[sort].asc(nulls_last=True)
    )
    problems = problems.order_by(order, "id")

    page = Paginator(problems, 30).get_page(request.GET.get("page"))
    solved_ids, tried_ids = set(), set()
    if request.user.is_authenticated:
        solved_ids = set(
            UserProblemSolved.objects.filter(
                user=request.user, problem__in=page.object_list
            ).values_list("problem_id", flat=True)
        )
        # tried and not solved yet: the row's mark is a ring instead of a tick
        tried_ids = set(
            Submission.objects.filter(user=request.user, problem__in=page.object_list)
            .values_list("problem_id", flat=True)
        ) - solved_ids
    # Only on the plain first page: with a search or filter the user already knows what they want.
    browsing = not (q or tag or difficulty or status or kind) and page.number == 1
    daily = daily_for() if browsing else None
    daily_done = streak = None
    if daily and request.user.is_authenticated:
        daily_done = DailySolve.objects.filter(user=request.user, daily=daily).exists()
        streak = streaks(request.user)[0]
    next_picks = (
        next_problems(request.user, exclude=(daily.problem_id,) if daily else ())
        if request.user.is_authenticated and browsing
        else []
    )
    total = visible.distinct().count()
    all_tags = list(Tag.objects.filter(problem__in=visible).distinct().order_by("name"))
    # the topics row: the biggest topics with their counts, the rest behind "Hammasi"
    topics = list(Tag.objects.filter(problem__in=visible).annotate(n=Count("problem", distinct=True))
                  .order_by("-n", "name"))
    # the courses on top, only while browsing: a way in for whoever does not know what to solve
    plans = []
    if browsing:
        plans = list(StudyPlan.objects.filter(is_public=True).order_by("order", "pk")[:3])
        progress_by_plan = plan_progress(request.user, plans) if request.user.is_authenticated else {}
        for plan in plans:
            plan.progress = progress_by_plan.get(plan.pk)
    progress = level_progress = None
    if request.user.is_authenticated:
        progress = {
            "done": UserProblemSolved.objects.filter(
                user=request.user, problem__in=visible
            ).count(),
            "total": total,
        }
        # the side card: solved out of open, per level (whatever the filters above say)
        level_progress = levels_of(request.user, visible)
    return render(
        request,
        "problems/list.html",
        {
            "problems": page,
            "progress": progress,
            "level_progress": level_progress,
            "ring": solved_ring(level_progress) if level_progress else None,
            "top_topics": topics[:8],
            "more_topics": topics[8:],
            "plans": plans,
            "tried_ids": tried_ids,
            "total": total,
            "level_chips": level_chips,
            "level_total": sum(by_level.values()),
            "any_rated": any(p.avg_stars for p in page),
            "next_picks": next_picks,
            "picks_reason": shared_reason(next_picks),
            "daily": daily,
            "daily_done": daily_done,
            "streak": streak,
            "sort": sort,
            "dir": "desc" if desc else "asc",
            "solved_ids": solved_ids,
            # each kind's topics in its own group; with a kind picked, only that kind's
            "tag_groups": [
                (label, [t for t in all_tags if t.kind == value])
                for value, label in Tag.Kind.choices
                if not kind or value == kind
            ],
            "q": q,
            "selected_tag": tag,
            "selected_difficulty": difficulty,
            "selected_status": status,
            "selected_kind": kind,
            "kinds": Problem.Kind.choices,
            "difficulties": Problem.Difficulty.choices,
        },
    )


def _visible_problem(request, slug):
    """(problem, running contest the user is in or None); 404 when the user may not see it."""
    try:
        problem = (
            Problem.objects.select_related("author")
            .prefetch_related("tags")
            .annotate(avg_stars=_AVG_STARS, n_ratings=_N_RATINGS)
            .get(slug=slug)
        )
    except Problem.DoesNotExist:
        raise Http404
    contest = active_contest_for(request.user, problem)
    is_owner_or_staff = request.user.is_authenticated and (
        request.user.is_staff or problem.author_id == request.user.id
    )
    if not is_owner_or_staff and (
        (not problem.is_public and contest is None) or in_upcoming_contest(problem)
    ):
        raise Http404
    return problem, contest


def leaders(problem, by: str, lang: str = "", limit: int = 20) -> list:
    """Best AC submission per user by `by` ("time" | "length"), optionally for one language."""
    qs = (
        Submission.objects.filter(problem=problem, verdict="AC")
        .select_related("user", "language")
        .annotate(code_len=Length("source"))
        .defer("source", "compile_log")
        .order_by(*_LEADER_ORDER[by])
    )
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


def _sql_context(problem) -> dict:
    """A SQL problem's sample tables and expected result, drawn as tables on its page."""
    dataset = (
        getattr(problem, "sql_dataset", None)
        if problem.kind == Problem.Kind.SQL
        else None
    )
    if dataset is None:
        return {}
    try:
        tables = sql_judge.tables(dataset.schema_sql, dataset.seed_sql)
    except sql_judge.SQLJudgeError:
        tables = []  # an authoring bug; the raw schema below still shows what's there
    return {
        "sql_dataset": dataset,
        "sql_tables": tables,
        "sql_expected": sql_judge.parse_rows(dataset.expected_result),
    }


def _problem_stats(problem) -> dict:
    """LeetCode's line under a statement: judged submissions, how many were accepted, the share accepted."""
    agg = Submission.objects.filter(problem=problem, verdict__in=Submission.TERMINAL).aggregate(
        total=Count("id"), accepted=Count("id", filter=Q(verdict="AC")))
    total, accepted = agg["total"], agg["accepted"]
    return {"total": total, "accepted": accepted, "rate": 100 * accepted / total if total else None}


def problem_detail(request, slug):
    problem, contest = _visible_problem(request, slug)
    if problem.kind == Problem.Kind.SQL:
        languages = Language.objects.filter(is_active=True, code="sql")
    else:
        languages = Language.objects.filter(is_active=True).exclude(code="sql")
    my_subs = []
    if request.user.is_authenticated:
        subs = Submission.objects.filter(user=request.user, problem=problem)
        if contest is not None:
            subs = subs.filter(contest=contest)  # in a contest, only what counts for it
        my_subs = list(subs.select_related("language")[:5])
    # Running contest that has this problem but the user hasn't joined: solving now
    # would count as practice, not for the standings — tell them before they submit.
    open_contest = None
    if contest is None and request.user.is_authenticated:
        now = timezone.now()
        cp = (
            ContestProblem.objects.filter(
                problem=problem, contest__start__lte=now, contest__end__gt=now
            )
            .select_related("contest")
            .first()
        )
        open_contest = cp.contest if cp else None
    public = Problem.objects.filter(is_public=True).exclude(
        contests__start__gt=timezone.now()
    )
    solved = (
        request.user.is_authenticated
        and UserProblemSolved.objects.filter(
            user=request.user, problem=problem
        ).exists()
    )
    show_leaders = contest is None and not in_running_contest(problem)
    # Hints and the editorial stay shut while a contest uses the problem.
    duel = active_duel_for(request.user, problem)
    help_locked = (
        "Duel davomida yopiq"
        if duel is not None
        else "Musobaqa davomida yopiq"
        if not show_leaders
        else ""
    )
    hints = list(problem.hints.all())
    opened = set()
    if request.user.is_authenticated and hints:
        opened = set(
            HintUnlock.objects.filter(
                user=request.user, hint__problem=problem
            ).values_list("hint_id", flat=True)
        )
    for i, h in enumerate(hints):
        h.opened = h.pk in opened and not help_locked
        h.html = _render_statement(h.body_md) if h.opened else ""
        h.can_open = (
            not help_locked and not h.opened and all(x.pk in opened for x in hints[:i])
        )
    editorial_open = (
        bool(problem.editorial_md)
        and not help_locked
        and (
            solved
            or (
                request.user.is_authenticated
                and (request.user.is_staff or problem.author_id == request.user.id)
            )
        )
    )
    my_stars = (
        ProblemRating.objects.filter(user=request.user, problem=problem)
        .values_list("stars", flat=True)
        .first()
        if solved
        else None
    )
    # AI penalty (a struck contest result): the problem is blocked for this
    # participant until the round ends — say so and lock the submit bar.
    contest_blocked = (
        request.user.is_authenticated
        and contest is not None
        and VoidedProblem.objects.filter(
            participation__user=request.user, participation__contest=contest,
            contest_problem__problem=problem, penalty=True
        ).exists()
    )
    from apps.integrity.models import PracticeReview

    # "void": a teacher found it copied; "held": flagged strongly, points wait for a teacher
    review = (
        PracticeReview.objects.filter(
            user=request.user, problem=problem, confirmed=True
        ).first()
        if solved
        else None
    )
    voided = review and ("void" if review.reviewer_id else "held")
    return render(
        request,
        "problems/detail.html",
        {
            "plan_nav": plan_nav(
                request.user, request.GET.get("plan", "")[:50], problem.pk
            )
            if contest is None
            else None,
            "save_lists": save_menu(request.user, problem)
            if contest is None and duel is None
            else None,
            "solved": solved,
            "voided": voided,
            "my_stars": my_stars,
            "star_range": range(1, 6),
            "fastest": leaders(problem, "time", limit=3) if show_leaders else [],
            "shortest": leaders(problem, "length", limit=3) if show_leaders else [],
            "show_leaders": show_leaders,
            "hints": hints,
            "duel": duel,
            "help_locked": help_locked,
            "editorial_html": _render_statement(problem.editorial_md)
            if editorial_open
            else "",
            "open_contest": open_contest,
            "contest_blocked": contest_blocked,
            "problem": problem,
            "my_subs": my_subs,
            "stats": _problem_stats(problem) if contest is None else None,
            "prev_problem": public.filter(id__lt=problem.id).order_by("-id").first(),
            "next_problem": public.filter(id__gt=problem.id).order_by("id").first(),
            "statement_html": _render_statement(problem.statement_md),
            "input_html": _render_statement(problem.input_md)
            if problem.input_md
            else "",
            "output_html": _render_statement(problem.output_md)
            if problem.output_md
            else "",
            "contest_problem": contest.contest_problems.filter(problem=problem).first()
            if contest
            else None,
            "contest_problems": (
                list(
                    contest.contest_problems.select_related("problem").order_by("label")
                )
                if contest
                else []
            ),
            "languages": languages,
            **_sql_context(problem),
            "contest": contest,
            "my_participation": (
                contest.participations.filter(user=request.user).first()
                if contest and request.user.is_authenticated
                else None
            ),
        },
    )


def problem_leaders(request, slug):
    problem, contest = _visible_problem(request, slug)
    if contest is not None or in_running_contest(problem):
        raise Http404  # solutions stay hidden while a contest with this problem runs
    by = request.GET.get("by") if request.GET.get("by") in _LEADER_ORDER else "time"
    languages = (
        Language.objects.filter(
            is_active=True, submission__problem=problem, submission__verdict="AC"
        )
        .distinct()
        .order_by("name")
    )
    lang = request.GET.get("lang", "")
    if lang not in {lg.code for lg in languages}:
        lang = ""
    solved = (
        request.user.is_authenticated
        and UserProblemSolved.objects.filter(
            user=request.user, problem=problem
        ).exists()
    )
    return render(
        request,
        "problems/leaders.html",
        {
            "problem": problem,
            "by": by,
            "lang": lang,
            "languages": languages,
            "rows": leaders(problem, by, lang, limit=50),
            "can_view_code": solved or request.user.is_staff,
        },
    )


@login_required
@require_POST
def rate_problem(request, slug):
    problem, _contest = _visible_problem(request, slug)
    if not UserProblemSolved.objects.filter(
        user=request.user, problem=problem
    ).exists():
        raise Http404  # only solvers rate — keeps the score about the problem, not about frustration
    try:
        stars = int(request.POST.get("stars", ""))
    except ValueError:
        stars = 0
    if 1 <= stars <= 5:
        ProblemRating.objects.update_or_create(
            user=request.user, problem=problem, defaults={"stars": stars}
        )
    return redirect(reverse("problems:detail", args=[problem.slug]) + "#baho")


@login_required
@require_POST
def hint_unlock(request, slug, hint_id):
    """Open one hint, in order. Its cost is settled when the user's AC lands
    (apps.submissions.solves): a hint opened after solving is free."""
    problem, contest = _visible_problem(request, slug)
    if (
        contest is not None
        or in_running_contest(problem)
        or in_upcoming_contest(problem)
    ):
        return HttpResponseBadRequest(
            "hints are locked while a contest uses this problem"
        )
    if active_duel_for(request.user, problem) is not None:
        return HttpResponseBadRequest(
            "hints are locked during your duel on this problem"
        )
    hints = list(problem.hints.all())
    hint = next((h for h in hints if h.pk == hint_id), None)
    if hint is None:
        raise Http404
    opened = set(
        HintUnlock.objects.filter(user=request.user, hint__problem=problem).values_list(
            "hint_id", flat=True
        )
    )
    if any(h.pk not in opened for h in hints[: hints.index(hint)]):
        return HttpResponseBadRequest("open the earlier hints first")
    HintUnlock.objects.get_or_create(user=request.user, hint=hint)
    return redirect(
        reverse("problems:detail", args=[problem.slug]) + f"#hint-{hint.pk}"
    )
