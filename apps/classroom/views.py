import csv

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.submissions.models import Submission

from .access import can_review
from .forms import AssignmentForm
from .models import Assignment, AssignmentProblem, ReviewComment
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
