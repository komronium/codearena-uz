from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Q
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Clarification, Contest, Participation
from .services import access_allowed
from .standings import compute_standings


def contest_list(request):
    contests = Contest.objects.order_by("-start")
    return render(request, "contests/list.html", {"contests": contests})


def contest_detail(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    problems = contest.contest_problems.select_related("problem")
    registered = (
        request.user.is_authenticated
        and Participation.objects.filter(user=request.user, contest=contest).exists()
    )
    return render(request, "contests/detail.html", {
        "contest": contest, "problems": problems, "registered": registered,
    })


@login_required
@require_POST
def register(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    if contest.has_ended:
        return HttpResponseBadRequest("contest has ended")
    if not access_allowed(request.user, contest, request.META.get("REMOTE_ADDR")):
        return HttpResponseBadRequest("not eligible for this contest")
    Participation.objects.get_or_create(user=request.user, contest=contest)
    return redirect("contests:detail", pk=pk)


def standings(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    cache_key = f"contest-standings-{pk}"
    rows = cache.get(cache_key)
    if rows is None:
        rows = compute_standings(contest)
        cache.set(cache_key, rows, 30)
    return render(request, "contests/standings.html", {"contest": contest, "rows": rows})


@login_required
def clarifications(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    registered = Participation.objects.filter(user=request.user, contest=contest).exists()
    if not registered and not request.user.is_staff:
        raise Http404
    qs = contest.clarifications.select_related("user", "problem__problem", "answered_by")
    if not request.user.is_staff:
        qs = qs.filter(Q(answered_at__isnull=False) | Q(user=request.user))
    return render(request, "contests/clarifications.html", {
        "contest": contest,
        "clars": qs,
        "problems": contest.contest_problems.select_related("problem"),
    })


@login_required
@require_POST
def ask_clarification(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    if not Participation.objects.filter(user=request.user, contest=contest).exists():
        return HttpResponseBadRequest("not registered")
    if contest.has_ended:
        return HttpResponseBadRequest("contest has ended")
    question = request.POST.get("question", "").strip()
    if not question or len(question) > 2000:
        return HttpResponseBadRequest("question empty or too long")
    Clarification.objects.create(
        contest=contest, problem_id=request.POST.get("problem_id") or None,
        user=request.user, question=question)
    return redirect("contests:clarifications", pk=pk)


@staff_member_required
@require_POST
def answer_clarification(request, pk, cid):
    clar = get_object_or_404(Clarification, pk=cid, contest_id=pk)
    answer = request.POST.get("answer", "").strip()
    if not answer:
        return HttpResponseBadRequest("answer empty")
    clar.answer = answer
    clar.answered_by = request.user
    clar.answered_at = timezone.now()
    clar.save(update_fields=["answer", "answered_by", "answered_at"])
    return redirect("contests:clarifications", pk=pk)
