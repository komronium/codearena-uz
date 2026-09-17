from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

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


@staff_member_required
def contest_report(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    counts = {}
    for fe in FocusEvent.objects.filter(contest=contest).select_related("user"):
        row = counts.setdefault(fe.user, {"blur": 0, "focus": 0, "paste": 0, "copy": 0})
        row[fe.kind] += 1
    flags = SimilarityFlag.objects.filter(submission_a__contest=contest).select_related(
        "submission_a__user", "submission_b__user", "submission_a__problem")
    return render(request, "integrity/contest_report.html", {
        "contest": contest, "counts": counts, "flags": flags,
    })
