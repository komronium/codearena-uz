from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.management import call_command
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.decorators import staff_required
from apps.contests.models import Contest, Participation
from apps.problems.models import Problem
from apps.submissions.models import Submission

from .models import FocusEvent, SimilarityFlag

# Difficulty tiers a genuine first-read-to-AC pass can't clear in seconds.
_FAST_SOLVE_DIFFICULTIES = {Problem.Difficulty.MEDIUM, Problem.Difficulty.HARD}
_FAST_SOLVE_SECONDS = 90


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
        row = counts.setdefault(fe.user, {"blur": 0, "focus": 0, "paste": 0, "copy": 0, "fast": 0, "last": None})
        row[fe.kind] += 1
        row["last"] = fe.at

    fast_solves = _fast_solves(contest)
    fast_solve_counts = {}
    for row in fast_solves:
        fast_solve_counts[row["user"]] = fast_solve_counts.get(row["user"], 0) + 1
    for user in fast_solve_counts:
        counts.setdefault(user, {"blur": 0, "focus": 0, "paste": 0, "copy": 0, "fast": 0, "last": None})

    # ponytail: risk = weighted event count; tune weights once real contests give data
    def _risk(c):
        return c["paste"] * 5 + c["copy"] * 2 + c["blur"] + c["fast"] * 3
    rows = sorted(counts.items(), key=lambda kv: -(_risk(kv[1]) + fast_solve_counts.get(kv[0], 0) * 4))
    parts = {p.user_id: p for p in Participation.objects.filter(contest=contest)}
    for user, c in rows:
        c["risk"] = _risk(c) + fast_solve_counts.get(user, 0) * 4
        c["fast_solves"] = fast_solve_counts.get(user, 0)
        c["participation"] = parts.get(user.pk)
    flags = SimilarityFlag.objects.filter(submission_a__contest=contest).select_related(
        "submission_a__user", "submission_b__user", "submission_a__problem")
    return render(request, "integrity/contest_report.html", {
        "contest": contest, "rows": rows, "flags": flags,
        "open_flags": sum(1 for f in flags if not f.reviewed),
        "fast_solves": fast_solves,
    })


def _fast_solves(contest):
    """First-ever submission for (user, problem) in this contest, AC, on a
    non-trivial problem, within _FAST_SOLVE_SECONDS of the problem becoming
    readable — implausible for a genuinely typed-from-scratch solution."""
    problem_ids = list(contest.contest_problems.filter(
        problem__difficulty__in=_FAST_SOLVE_DIFFICULTIES).values_list("problem_id", flat=True))
    if not problem_ids:
        return []
    starts = {p.user_id: max(p.registered_at, contest.start)
              for p in Participation.objects.filter(contest=contest)}
    subs = (Submission.objects.filter(contest=contest, problem_id__in=problem_ids)
            .select_related("user", "problem").order_by("created"))
    first_seen, out = set(), []
    for sub in subs:
        key = (sub.user_id, sub.problem_id)
        if key in first_seen:
            continue
        first_seen.add(key)
        if sub.verdict != "AC":
            continue
        t0 = starts.get(sub.user_id)
        if t0 is None:
            continue
        elapsed = (sub.created - t0).total_seconds()
        if 0 <= elapsed < _FAST_SOLVE_SECONDS:
            out.append({"user": sub.user, "problem": sub.problem, "elapsed": int(elapsed), "submission": sub})
    return out


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
