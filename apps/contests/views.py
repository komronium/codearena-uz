from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count, Q
import datetime as dt

from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.accounts.decorators import staff_required
from apps.problems.views import _render_statement
from apps.submissions.models import VERDICT_LABELS, Submission
from apps.submissions.solves import refresh_solves

from apps.integrity import audit

from . import rating, virtual
from .models import Clarification, Contest, ContestProblem, Participation, VirtualParticipation, VoidedProblem
from .services import access_allowed
from .standings import compute_standings, elapsed, problem_points


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
    # the sidebar's top ten, from the rating page's pool: users with a finished rated contest
    pool = get_user_model().objects.filter(is_active=True, participations__rating_after__isnull=False).distinct()
    top_rated = pool.order_by("-rating", "username")[:10]
    # the cover's numbers: your rating, your place in that same pool, the rounds you finished
    me = None
    if request.user.is_authenticated:
        rated = pool.filter(pk=request.user.pk).exists()
        me = {"rating": request.user.rating, "rated": rated,
              "place": pool.filter(rating__gt=request.user.rating).count() + 1 if rated else None,
              "pool": pool.count(),
              "attended": Participation.objects.filter(user=request.user, contest__end__lte=now).count()}
    return render(request, "contests/list.html", {"running": running, "upcoming": upcoming, "ended": ended,
                                                  "next_contest": next(iter([*running, *upcoming]), None),
                                                  "top_rated": top_rated, "me": me})


def _standings(contest, problems=None):
    """The standings rows, cached for 30 s (the judge drops the entry on every verdict). The entry
    remembers which problems its cells are for, so adding, removing or reordering a contest's
    problems rebuilds it instead of serving cells that no longer line up with the columns."""
    cache_key = f"contest-standings-{contest.pk}"
    layout = ([cp.pk for cp in problems] if problems is not None
              else list(contest.contest_problems.values_list("pk", flat=True)))
    hit = cache.get(cache_key)
    if isinstance(hit, tuple) and hit[0] == layout:
        return hit[1]
    rows = compute_standings(contest)
    cache.set(cache_key, (layout, rows), 30)
    return rows


def contest_detail(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    problems = list(contest.contest_problems.select_related("problem"))
    me = (Participation.objects.filter(user=request.user, contest=contest).first()
          if request.user.is_authenticated else None)
    registered = me is not None
    my_row, leaders, next_cp, registrants = None, [], None, []
    if contest.has_started:
        rows = _standings(contest, problems)
        counted = [r for r in rows if not r["disqualified"]]
        # the board's top: the leaders while it runs, the final results once it is over
        leaders = counted[:6]
        for i, cp in enumerate(problems):
            cp.solved_count = sum(1 for r in counted if r["cells"][i]["solved"])
            cp.n_tried = sum(1 for r in counted if r["cells"][i]["solved"] or r["cells"][i]["wrong"])
        if request.user.is_authenticated:
            my_row = next((r for r in rows if r["user"].pk == request.user.pk), None)
            for i, cp in enumerate(problems):
                cp.my_cell = my_row["cells"][i] if my_row else None
        if contest.is_running:
            # Codeforces rules: what a problem is worth if solved now, without wrong tries
            minutes = int((timezone.now() - contest.start).total_seconds()) // 60
            for cp in problems:
                cp.now_points = problem_points(contest, cp.points, minutes, 0)
            if registered:
                next_cp = next((cp for cp in problems if not (cp.my_cell and cp.my_cell["solved"])), None)
    else:
        for cp in problems:
            cp.solved_count = cp.n_tried = 0
        # a few faces of who is coming, newest first
        registrants = [p.user for p in contest.participations.select_related("user").order_by("-registered_at")[:8]]
    return render(request, "contests/detail.html", {
        "contest": contest, "problems": problems, "registered": registered, "my_row": my_row,
        "leaders": leaders, "next_cp": next_cp, "registrants": registrants,
        "description_html": _render_statement(contest.description_md) if contest.description_md else "",
        "my_participation": me,
        "n_participants": contest.participations.count(),
        **_virtual_ctx(request, contest),
    })


def calendar_ics(request, pk):
    """The round as a calendar event (.ics) with a reminder an hour before, for any calendar app."""
    contest = get_object_or_404(Contest, pk=pk)
    url = request.build_absolute_uri(reverse("contests:detail", args=[contest.pk]))

    def stamp(moment):
        return moment.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    def text(value):
        return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//CodeArena//Musobaqalar//UZ", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             "BEGIN:VEVENT", f"UID:contest-{contest.pk}@{request.get_host()}", f"DTSTAMP:{stamp(timezone.now())}",
             f"DTSTART:{stamp(contest.start)}", f"DTEND:{stamp(contest.end)}", f"SUMMARY:{text(contest.title)}",
             f"URL:{url}", f"DESCRIPTION:{text(url)}",
             "BEGIN:VALARM", "TRIGGER:-PT1H", "ACTION:DISPLAY", f"DESCRIPTION:{text(contest.title)}", "END:VALARM",
             "END:VEVENT", "END:VCALENDAR", ""]
    response = HttpResponse("\r\n".join(lines), content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="codearena-{contest.pk}.ics"'
    return response


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
    problems = list(contest.contest_problems.select_related("problem"))
    rows = _standings(contest, problems)
    # per-problem solved / tried, over the rows that count (a DQ row is shown but not counted,
    # as on the contest page)
    counted = [r for r in rows if not r["disqualified"]]
    for i, cp in enumerate(problems):
        cp.n_solved = sum(1 for r in counted if r["cells"][i]["solved"])
        cp.n_tried = sum(1 for r in counted if r["cells"][i]["solved"] or r["cells"][i]["wrong"])
        cp.solve_pct = round(100 * cp.n_solved / len(counted)) if counted else 0
    me = contest.participations.filter(user=request.user).first() if request.user.is_authenticated else None
    my_row = next((r for r in rows if r["user"].pk == request.user.pk), None) if me is not None else None
    ctx = {"contest": contest, "rows": rows, "problems": problems, "registered": me is not None,
           "my_participation": me, "my_row": my_row}
    # the live refresh asks for the table only: no header, menu or streak queries per poll
    template = "contests/_standings_live.html" if request.headers.get("HX-Request") else "contests/standings.html"
    return render(request, template, ctx)


@staff_required
def submissions(request, pk):
    """Every submission of a round, newest first, for staff: during the round too, which the public
    status page hides. ?problem=<label>, ?user=<handle> and ?verdict=<code> narrow it; a standings
    cell opens one participant's one problem here. The table re-fetches itself while the round runs."""
    contest = get_object_or_404(Contest, pk=pk)
    problems = list(contest.contest_problems.select_related("problem"))
    label = {cp.problem_id: cp.label for cp in problems}
    f = {k: request.GET.get(k, "").strip() for k in ("problem", "user", "verdict")}
    qs = (Submission.objects.filter(contest=contest).select_related("user", "problem", "language")
          .defer("source", "compile_log"))
    picked = next((cp for cp in problems if cp.label == f["problem"]), None)
    if picked is not None:
        qs = qs.filter(problem_id=picked.problem_id)
    if f["user"]:
        qs = qs.filter(user__username=f["user"])
    if f["verdict"] in Submission.TERMINAL:
        qs = qs.filter(verdict=f["verdict"])
    page = Paginator(qs.order_by("-id"), 50).get_page(request.GET.get("page"))
    for s in page:
        s.label = label.get(s.problem_id, "?")
        s.elapsed = elapsed(max(0, int((s.created - contest.start).total_seconds()) // 60))
    if request.headers.get("HX-Request"):
        return render(request, "contests/_submissions_live.html", {"contest": contest, "page": page, "f": f})
    return render(request, "contests/submissions.html", {
        "contest": contest, "problems": problems, "page": page, "f": f, "verdicts": list(VERDICT_LABELS.items()),
        "participant": _participant_results(contest, problems, f["user"]) if f["user"] else None})


def _participant_results(contest, problems, username) -> dict | None:
    """One participant's round problem by problem, for staff to strike or restore a problem's result:
    their standings cell and the void on it, if any."""
    p = contest.participations.select_related("user").filter(user__username=username).first()
    if p is None:
        return None
    row = next((r for r in _standings(contest, problems) if r["user"].pk == p.user_id), None)
    voids = {v.contest_problem_id: v for v in p.voids.all()}
    return {"participation": p, "results": [{"cp": cp, "cell": row["cells"][i] if row else None,
                                             "void": voids.get(cp.id)} for i, cp in enumerate(problems)]}


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
            _rerate(request, p.contest)
        if p.contest.official_applied_at:
            rating.recalc_official()
            audit.record(request, audit.Action.RATING_RECOMPUTE, contest=p.contest, note="rasmiy")
            messages.success(request, "Rasmiy reyting qayta hisoblandi.")
    cache.delete(f"contest-standings-{pk}")
    if request.POST.get("back") == "report":
        return redirect("integrity:contest_report", pk)
    if request.POST.get("back") == "official":
        return redirect("moderation:contest_official", pk)
    return redirect("contests:standings", pk=pk)


@staff_required
@require_POST
def void(request, pk, user_id):
    """Strike (voided=1) or restore (voided=0) one participant's result on one problem of the round
    (label=<letter>, reason): for work that was not their own on that problem alone, where a
    disqualification would take the rest of their round too. Silent for the participant: the cell
    counts as untried. With penalty=1 (AI caught red-handed) the strike counts as a wrong try
    instead and the problem is blocked for the participant until the round ends. Standings,
    solves after publish and an applied rating follow, as after a DQ."""
    want = {"1": True, "0": False}.get(request.POST.get("voided"))
    if want is None:
        return HttpResponseBadRequest("voided must be 0 or 1")
    p = get_object_or_404(Participation.objects.select_related("contest", "user"), contest_id=pk, user_id=user_id)
    cp = get_object_or_404(ContestProblem, contest_id=pk, label=request.POST.get("label", ""))
    current = VoidedProblem.objects.filter(participation=p, contest_problem=cp).first()
    if want and current is None:
        reason = request.POST.get("reason", "").strip()[:200]
        penalty = request.POST.get("penalty") == "1"
        VoidedProblem.objects.create(participation=p, contest_problem=cp, reason=reason,
                                     penalty=penalty)
        audit.record(request, audit.Action.PENALTY if penalty else audit.Action.VOID,
                     contest=p.contest, subject=p.user,
                     note=f"{cp.label}: {reason}" if reason else cp.label)
        if penalty:
            messages.success(request, f"{p.user.username}: {cp.label} AI jarimasi — xato urinish hisoblandi, masala bloklandi.")
        else:
            messages.success(request, f"{p.user.username}: {cp.label} masalasi natijasi bekor qilindi.")
    elif not want and current is not None:
        current.delete()
        audit.record(request, audit.Action.UNVOID, contest=p.contest, subject=p.user, note=cp.label)
        messages.success(request, f"{p.user.username}: {cp.label} masalasi natijasi tiklandi.")
    else:  # a stale page or a second tab: already as asked
        return _back(request, pk)
    cache.delete(f"contest-standings-{pk}")
    if p.contest.published_at is not None:
        refresh_solves(cp.problem_id, [p.user_id])
    if p.contest.rating_applied:
        _rerate(request, p.contest)
    if p.contest.official_applied_at:
        rating.recalc_official()
        audit.record(request, audit.Action.RATING_RECOMPUTE, contest=p.contest, note="rasmiy")
        messages.success(request, "Rasmiy reyting qayta hisoblandi.")
    return _back(request, pk)


def _back(request, pk):
    """To the page the action came from (POST next=), else the standings."""
    nxt = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(nxt)
    return redirect("contests:standings", pk=pk)


def _rerate(request, contest):
    """A DQ moves the participant to last place, and a voided problem lowers their score, which
    changes everyone's delta. Only the latest rated contest can be redone without breaking later
    rating chains."""
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
        "registered": registered,
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
    problem = None
    if problem_id := request.POST.get("problem_id", ""):
        # Only a problem of this round, and only once it has started (titles are secret before).
        if problem_id.isdigit() and contest.has_started:
            problem = contest.contest_problems.filter(pk=problem_id).first()
        if problem is None:
            return HttpResponseBadRequest("unknown problem")
    Clarification.objects.create(contest=contest, problem=problem, user=request.user, question=question)
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
