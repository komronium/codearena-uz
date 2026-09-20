from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.management import call_command
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.decorators import staff_required
from apps.contests.models import Contest, Participation

from .models import FocusEvent, SimilarityFlag


@login_required
@require_POST
def event(request):
    contest = get_object_or_404(Contest, pk=request.POST.get("contest_id"))
    kind = request.POST.get("kind")
    if kind not in FocusEvent.Kind.values:
        return HttpResponseBadRequest("bad kind")
    if not Participation.objects.filter(user=request.user, contest=contest).exists():
        return HttpResponseBadRequest("not a participant")
    FocusEvent.objects.create(user=request.user, contest=contest, kind=kind)
    return JsonResponse({"ok": True})


@staff_required
def contest_report(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    counts = {}
    for fe in FocusEvent.objects.filter(contest=contest).select_related("user").order_by("at"):
        row = counts.setdefault(fe.user, {"blur": 0, "focus": 0, "paste": 0, "copy": 0, "last": None})
        row[fe.kind] += 1
        row["last"] = fe.at
    # ponytail: risk = weighted event count; tune weights once real contests give data
    rows = sorted(counts.items(), key=lambda kv: -(kv[1]["paste"] * 5 + kv[1]["copy"] * 2 + kv[1]["blur"]))
    parts = {p.user_id: p for p in Participation.objects.filter(contest=contest)}
    for user, c in rows:
        c["risk"] = c["paste"] * 5 + c["copy"] * 2 + c["blur"]
        c["participation"] = parts.get(user.pk)
    flags = SimilarityFlag.objects.filter(submission_a__contest=contest).select_related(
        "submission_a__user", "submission_b__user", "submission_a__problem")
    return render(request, "integrity/contest_report.html", {
        "contest": contest, "rows": rows, "flags": flags,
        "open_flags": sum(1 for f in flags if not f.reviewed),
    })


@staff_required
@require_POST
def flag_review(request, pk):
    flag = get_object_or_404(SimilarityFlag, pk=pk)
    flag.reviewed = not flag.reviewed
    flag.note = request.POST.get("note", flag.note).strip()
    flag.save(update_fields=["reviewed", "note"])
    return redirect("integrity:contest_report", flag.submission_a.contest_id)


@staff_required
@require_POST
def flag_run(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    call_command("flag_similarity", contest.pk)
    messages.success(request, "O‘xshashlik tekshiruvi bajarildi.")
    return redirect("integrity:contest_report", contest.pk)
