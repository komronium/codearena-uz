import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.submissions.models import Submission

from . import duels
from .access import can_review
from .forms import AssignmentForm
from .models import Assignment, AssignmentProblem, Duel, ReviewComment
from .progress import cell, grid


def can_manage(user, group) -> bool:
    return user.is_staff or group.teacher_id == user.id


@login_required
def assignment_list(request):
    mine = list(Assignment.objects.filter(group__members=request.user).select_related("group")
                .prefetch_related("assignment_problems"))
    solved = set(Submission.objects.filter(user=request.user, verdict=Submission.Verdict.AC)
                 .values_list("problem_id", flat=True))
    for a in mine:
        ids = [ap.problem_id for ap in a.assignment_problems.all()]
        a.my_total, a.my_solved = len(ids), sum(1 for i in ids if i in solved)
    taught = Assignment.objects.none()
    if request.user.is_staff:
        taught = Assignment.objects.all()
    elif request.user.taught_groups.exists():
        taught = Assignment.objects.filter(group__teacher=request.user)
    return render(request, "classroom/list.html", {
        "assignments": mine,
        "taught": taught.select_related("group"),
        "can_create": request.user.is_staff or request.user.taught_groups.exists(),
        "now": timezone.now(),
    })


@login_required
def assignment_edit(request, pk=None):
    assignment = get_object_or_404(Assignment, pk=pk) if pk else None
    if assignment and not can_manage(request.user, assignment.group):
        raise PermissionDenied
    if not (request.user.is_staff or request.user.taught_groups.exists()):
        raise PermissionDenied
    form = AssignmentForm(request.POST or None, instance=assignment, user=request.user)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            a = form.save(commit=False)
            if a.pk is None:
                a.created_by = request.user
            a.save()
            a.assignment_problems.all().delete()
            AssignmentProblem.objects.bulk_create(
                AssignmentProblem(assignment=a, problem=p, order=i) for i, p in enumerate(form.cleaned_data["problems"]))
        return redirect("classroom:detail", a.pk)
    return render(request, "classroom/form.html", {"form": form, "assignment": assignment})


@login_required
def assignment_detail(request, pk):
    assignment = get_object_or_404(Assignment.objects.select_related("group"), pk=pk)
    manages = can_manage(request.user, assignment.group)
    member = assignment.group.members.filter(pk=request.user.pk).exists()
    if not (manages or member):
        raise Http404
    problems = [ap.problem for ap in assignment.assignment_problems.select_related("problem")]
    ctx = {"assignment": assignment, "problems": problems}
    if manages:
        rows = grid(assignment)
        if request.GET.get("format") == "csv":
            return _csv(assignment, problems, rows)
        ctx["grid"] = rows
    if member:
        subs = {}
        for s in Submission.objects.filter(user=request.user, problem__in=problems).order_by("created", "id"):
            subs.setdefault(s.problem_id, []).append(s)
        ctx["mine"] = [{"problem": p, **cell(subs.get(p.pk, []), assignment.deadline)} for p in problems]
    return render(request, "classroom/detail.html", ctx)


_CSV_STATUS = {"ok": "ok", "late": "kech", "none": ""}


def _csv(assignment, problems, rows):
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="vazifa-{assignment.pk}.csv"'
    resp.write("﻿")  # Excel reads UTF-8 only with a BOM
    w = csv.writer(resp)
    w.writerow(["Foydalanuvchi", "Ism", *[p.title for p in problems], "O‘z vaqtida", "Jami"])
    for r in rows:
        w.writerow([r["user"].username, r["user"].get_full_name(),
                    *[_CSV_STATUS.get(c["status"], f"x{c['tries']}") for c in r["cells"]],
                    r["on_time"], r["solved"]])
    return resp


@login_required
@require_POST
def review(request, pk):
    submission = get_object_or_404(Submission, pk=pk)
    if not can_review(request.user, submission):
        raise Http404
    body = request.POST.get("body", "").strip()
    line = request.POST.get("line", "").strip()
    n_lines = len(submission.source.splitlines())
    if not body or len(body) > 2000:
        return HttpResponseBadRequest("izoh bo‘sh yoki juda uzun")
    if line and not (line.isdigit() and 1 <= int(line) <= n_lines):
        return HttpResponseBadRequest(f"qator 1..{n_lines} oralig‘ida bo‘lishi kerak")
    ReviewComment.objects.create(submission=submission, author=request.user, body=body,
                                 line=int(line) if line else None,
                                 read=request.user.pk == submission.user_id)
    return redirect(reverse("submissions:detail", args=[pk]) + "#review")


@login_required
def duel_list(request):
    duels.settle_open(request.user)
    error = ""
    if request.method == "POST":
        if "find" in request.POST:
            duel, error = duels.find_opponent(request.user, request.POST.get("difficulty", ""))
        else:
            duel, error = duels.challenge(request.user, request.POST.get("opponent", ""),
                                          request.POST.get("difficulty", ""))
        if duel is not None:
            return redirect("classroom:duel", duel.pk)
    mine = (Duel.objects.filter(Q(challenger=request.user) | Q(opponent=request.user))
            .select_related("challenger", "opponent", "winner", "problem"))
    joinable = duels.joinable_counts(request.user)
    return render(request, "classroom/duels.html", {
        "incoming": [d for d in mine if d.status == Duel.Status.PENDING and d.opponent_id == request.user.pk],
        "open": [d for d in mine if d.status in duels.OPEN
                 and not (d.status == Duel.Status.PENDING and d.opponent_id == request.user.pk)],
        # an open duel nobody joined was never a duel: it stays out of the record
        "history": [d for d in mine if d.status not in duels.OPEN and d.opponent_id][:30],
        "error": error, "difficulties": Duel._meta.get_field("difficulty").choices,
        "levels": [{"value": v, "label": lbl, "joinable": joinable.get(v, 0)}
                   for v, lbl in Duel._meta.get_field("difficulty").choices],
        "form": request.POST if error else {},
        # usernames are hard to remember: offer the people from your groups
        "classmates": sorted(set(User.objects.filter(student_groups__in=request.user.student_groups.all(),
                                                     is_active=True)
                                 .exclude(pk=request.user.pk).values_list("username", flat=True)[:100])),
    })


def _my_duel(request, pk):
    duel = get_object_or_404(Duel.objects.select_related("challenger", "opponent", "winner", "problem"), pk=pk)
    if request.user.pk not in duel.players() and not request.user.is_staff:
        raise Http404
    return duel


@login_required
@require_POST
def duel_answer(request, pk):
    duel = _my_duel(request, pk)
    if request.POST.get("accept") == "1":
        if duel.opponent_id != request.user.pk:
            raise Http404
        error = duels.accept(duel, request.user)
        if error:
            messages.error(request, error)
    else:
        duels.decline(duel, request.user)
    return redirect("classroom:duel", duel.pk)


@login_required
def duel_detail(request, pk):
    duel = _my_duel(request, pk)
    duels.settle(duel)
    duel.refresh_from_db()
    state = f"{duel.status}.{duel.opponent_id or 0}"
    if request.headers.get("HX-Request"):
        seen = request.GET.get("seen")
        if seen and seen != state:  # someone joined, or it ended: the whole page changes
            return HttpResponse(headers={"HX-Refresh": "true"})
        template = "classroom/_duel_status.html"
    else:
        template = "classroom/duel.html"
    return render(request, template, {"duel": duel, "state": state, **_duel_board(duel, request.user)})


def _mmss(t) -> str:
    s = int(t.total_seconds())
    return f"{s // 60:02d}:{s % 60:02d}"


def _pct(t) -> str:
    """Where `t` falls on the duel track, as a CSS percentage (a string, so the
    template's number localisation can't turn the dot into a comma)."""
    return f"{min(t / duels.DURATION, 1) * 100:.2f}"


def _duel_board(duel, viewer) -> dict:
    """Both players' own runs on one 0..DURATION track, open to both like a live
    standings row: every attempt, the AC and how long it took, a clock still running."""
    now = timezone.now()
    rows = []
    for u, delta in ((duel.challenger, duel.challenger_delta), (duel.opponent, duel.opponent_delta)):
        r = duels.run(duel, u.pk) if u else None
        rows.append({
            "user": u, "run": r, "delta": delta, "winner": u is not None and duel.winner_id == u.pk,
            "attempts": len(r.subs) if r else 0,
            "solved_in": _mmss(r.solved_in) if r and r.solved_in is not None else None,
            "solved_at": _pct(r.solved_in) if r and r.solved_in is not None else None,
            "running": r is not None and r.solved_in is None and now < r.end,
            "marks": [{"at": _pct(t), "time": _mmss(t), "verdict": v}
                      for t, v in r.subs] if r else [],
        })
    solved = [row["run"].solved_in for row in rows if row["run"] and row["run"].solved_in is not None]
    best = min(solved, default=None)
    me = next((row for row in rows if row["user"] and row["user"].pk == viewer.pk), None)
    return {
        "players": rows,
        # the time to beat: the faster AC so far, marked across both lanes
        "best": {"at": _pct(best), "time": _mmss(best)} if best is not None else None,
        # a running clock of yours races the other player's AC: this is when it's out of reach
        "beat_by": me["run"].start + best if me and me["running"] and best is not None else None,
        "my_run": me["run"] if me else None, "my_running": bool(me and me["running"]),
        "duration_s": int(duels.DURATION.total_seconds()), "expires": duel.created + duels.WAIT_FOR,
    }
