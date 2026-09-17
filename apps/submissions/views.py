import django_rq
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.contests.services import access_allowed, active_contest_for
from apps.problems.models import Language, Problem
from judge.runner import run_submission

from .models import Submission

MAX_SOURCE = 64 * 1024


@login_required
@require_POST
def submit(request, slug):
    try:
        problem = Problem.objects.get(slug=slug)
    except Problem.DoesNotExist:
        raise Http404
    contest = active_contest_for(request.user, problem)
    if not problem.is_public and contest is None:
        raise Http404
    # re-check supervised-mode eligibility on every submit, not just at
    # registration — group membership or client IP can change mid-contest.
    if contest is not None and not access_allowed(request.user, contest, request.META.get("REMOTE_ADDR")):
        return HttpResponseBadRequest("not eligible for this contest")
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
    subs = Submission.objects.filter(user=request.user).select_related("problem", "language")[:100]
    return render(request, "submissions/list.html", {"subs": subs})
