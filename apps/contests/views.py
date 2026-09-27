from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.decorators import staff_required
from apps.submissions.solves import refresh_solves

from apps.integrity import audit

from . import rating, virtual
from .models import Clarification, Contest, Participation, VirtualParticipation
from .services import access_allowed
from .standings import compute_standings


def contest_list(request):
    now = timezone.now()
    contests = Contest.objects.annotate(n_participants=Count("participations")).order_by("-start")
    running = [c for c in contests if c.start <= now < c.end]
    upcoming = sorted((c for c in contests if c.start > now), key=lambda c: c.start)
    ended = Paginator([c for c in contests if c.end <= now], 20).get_page(request.GET.get("page"))
    shown = [*running, *upcoming, *ended]
    mine = {}
    if request.user.is_authenticated:
        mine = {p.contest_id: p for p in Participation.objects.filter(
            user=request.user, contest_id__in=[c.pk for c in shown])}
    for c in shown:
        c.me = mine.get(c.pk)
        c.my_delta = (c.me.rating_after - c.me.rating_before
                      if c.me and c.me.rating_after is not None and c.me.rating_before is not None else None)
    for c in running:
        c.elapsed_pct = round(100 * (now - c.start) / (c.end - c.start))
        c.n_problems = c.contest_problems.count()
        # your place and progress so far, from the same standings the table shows
        row = c.me and next((r for r in _standings(c) if r["user"].pk == request.user.pk), None)
        c.my_rank, c.my_solved = (row["rank"], row["solved"]) if row else (None, None)
    return render(request, "contests/list.html", {"running": running, "upcoming": upcoming, "ended": ended})


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
    me = (Participation.objects.filter(user=request.user, contest=contest).first()
          if request.user.is_authenticated else None)
    registered = me is not None
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
        "my_participation": me,
        "n_participants": contest.participations.count(),
        **_virtual_ctx(request, contest),
    })


def _virtual_ctx(request, contest) -> dict:
    if not (request.user.is_authenticated and contest.has_ended):
        return {}
    vp = VirtualParticipation.objects.filter(user=request.user, contest=contest).first()
    if vp is not None:
        return {"virtual": virtual.virtual_result(vp), "vp": vp}
    return {"can_virtual": not virtual.start_refusal(request.user, contest)}


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
    for i, cp in enumerate(problems):  # column footer-style summary: solved / tried
        cp.n_solved = sum(1 for r in rows if r["cells"][i]["solved"])
        cp.n_tried = sum(1 for r in rows if r["cells"][i]["solved"] or r["cells"][i]["wrong"])
    for cp in problems:
        cp.solve_pct = round(100 * cp.n_solved / len(rows)) if rows else 0
    me = contest.participations.filter(user=request.user).first() if request.user.is_authenticated else None
    return render(request, "contests/standings.html",
                  {"contest": contest, "rows": rows, "problems": problems, "registered": me is not None,
                   "my_participation": me,
                   "me_in_rows": me is not None and any(r["user"].pk == request.user.pk for r in rows)})


@staff_required
@require_POST
def disqualify(request, pk, user_id):
    """Set a participant's disqualification to the POSTed state; standings cache is
    dropped so the table reorders immediately. After publish the user's contest solves
    follow it (a disqualified participant's contest ACs don't count)."""
    # An explicit state, not a toggle: a click from a stale page or a second teacher's
    # tab must not quietly re-qualify someone.
    want = {"1": True, "0": False}.get(request.POST.get("disqualified"))
    if want is None:
        return HttpResponseBadRequest("disqualified must be 0 or 1")
    p = get_object_or_404(Participation.objects.select_related("contest"), contest_id=pk, user_id=user_id)
    if p.disqualified != want:
        p.disqualified = want
        p.disqualified_reason = request.POST.get("reason", "").strip()[:200] if want else ""
        p.save(update_fields=["disqualified", "disqualified_reason"])
        audit.record(request, audit.Action.DISQUALIFY if want else audit.Action.REQUALIFY,
                     contest=p.contest, subject=p.user, note=p.disqualified_reason)
        if p.contest.published_at is not None:
            for problem_id in p.contest.contest_problems.values_list("problem_id", flat=True):
                refresh_solves(problem_id, [p.user_id])
        if p.contest.rating_applied:
            _rerate_after_dq(request, p.contest)
    cache.delete(f"contest-standings-{pk}")
    if request.POST.get("back") == "report":
        return redirect("integrity:contest_report", pk)
    return redirect("contests:standings", pk=pk)


def _rerate_after_dq(request, contest):
    """A DQ moves the participant to last place, which changes everyone's delta. Only the
    latest rated contest can be redone without breaking later rating chains."""
    if rating.is_latest(contest):
        rating.recompute(contest)
        audit.record(request, audit.Action.RATING_RECOMPUTE, contest=contest)
        messages.success(request, "Reyting qayta hisoblandi.")
    else:
        messages.warning(request, "Ishtirokchilar keyinroq boshqa reytingli musobaqada qatnashgan — "
                                  "bu musobaqaning reyting o‘zgarmadi.")


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
        # Titles are secret until the start; before it only general questions are possible.
        "problems": contest.contest_problems.select_related("problem")
        if contest.has_started else [],
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


@login_required
@require_POST
def virtual_start(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    if not contest.has_ended:
        return HttpResponseBadRequest("contest has not ended")
    refusal = virtual.start_refusal(request.user, contest)
    if refusal:
        return HttpResponseBadRequest(refusal)
    VirtualParticipation.objects.create(user=request.user, contest=contest, start=timezone.now())
    return redirect("contests:detail", pk=pk)
