"""The public read-only API (docs/api.md). Every view here shows what an anonymous visitor could already read on the
site's own pages, in JSON; the rules for what stays hidden (drafts, a round's problems before it starts, a marathon's
board before it ends) are the pages' rules."""
import datetime as dt

from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.tiers import RATING_TIERS
from apps.contests.models import Contest, DivisionRange, Participation, division_ranges
from apps.contests.rating import INACTIVE_DAYS
from apps.contests.views import _standings
from apps.problems.models import Problem
from apps.translations.mixin import confirmed_text

from . import serializers as s
from .http import api, page_of, respond

VERSION = "1"
LANGS = ("uz", "en")


def _contests():
    return Contest.objects.filter(is_draft=False).annotate(
        n_participants=Count("participations", distinct=True), n_problems=Count("contest_problems", distinct=True)
    ).prefetch_related("authors")


def _contest_or_404(pk):
    return get_object_or_404(_contests(), pk=pk)


def _lang(request):
    lang = request.GET.get("lang", "")
    return lang if lang in LANGS else None


@api
def index(request):
    base = request.build_absolute_uri("/api/v1/")
    return respond({
        "status": "ok", "name": "CodeArena API", "version": VERSION,
        "endpoints": {name: base + path for name, path in {
            "contests": "contests/", "contest": "contests/{id}/", "standings": "contests/{id}/standings/",
            "clist_standings": "contests/{id}/clist-standings/", "problems": "problems/", "problem": "problems/{slug}/",
            "users": "users/", "user": "users/{username}/", "user_ratings": "users/{username}/ratings/",
            "meta": "meta/"}.items()},
    })


@api
def meta(request):
    """The things the other endpoints refer to: the rating tiers and what each division rates."""
    ranges = division_ranges()
    return respond({
        "status": "ok",
        "tiers": [{"name": name, "color": color, "floor": floor, "ceiling": ceiling}
                  for floor, ceiling, name, color in RATING_TIERS],
        "divisions": [{"number": n, "label": f"Div. {n}", "floor": floor, "ceiling": ceiling,
                       "span": DivisionRange(number=n, floor=floor, ceiling=ceiling).span}
                      for n, (floor, ceiling) in sorted(ranges.items())],
        "contest_rules": {"score": "points, ties broken by penalty", "cf": "Codeforces: points fall with time",
                          "icpc": "ICPC: problems solved, then penalty"},
        "times": "ISO 8601, UTC",
    })


# ---- contests -------------------------------------------------------------------------------------------------

@api
def contest_list(request):
    """?status=upcoming|running|past, ?kind=round|marathon, ?rated=1|0, ?order=start (oldest first; default newest),
    ?start_after= / ?start_before= (ISO dates or datetimes), ?q= (part of the title)."""
    now = timezone.now()
    qs = _contests()
    status = request.GET.get("status", "")
    if status == "upcoming":
        qs = qs.filter(start__gt=now)
    elif status == "running":
        qs = qs.filter(start__lte=now, end__gt=now)
    elif status == "past":
        qs = qs.filter(end__lte=now)
    if request.GET.get("kind") in Contest.Kind.values:
        qs = qs.filter(kind=request.GET["kind"])
    if request.GET.get("rated") in ("0", "1"):
        qs = qs.filter(is_rated=request.GET["rated"] == "1")
    for name, lookup in (("start_after", "start__gte"), ("start_before", "start__lt")):
        moment = _moment(request.GET.get(name, ""))
        if moment:
            qs = qs.filter(**{lookup: moment})
    if q := request.GET.get("q", "").strip()[:100]:
        qs = qs.filter(title__icontains=q)
    qs = qs.order_by("start", "pk") if request.GET.get("order") == "start" else qs.order_by("-start", "-pk")
    return respond(page_of(request, qs, lambda c: s.contest_item(request, c)))


def _moment(text):
    """An ISO date or datetime (a date is its midnight UTC), or None."""
    try:
        moment = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if timezone.is_aware(moment) else moment.replace(tzinfo=dt.timezone.utc)


@api
def contest_detail(request, pk):
    contest = _contest_or_404(pk)
    lang = _lang(request)
    description = (confirmed_text(contest, "description_md", lang) if lang else None) or contest.description_md
    return respond({"status": "ok", "contest": s.contest_detail(request, contest, description)})


def _standings_view(contest):
    """(problems, rows) of the board, empty while the round has not begun or its board is shut."""
    if not s.contest_problems_shown(contest):
        return [], []
    problems = list(contest.contest_problems.select_related("problem").order_by("order", "pk"))
    return problems, _standings(contest, problems)


@api
def standings(request, pk):
    contest = _contest_or_404(pk)
    problems, rows = _standings_view(contest)
    labels = [cp.label for cp in problems]
    body = page_of(request, rows, lambda row: s.standings_row(request, row, labels), default_size=100)
    body |= {"contest": s.contest_item(request, contest), "hidden": s.board_hidden(contest),
             "problems": [s.contest_problem_item(request, cp) for cp in problems]}
    return respond(body)


@api
def clist_standings(request, pk):
    """The whole board in the shape clist's Statistic.get_standings reads: problems by short name, and one row per
    member with `place`, `solving`, `penalty` and `problems[short] = {result, time}`. An ICPC round's `solving` is
    the number solved and results are "+", "+N", "-N"; the other rules' `solving` is the score and a result is the
    points. `place` is null for authors and the disqualified, who stand on the board but have no rank."""
    contest = _contest_or_404(pk)
    base = {"status": "ok", "contest": contest.pk, "contest_status": s.status_of(contest), "rules": contest.type}
    problems, rows = _standings_view(contest)
    if not problems:
        return respond(base | {"hidden": s.board_hidden(contest), "problems": [], "standings": []})
    icpc = contest.type == Contest.Type.ICPC
    labels = [cp.label for cp in problems]
    out = []
    for row in rows:
        results = {}
        for label, c in zip(labels, row["cells"]):
            if c["solved"]:
                result = {"result": c["mark"] if icpc else c["points"], "time": c["time"]}
                if c.get("first"):
                    result["first_ac"] = True
            elif c["wrong"]:
                result = {"result": f"-{c['wrong']}"}
            else:
                continue
            results[label] = result
        user = row["user"]
        item = {"member": user.username, "name": user.get_full_name() or None,
                "place": None if row["author"] or row["disqualified"] else row["rank"],
                "solving": row["solved"] if icpc else row["score"], "penalty": row["penalty"],
                "solved": row["solved"], "problems": results}
        if user.country:
            item["country"] = user.country
        if row["author"] or row["out"]:
            item["out_of_competition"] = True
        if row["participation"].rating_after is not None:
            item["old_rating"] = row["participation"].rating_before
            item["new_rating"] = row["participation"].rating_after
        out.append(item)
    return respond(base | {
        "hidden": False,
        "problems": [{"short": cp.label, "name": cp.problem.title, "url": s.absolute(request, "problems:detail", cp.problem.slug),
                      "full_score": cp.points} for cp in problems],
        "standings": out})


# ---- problems -------------------------------------------------------------------------------------------------

def _public_problems():
    """The problems anyone can open: public, approved, and not held by a round that has not begun."""
    return (Problem.objects.filter(is_public=True, status=Problem.Status.APPROVED)
            .exclude(contests__start__gt=timezone.now()).distinct().prefetch_related("tags"))


@api
def problem_list(request):
    """?difficulty=beginner|easy|medium|hard, ?tag=<name>, ?q=<part of the title>, ?kind=code|sql."""
    qs = _public_problems()
    if request.GET.get("difficulty") in Problem.Difficulty.values:
        qs = qs.filter(difficulty=request.GET["difficulty"])
    if request.GET.get("kind") in Problem.Kind.values:
        qs = qs.filter(kind=request.GET["kind"])
    if tag := request.GET.get("tag", "").strip():
        qs = qs.filter(tags__name=tag)
    if q := request.GET.get("q", "").strip()[:100]:
        qs = qs.filter(title__icontains=q)
    lang = _lang(request)
    return respond(page_of(request, qs.order_by("id"), lambda p: s.problem_item(request, p, lang)))


@api
def problem_detail(request, slug):
    problem = get_object_or_404(_public_problems(), slug=slug)
    return respond({"status": "ok", "problem": s.problem_detail(request, problem, _lang(request))})


# ---- users ----------------------------------------------------------------------------------------------------

def _active_users():
    return User.objects.filter(is_active=True).select_related("club")


def _board():
    """The open rating board (accounts.views.rating): those with a rated contest lately, best rating first."""
    cutoff = timezone.now() - dt.timedelta(days=INACTIVE_DAYS)
    return (_active_users().annotate(last_rated=Max("participations__contest__end",
                                                    filter=Q(participations__rating_after__isnull=False)))
            .filter(last_rated__gte=cutoff).order_by("-rating", "username"))


@api
def user_list(request):
    """The rating board, best first. ?q=<part of the username>, ?country=UZ, ?city=, ?school=."""
    qs = _board()
    everyone = list(qs.values_list("rating", flat=True))
    if q := request.GET.get("q", "").strip()[:50]:
        qs = qs.filter(username__icontains=q)
    if country := request.GET.get("country", "").upper()[:2]:
        qs = qs.filter(country=country)
    if city := request.GET.get("city", "").strip()[:100]:
        qs = qs.filter(location__iexact=city)
    if school := request.GET.get("school", "").strip()[:150]:
        qs = qs.filter(school__icontains=school)
    return respond(page_of(request, qs, lambda u: s.user_item(request, u, rank=sum(1 for r in everyone if r > u.rating) + 1)))


@api
def user_detail(request, username):
    user = get_object_or_404(_active_users(), username=username)
    rated = Participation.objects.filter(user=user, rating_after__isnull=False)
    on_board = _board().filter(pk=user.pk).exists()
    rank = (_board().filter(rating__gt=user.rating).count() + 1) if on_board else None
    best = rated.order_by("-rating_after").values_list("rating_after", flat=True).first()
    solved = Problem.objects.filter(userproblemsolved__user=user, is_public=True).count()
    data = s.user_item(request, user, rank=rank) | {
        "on_board": on_board,
        "max_rating": best,
        "n_rated_contests": rated.count(),
        "n_contests": user.participations.count(),
        "n_solved": solved,
        "ratings_url": request.build_absolute_uri(reverse("api:user_ratings", args=[user.username])),
    }
    return respond({"status": "ok", "user": data})


@api
def user_ratings(request, username):
    """A user's rated contests, oldest first: place, rating before and after."""
    user = get_object_or_404(_active_users(), username=username)
    history = (Participation.objects.filter(user=user, rating_after__isnull=False, rating_before__isnull=False)
               .select_related("contest").order_by("contest__end", "contest_id"))
    return respond(page_of(request, list(history), lambda p: s.rating_change_item(request, p), default_size=100))
