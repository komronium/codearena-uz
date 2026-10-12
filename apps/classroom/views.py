import csv
import random
from collections import Counter

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Case, IntegerField, Q, Value, When
from django.http import Http404, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import Group, User
from apps.accounts.tiers import tier_color
from apps.problems.views import _render_statement
from apps.submissions.models import Submission

from . import duels
from .duel_badges import duel_badges
from .access import can_review
from .forms import AssignmentForm
from .models import Assignment, AssignmentProblem, Duel, DuelAnswer, DuelQuestion, ReviewComment
from .progress import cell, grid


def can_manage(user, group) -> bool:
    return user.is_staff or group.teacher_id == user.id


def can_teach(user) -> bool:
    return user.is_staff or user.role == User.Role.TEACHER


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
        "can_teach": can_teach(request.user),
        "my_groups": request.user.taught_groups.prefetch_related("members").order_by("name"),
        "joined_groups": request.user.student_groups.select_related("teacher").order_by("name"),
        "now": timezone.now(),
    })


@login_required
@require_POST
def group_create(request):
    if not can_teach(request.user):
        raise PermissionDenied
    name = request.POST.get("name", "").strip()[:100]
    if not name:
        messages.error(request, "Guruh nomini yozing.")
    else:
        g = Group.objects.create(name=name, teacher=request.user)
        messages.success(request, f"«{g.name}» guruhi ochildi. O‘quvchilarga kodni bering: {g.join_code}")
    return redirect("classroom:list")


@login_required
@require_POST
def group_join(request):
    code = request.POST.get("code", "").strip().upper().replace(" ", "")
    group = Group.objects.filter(join_code=code).first() if code else None
    if group is None:
        messages.error(request, "Bunday kodli guruh topilmadi. Kodni o‘qituvchingizdan qayta so‘rang.")
    elif group.teacher_id == request.user.id:
        messages.info(request, "Bu sizning guruhingiz.")
    else:
        group.members.add(request.user)
        messages.success(request, f"«{group.name}» guruhiga qo‘shildingiz. Vazifalar shu yerda ko‘rinadi.")
    return redirect("classroom:list")


@login_required
@require_POST
def group_remove_member(request, pk, user_id):
    group = get_object_or_404(Group, pk=pk)
    if not can_manage(request.user, group):
        raise PermissionDenied
    group.members.remove(user_id)
    messages.info(request, "O‘quvchi guruhdan chiqarildi.")
    return redirect("classroom:list")


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
            created = a.pk is None
            if created:
                a.created_by = request.user
            a.save()
            a.assignment_problems.all().delete()
            AssignmentProblem.objects.bulk_create(
                AssignmentProblem(assignment=a, problem=p, order=i) for i, p in enumerate(form.cleaned_data["problems"]))
            if created:
                from apps.accounts.telegram import notify_assignment

                transaction.on_commit(lambda assignment_id=a.pk: notify_assignment(assignment_id))
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
    # the teacher writes markdown (the form says so); rendered and sanitized like a statement
    ctx = {"assignment": assignment, "problems": problems,
           "description_html": _render_statement(assignment.description_md)}
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
        language, level = request.POST.get("language", ""), request.POST.get("difficulty", "")
        if "find" in request.POST:
            duel, error = duels.find_opponent(request.user, language, level)
        else:
            duel, error = duels.challenge(request.user, request.POST.get("opponent", ""), language, level)
        if duel is not None:
            return redirect("classroom:duel_play", duel.pk)
    mine = (Duel.objects.filter(Q(challenger=request.user) | Q(opponent=request.user))
            .select_related("challenger", "opponent", "winner"))
    joinable = duels.joinable_counts(request.user)
    finished = [d for d in mine if d.status == Duel.Status.FINISHED]
    record = {"wins": sum(1 for d in finished if d.winner_id == request.user.pk),
              "losses": sum(1 for d in finished if d.winner_id and d.winner_id != request.user.pk)}
    record["draws"] = len(finished) - record["wins"] - record["losses"]
    # the duel board: everyone with a finished duel, by duel rating
    played = Counter()
    for pair in Duel.objects.filter(status=Duel.Status.FINISHED).values_list("challenger_id", "opponent_id"):
        played.update(pair)
    played.pop(None, None)
    board = list(User.objects.filter(pk__in=played, is_active=True).order_by("-duel_rating", "username")
                 .only("username", "rating", "duel_rating")[:10])
    for u in board:
        u.duels = played[u.pk]
    rank = (User.objects.filter(pk__in=played, is_active=True, duel_rating__gt=request.user.duel_rating).count() + 1
            if request.user.pk in played else None)
    return render(request, "classroom/duels.html", {
        "record": record, "board": board, "duel_rank": rank, "duelists": len(played),
        "incoming": [d for d in mine if d.status == Duel.Status.PENDING and d.opponent_id == request.user.pk],
        "open": [d for d in mine if d.status in duels.OPEN
                 and not (d.status == Duel.Status.PENDING and d.opponent_id == request.user.pk)],
        # an open duel nobody joined was never a duel: it stays out of the record
        "history": [d for d in mine if d.status not in duels.OPEN and d.opponent_id][:30],
        "error": error, "languages": duels.LANGUAGES, "levels": duels.LEVELS, "joinable": joinable,
        "form": request.POST if error else {}, "per_question": int(duels.PER_QUESTION.total_seconds()),
        "n_questions": duels.QUESTIONS, "badges": duel_badges(request.user),
    })


@login_required
def duel_people(request):
    """Who to challenge, for the duel form's finder (handles are hard to remember): with nothing typed your
    classmates and the people you have duelled, else up to 8 active users whose handle holds the text, the
    exact handle first, then those starting with it."""
    q = request.GET.get("q", "").strip()[:30]
    people = User.objects.filter(is_active=True).exclude(pk=request.user.pk)
    mates = set(people.filter(student_groups__in=request.user.student_groups.all()).values_list("pk", flat=True))
    if q:
        found = (people.filter(username__icontains=q)
                 .annotate(rank=Case(When(username__iexact=q, then=Value(0)),
                                     When(username__istartswith=q, then=Value(1)),
                                     default=Value(2), output_field=IntegerField()))
                 .order_by("rank", "username")[:8])
    else:
        pairs = (Duel.objects.filter(Q(challenger=request.user) | Q(opponent=request.user), opponent__isnull=False)
                 .order_by("-pk").values_list("challenger_id", "opponent_id")[:30])
        rivals = {b if a == request.user.pk else a for a, b in pairs}
        found = people.filter(pk__in=mates | rivals).order_by("username")[:8]
    return JsonResponse({"results": [{"username": u.username, "color": tier_color(u.rating), "duel": u.duel_rating,
                                      "mate": u.pk in mates} for u in found]})


def _my_duel(request, pk):
    duel = get_object_or_404(Duel.objects.select_related("challenger", "opponent", "winner"), pk=pk)
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
            return redirect("classroom:duel_play", duel.pk)
    else:
        duels.decline(duel, request.user)
    return redirect("classroom:duel", duel.pk)


@login_required
def duel_detail(request, pk):
    duel = _my_duel(request, pk)
    duels.settle(duel)
    duel.refresh_from_db()
    board = _duel_board(duel, request.user)
    state = f"{duel.status}.{duel.opponent_id or 0}.{board['my_over']}"
    if request.headers.get("HX-Request"):
        seen = request.GET.get("seen")
        if seen and seen != state:  # someone joined, a run ended, or the duel did: the whole page changes
            return HttpResponse(headers={"HX-Refresh": "true"})
        template = "classroom/_duel_status.html"
    else:
        template = "classroom/duel.html"
    return render(request, template, {"duel": duel, "state": state, **board})


def _secs(t) -> str:
    return f"{t.total_seconds():.1f}".replace(".", ",")


def _duel_board(duel, viewer) -> dict:
    """Both players' runs side by side, open to both like a live standings row: how many right, the time
    spent, and a cell per question (right, wrong, on it, not yet). The questions themselves, with the
    answers, only once your own run is over, so nobody sees them before playing."""
    now = timezone.now()
    rows, runs = [], {}
    for u, delta in ((duel.challenger, duel.challenger_delta), (duel.opponent, duel.opponent_delta)):
        r = duels.run(duel, u.pk) if u and duel.mode == Duel.Mode.QUIZ else None
        runs[u.pk if u else None] = r
        cells = []
        if r is not None:
            for a in r.answers:
                state = "ok" if a.correct else ("bad" if r.closed(a, now) else "now")
                took = min(a.answered_at - a.shown_at, duels.PER_QUESTION) if a.answered_at else None
                cells.append({"state": state, "secs": _secs(took) if took is not None else ""})
            if r.over(now):
                cells += [{"state": "bad", "secs": ""}] * (duels.QUESTIONS - len(cells))
            cells += [{"state": "", "secs": ""}] * (duels.QUESTIONS - len(cells))
        rows.append({"user": u, "run": r, "delta": delta, "winner": u is not None and duel.winner_id == u.pk,
                     "over": r is not None and r.over(now), "right": r.right if r else 0,
                     "spent": _secs(r.spent(now)) if r is not None and r.over(now) else "", "cells": cells})
    mine = runs.get(viewer.pk)
    my_over = mine is not None and mine.over(now)
    review = []
    if duel.mode == Duel.Mode.QUIZ and (my_over or viewer.is_staff and duel.status == Duel.Status.FINISHED):
        other = duel.opponent_id if viewer.pk == duel.challenger_id else duel.challenger_id
        theirs = runs.get(other)
        show_theirs = theirs is not None and theirs.over(now)
        by_index = lambda r: {a.index: a for a in r.answers} if r else {}
        me_by, them_by = by_index(mine), by_index(theirs)
        questions = DuelQuestion.objects.in_bulk(duel.questions)
        for i, qid in enumerate(duel.questions):
            q = questions.get(qid)
            if q is None:
                continue
            review.append({"n": i + 1, "q": q, "me": me_by.get(i), "them": them_by.get(i) if show_theirs else None,
                           "them_pending": not show_theirs})
    return {
        "players": rows, "review": review, "my_over": my_over,
        "my_playing": mine is not None and not my_over,
        "my_started": bool(mine and mine.answers),
        "per_question": int(duels.PER_QUESTION.total_seconds()), "n_questions": duels.QUESTIONS,
        "expires": duel.created + duels.WAIT_FOR,
    }


def _shuffled(options, seed) -> list:
    out = list(options)
    random.Random(seed).shuffle(out)
    return out


@login_required
def duel_play(request, pk):
    """Your run: one question at a time with its own 20 seconds (from when the server first showed it, so a
    reload doesn't reset it), then a moment to see if you were right before the next one."""
    duel = _my_duel(request, pk)
    if duel.mode != Duel.Mode.QUIZ or request.user.pk not in duel.players():
        return redirect("classroom:duel", duel.pk)
    if request.method == "POST":
        try:
            index = int(request.POST.get("index", ""))
        except ValueError:
            return HttpResponseBadRequest()
        duels.answer(duel, request.user, index, request.POST.get("answer", ""))
        return redirect(reverse("classroom:duel_play", args=[duel.pk]) + f"?after={index}")
    after = request.GET.get("after")
    if after is not None and after.isdigit():
        a = (DuelAnswer.objects.select_related("question")
             .filter(duel=duel, user=request.user, index=int(after)).first())
        r = duels.run(duel, request.user.pk)
        if a is not None and r is not None and r.closed(a, timezone.now()):
            late = a.answered_at is None or a.answered_at > a.shown_at + duels.PER_QUESTION + duels.GRACE
            return render(request, "classroom/duel_play.html", {
                "duel": duel, "feedback": a, "q": a.question, "n": a.index + 1, "n_questions": duels.QUESTIONS,
                "timed_out": late or not a.answer,
                "last": a.index + 1 >= duels.QUESTIONS or r.over(timezone.now()),
                "cells": _my_cells(r), "language": duel.get_language_display()})
    current = duels.current(duel, request.user)
    if current is None:
        return redirect("classroom:duel", duel.pk)
    q = current.question
    r = duels.run(duel, request.user.pk)
    return render(request, "classroom/duel_play.html", {
        "duel": duel, "a": current, "q": q, "n": current.index + 1, "n_questions": duels.QUESTIONS,
        "remaining_ms": max(0, int((current.shown_at + duels.PER_QUESTION - timezone.now()).total_seconds() * 1000)),
        "per_question": int(duels.PER_QUESTION.total_seconds()),
        "options": _shuffled(q.options, f"{duel.pk}-{request.user.pk}-{current.index}"),
        "cells": _my_cells(r), "language": duel.get_language_display(),
    })


def _my_cells(r) -> list[str]:
    now = timezone.now()
    cells = ["ok" if a.correct else ("bad" if r.closed(a, now) else "now") for a in r.answers]
    return cells + [""] * (duels.QUESTIONS - len(cells))
