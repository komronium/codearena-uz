from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Count, Q
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.decorators import staff_required

from .models import Clarification, Contest, Participation
from .services import access_allowed
from .standings import compute_standings


def contest_list(request):
    now = timezone.now()
    contests = Contest.objects.annotate(n_participants=Count("participations")).order_by("-start")
    running = [c for c in contests if c.start <= now < c.end]
    upcoming = sorted((c for c in contests if c.start > now), key=lambda c: c.start)
    ended = [c for c in contests if c.end <= now]
    return render(request, "contests/list.html", {
        "running": running, "upcoming": upcoming, "ended": ended,
        "sections": [
            {"key": "running", "title": "Faol", "dot": "bg-ok", "last_col": "Tugashiga", "items": running},
            {"key": "upcoming", "title": "Kutilmoqda", "dot": "bg-warn", "last_col": "Boshlanishiga", "items": upcoming},
            {"key": "ended", "title": "Tugagan", "dot": "bg-mute", "last_col": "", "items": ended},
        ],
    })


def _standings(contest):
    cache_key = f"contest-standings-{contest.pk}"
    rows = cache.get(cache_key)
    if rows is None:
        rows = compute_standings(contest)
        cache.set(cache_key, rows, 30)
    return rows


def contest_detail(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    problems = list(contest.contest_problems.select_related("problem"))
    registered = (
        request.user.is_authenticated
        and Participation.objects.filter(user=request.user, contest=contest).exists()
    )
    my_row, solved_count = None, {}
    if contest.has_started:
        rows = _standings(contest)
        for i, cp in enumerate(problems):
            solved_count[cp.id] = sum(1 for r in rows if r["cells"][i]["solved"] and not r["disqualified"])
        if request.user.is_authenticated:
            my_row = next((r for r in rows if r["user"].pk == request.user.pk), None)
            for i, cp in enumerate(problems):
                cp.my_cell = my_row["cells"][i] if my_row else None
    for cp in problems:
        cp.solved_count = solved_count.get(cp.id, 0)
    return render(request, "contests/detail.html", {
        "contest": contest, "problems": problems, "registered": registered, "my_row": my_row,
        "n_participants": contest.participations.count(),
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
    rows = _standings(contest)
    problems = list(contest.contest_problems.select_related("problem"))
    me = contest.participations.filter(user=request.user).first() if request.user.is_authenticated else None
    return render(request, "contests/standings.html",
                  {"contest": contest, "rows": rows, "problems": problems, "registered": me is not None,
                   "my_participation": me})


@staff_required
@require_POST
def disqualify(request, pk, user_id):
    """Toggle a participant's disqualification; standings cache is dropped so the
    table reorders immediately."""
    p = get_object_or_404(Participation, contest_id=pk, user_id=user_id)
    p.disqualified = not p.disqualified
    p.disqualified_reason = request.POST.get("reason", "").strip()[:200] if p.disqualified else ""
    p.save(update_fields=["disqualified", "disqualified_reason"])
    cache.delete(f"contest-standings-{pk}")
    if request.POST.get("back") == "report":
        return redirect("integrity:contest_report", pk)
    return redirect("contests:standings", pk=pk)


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


@staff_required
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
