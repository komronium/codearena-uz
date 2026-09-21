import django_rq
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.contests.models import Participation
from apps.contests.services import access_allowed, active_contest_for, in_upcoming_contest
from apps.problems.models import Language, Problem
from judge.runner import run_submission

from .models import Submission

MAX_SOURCE = 64 * 1024
RATE_LIMIT_MAX = 10       # submissions
RATE_LIMIT_WINDOW_S = 60  # per rolling window


def _rate_limited(user_id) -> bool:
    # ponytail: fixed window, not sliding — a burst can land 2x MAX across a
    # window boundary. Good enough to stop a submit-spam script; swap for a
    # sliding/token-bucket counter if that boundary burst becomes a problem.
    key = f"submit-rl:{user_id}"
    count = cache.get(key)
    if count is None:
        cache.set(key, 1, timeout=RATE_LIMIT_WINDOW_S)
        return False
    if count >= RATE_LIMIT_MAX:
        return True
    cache.incr(key)
    return False


@login_required
@require_POST
def submit(request, slug):
    try:
        problem = Problem.objects.get(slug=slug)
    except Problem.DoesNotExist:
        raise Http404
    contest = active_contest_for(request.user, problem)
    is_owner_or_staff = request.user.is_staff or problem.author_id == request.user.id
    if not is_owner_or_staff and ((not problem.is_public and contest is None) or in_upcoming_contest(problem)):
        raise Http404
    # re-check supervised-mode eligibility on every submit, not just at
    # registration — group membership or client IP can change mid-contest.
    if contest is not None and not access_allowed(request.user, contest, request.META.get("REMOTE_ADDR")):
        return HttpResponseBadRequest("not eligible for this contest")
    if contest is not None and Participation.objects.filter(user=request.user, contest=contest, disqualified=True).exists():
        return HttpResponseBadRequest("disqualified from this contest")
    if _rate_limited(request.user.id):
        return HttpResponse("too many submissions, slow down", status=429)
    language = get_object_or_404(Language, code=request.POST.get("language"), is_active=True)
    source = request.POST.get("source", "")
    if not source.strip() or len(source) > MAX_SOURCE:
        return HttpResponseBadRequest("source empty or too large")
    sub = Submission.objects.create(user=request.user, problem=problem, contest=contest,
                                    language=language, source=source)
    django_rq.enqueue(run_submission, sub.pk)
    return redirect("problems:detail", problem.slug)


def _own(request, pk):
    return get_object_or_404(Submission.objects.select_related("problem", "language"), pk=pk, user=request.user)


def _results_ctx(s):
    results = list(s.results.select_related("testcase"))
    first_fail = next((r for r in results if r.verdict != "AC"), None)
    if first_fail is not None:
        first_fail.index = results.index(first_fail) + 1
    total = s.total or s.problem.testcases.count()
    return {"s": s, "results": results, "first_fail": first_fail,
            "progress": {"done": len(results), "total": total,
                         "pct": int(len(results) * 100 / total) if total else 0}}


@login_required
def detail(request, pk):
    return render(request, "submissions/detail.html", _results_ctx(_own(request, pk)))


@login_required
def status(request, pk):
    return render(request, "submissions/_status.html", _results_ctx(_own(request, pk)))


@login_required
def mine(request):
    qs = Submission.objects.filter(user=request.user).select_related("problem", "language")
    verdict = request.GET.get("verdict", "")
    if verdict in Submission.TERMINAL:
        qs = qs.filter(verdict=verdict)
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    verdicts = [("AC", "AC"), ("WA", "WA"), ("TLE", "TL"), ("MLE", "ML"), ("RE", "RE"), ("CE", "CE")]
    return render(request, "submissions/list.html", {"subs": page, "verdict": verdict, "verdicts": verdicts})
