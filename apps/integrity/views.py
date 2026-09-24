from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.management import call_command
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.accounts.decorators import staff_required
from apps.accounts.models import User
from apps.contests.models import Contest, Participation
from apps.problems.models import Language, Problem
from apps.submissions.models import Submission

from .models import CodeSnapshot, FocusEvent, SimilarityFlag
from .similarity import MIN_LINES, THRESHOLD, matched_lines

# First-open-to-AC time no genuine read-think-type pass beats, per difficulty (beginner: none).
_SPEED_LIMITS_S = {Problem.Difficulty.EASY: 90, Problem.Difficulty.MEDIUM: 240, Problem.Difficulty.HARD: 420}
# An absence this long, followed by AC this soon after coming back, is the PrtSc -> AI -> retype shape.
_MIN_AWAY_S = 20
_QUICK_AFTER_RETURN_S = 180
# chars that appeared between two consecutive snapshots (~10 s apart) worth pointing at
_JUMP_CHARS = 150


_MAX_AWAY_MS = 6 * 3600 * 1000
_MAX_SNAPSHOT_CHARS = 64_000


def _participant_contest(request):
    """(contest, contest problem or None) for a POST from a participant, or an error response."""
    contest = get_object_or_404(Contest, pk=request.POST.get("contest_id"))
    if not Participation.objects.filter(user=request.user, contest=contest).exists():
        return None, None, HttpResponseBadRequest("not a participant")
    problem = None
    if request.POST.get("problem_id"):
        problem = Problem.objects.filter(pk=request.POST["problem_id"], contests=contest).first()
        if problem is None:
            return None, None, HttpResponseBadRequest("problem not in contest")
    return contest, problem, None


@login_required
@require_POST
def event(request):
    kind = request.POST.get("kind")
    if kind not in FocusEvent.Kind.values:
        return HttpResponseBadRequest("bad kind")
    contest, problem, error = _participant_contest(request)
    if error:
        return error
    away = request.POST.get("away_ms", "")
    away_ms = min(int(away), _MAX_AWAY_MS) if kind == FocusEvent.Kind.FOCUS and away.isdigit() else None
    FocusEvent.objects.create(user=request.user, contest=contest, kind=kind, problem=problem, away_ms=away_ms)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def snapshot(request):
    contest, problem, error = _participant_contest(request)
    if error:
        return error
    if problem is None or not contest.is_running:
        return HttpResponseBadRequest("no running contest problem")
    source = request.POST.get("source", "")[:_MAX_SNAPSHOT_CHARS]
    last = (CodeSnapshot.objects.filter(user=request.user, contest=contest, problem=problem)
            .order_by("-at").values_list("source", flat=True).first())
    if source != last:
        CodeSnapshot.objects.create(user=request.user, contest=contest, problem=problem, source=source,
                                    language=Language.objects.filter(code=request.POST.get("language")).first())
    return JsonResponse({"ok": True})


@staff_required
def contest_report(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    events = list(FocusEvent.objects.filter(contest=contest).select_related("user").order_by("at"))
    counts = {}
    for fe in events:
        row = counts.setdefault(fe.user, _empty_counts())
        row[fe.kind] += 1
        row["away_ms"] += fe.away_ms or 0
        row["last"] = fe.at

    suspicious = _suspicious_solves(contest, events)
    n_suspicious = {}
    for r in suspicious:
        n_suspicious[r["user"]] = n_suspicious.get(r["user"], 0) + 1
        counts.setdefault(r["user"], _empty_counts())

    # ponytail: risk = weighted event count; tune weights once real contests give data
    def _risk(user, c):
        return (c["paste"] * 5 + c["copy"] * 2 + c["blur"] + c["fast"] * 3
                + c["away_ms"] // 60_000 + n_suspicious.get(user, 0) * 4)
    parts = {p.user_id: p for p in Participation.objects.filter(contest=contest)}
    for user, c in counts.items():
        c["risk"] = _risk(user, c)
        c["suspicious"] = n_suspicious.get(user, 0)
        c["participation"] = parts.get(user.pk)
    rows = sorted(counts.items(), key=lambda kv: -kv[1]["risk"])
    flags = _flag_cards(contest, counts, parts)
    return render(request, "integrity/contest_report.html", {
        "contest": contest, "rows": rows, "flags": flags,
        "open_flags": sum(1 for f in flags if not f.reviewed),
        "suspicious": suspicious, "min_lines": MIN_LINES, "threshold": round(THRESHOLD * 100),
        "quick_after_return_s": _QUICK_AFTER_RETURN_S, "min_away_s": _MIN_AWAY_S,
        "speed_limits": _SPEED_LIMITS_S, "contest_problems": contest.contest_problems.select_related("problem"),
    })


def _empty_counts():
    return {kind: 0 for kind in FocusEvent.Kind.values} | {"away_ms": 0, "last": None}


def _flag_cards(contest, counts, parts):
    """Similarity flags ready for side-by-side review: earlier submission on the left,
    each line marked if it is part of a shared block. Unreviewed first, then by score."""
    labels = dict(contest.contest_problems.values_list("problem_id", "label"))
    flags = sorted(
        SimilarityFlag.objects.filter(submission_a__contest=contest).select_related(
            "submission_a__user", "submission_b__user", "submission_a__problem", "submission_a__language",
            "submission_b__language"),
        key=lambda f: (f.reviewed, -f.score))
    for f in flags:
        first, second = sorted((f.submission_a, f.submission_b), key=lambda s: s.created)
        hit_first, hit_second = matched_lines(first.source, second.source)
        f.label = labels.get(first.problem_id, "")
        f.problem = f.submission_a.problem
        f.gap_min = int((second.created - first.created).total_seconds() // 60)
        f.sides = [_side(first, hit_first, counts, parts), _side(second, hit_second, counts, parts)]
    return flags


def _side(sub, hits, counts, parts):
    lines = [(i + 1, text, i in hits) for i, text in enumerate(sub.source.splitlines())]
    code = sum(1 for _, text, _ in lines if text.strip())
    events = counts.get(sub.user, {})
    return {
        "sub": sub, "user": sub.user, "lines": lines, "n_hit": len(hits), "n_code": code,
        "paste": events.get("paste", 0), "blur": events.get("blur", 0),
        "participation": parts.get(sub.user_id),
    }


def _suspicious_solves(contest, events):
    """First AC per (user, problem) that looks copied rather than written:
    - too fast: solved within the difficulty's limit of first opening the problem, or
    - back-and-solve: AC shortly after returning from a real absence (the PrtSc -> AI -> retype pattern).
    """
    views, returns = {}, {}
    for fe in events:
        if fe.kind == FocusEvent.Kind.VIEW and fe.problem_id:
            views.setdefault((fe.user_id, fe.problem_id), fe.at)
        elif fe.kind == FocusEvent.Kind.FOCUS and (fe.away_ms or 0) >= _MIN_AWAY_S * 1000:
            returns.setdefault(fe.user_id, []).append(fe)
    starts = {p.user_id: max(p.registered_at, contest.start) for p in Participation.objects.filter(contest=contest)}
    subs = (Submission.objects.filter(contest=contest, verdict="AC")
            .select_related("user", "problem").order_by("created"))
    seen, out = set(), []
    for sub in subs:
        key = (sub.user_id, sub.problem_id)
        if key in seen:
            continue
        seen.add(key)
        t0 = views.get(key) or starts.get(sub.user_id) or contest.start
        elapsed = int((sub.created - t0).total_seconds())
        limit = _SPEED_LIMITS_S.get(sub.problem.difficulty)
        ret = next((r for r in reversed(returns.get(sub.user_id, [])) if r.at <= sub.created), None)
        after_return = int((sub.created - ret.at).total_seconds()) if ret else None
        too_fast = limit is not None and 0 <= elapsed < limit
        back_and_solve = after_return is not None and after_return <= _QUICK_AFTER_RETURN_S
        if too_fast or back_and_solve:
            out.append({
                "user": sub.user, "problem": sub.problem, "submission": sub, "elapsed": elapsed,
                "too_fast": too_fast, "back_and_solve": back_and_solve,
                "away_s": ret.away_ms // 1000 if back_and_solve else None, "after_return": after_return,
                "has_view": key in views,
            })
    return out


@staff_required
def replay(request, pk, user_id, problem_id):
    """Step through a participant's editor snapshots for one problem, with their
    leaves/returns and submissions on the same timeline."""
    contest = get_object_or_404(Contest, pk=pk)
    cp = get_object_or_404(contest.contest_problems.select_related("problem"), problem_id=problem_id)
    participant = get_object_or_404(User, pk=user_id)
    snaps = list(CodeSnapshot.objects.filter(contest=contest, user=participant, problem_id=problem_id)
                 .select_related("language").order_by("at"))
    frames, jumps = [], []
    prev_len, prev_at = 0, contest.start
    for snap in snaps:
        grew = len(snap.source) - prev_len
        secs = max(1, int((snap.at - prev_at).total_seconds()))
        frames.append({"t": snap.at.isoformat(), "src": snap.source,
                       "lang": snap.language.name if snap.language else ""})
        # a big chunk appearing between two 10-second snapshots is text that wasn't typed here
        if grew >= _JUMP_CHARS:
            jumps.append({"at": snap.at, "chars": grew, "secs": secs, "frame": len(frames) - 1})
        prev_len, prev_at = len(snap.source), snap.at
    timeline = [
        {"at": fe.at, "kind": fe.kind, "away_s": (fe.away_ms or 0) // 1000,
         "here": fe.problem_id == cp.problem_id}
        for fe in FocusEvent.objects.filter(contest=contest, user=participant,
                                            kind__in=["blur", "focus", "paste", "fast", "view"]).order_by("at")
    ]
    timeline += [{"at": sub.created, "kind": "submit", "sub": sub, "here": True}
                 for sub in Submission.objects.filter(contest=contest, user=participant, problem_id=problem_id)]
    timeline += [{"at": j["at"], "kind": "jump", "chars": j["chars"], "secs": j["secs"], "here": True} for j in jumps]
    timeline.sort(key=lambda item: item["at"])
    return render(request, "integrity/replay.html", {
        "contest": contest, "cp": cp, "participant": participant, "frames": frames, "jumps": jumps,
        "timeline": timeline,
        "others": contest.contest_problems.select_related("problem"),
    })


@staff_required
@require_POST
def flag_review(request, pk):
    flag = get_object_or_404(SimilarityFlag, pk=pk)
    flag.reviewed = not flag.reviewed
    flag.note = request.POST.get("note", flag.note).strip()
    flag.save(update_fields=["reviewed", "note"])
    return redirect(reverse("integrity:contest_report", args=[flag.submission_a.contest_id]) + f"#flag-{flag.pk}")


@staff_required
@require_POST
def flag_run(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    labels = request.POST.getlist("problems")
    if not labels:
        messages.error(request, "Tekshirish uchun kamida bitta masalani tanlang.")
        return redirect("integrity:contest_report", contest.pk)
    call_command("flag_similarity", contest.pk, problems=",".join(labels))
    messages.success(request, f"O‘xshashlik tekshirildi: {', '.join(labels)}.")
    return redirect("integrity:contest_report", contest.pk)
