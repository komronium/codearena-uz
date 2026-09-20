import django_rq
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.contests.services import access_allowed, active_contest_for
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
    if not problem.is_public and contest is None and not is_owner_or_staff:
        raise Http404
    # re-check supervised-mode eligibility on every submit, not just at
    # registration — group membership or client IP can change mid-contest.
    if contest is not None and not access_allowed(request.user, contest, request.META.get("REMOTE_ADDR")):
        return HttpResponseBadRequest("not eligible for this contest")
    if _rate_limited(request.user.id):
        return HttpResponse("too many submissions, slow down", status=429)
    language = get_object_or_404(Language, code=request.POST.get("language"), is_active=True)
    source = request.POST.get("source", "")
    if not source.strip() or len(source) > MAX_SOURCE:
        return HttpResponseBadRequest("source empty or too large")
    sub = Submission.objects.create(user=request.user, problem=problem, contest=contest,
                                    language=language, source=source)
    django_rq.enqueue(run_submission, sub.pk)
    return redirect("submissions:detail", sub.pk)


def _own(request, pk):
    return get_object_or_404(Submission.objects.select_related("problem", "language"), pk=pk, user=request.user)


@login_required
def detail(request, pk):
    return render(request, "submissions/detail.html", {"s": _own(request, pk)})


@login_required
def status(request, pk):
    s = _own(request, pk)
    return render(request, "submissions/_status.html", {"s": s, "results": s.results.select_related("testcase")})


@login_required
def mine(request):
    qs = Submission.objects.filter(user=request.user).select_related("problem", "language")
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    return render(request, "submissions/list.html", {"subs": page})
