import django_rq
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.contests.models import Participation, VoidedProblem
from apps.contests.services import (
    access_allowed,
    active_contest_for,
    in_running_contest,
    in_upcoming_contest,
)
from apps.contests.virtual import active_virtual_for
from apps.problems.models import Language, Problem
from judge import sql_judge
from judge.runner import run_submission, run_trial

from .models import VERDICT_LABELS, Submission, UserProblemSolved
from .ratelimit import rate_limited

MAX_SOURCE = 64 * 1024
RATE_LIMIT_MAX = 10  # submissions per minute
TRIAL_RATE_MAX = (
    20  # "Sinab ko'rish" runs per minute: cheaper than a submit, but still a container
)
MAX_TRIAL_INPUT = 64 * 1024
TRIAL_SQL_ROWS = 100  # rows of a SQL trial result sent back to draw


def _gate(request, slug):
    """(problem, contest, error) for someone about to run code against `slug`."""
    try:
        problem = Problem.objects.get(slug=slug)
    except Problem.DoesNotExist:
        raise Http404
    contest = active_contest_for(request.user, problem)
    is_owner_or_staff = request.user.is_staff or problem.author_id == request.user.id
    if not is_owner_or_staff and (
        (not problem.is_public and contest is None) or in_upcoming_contest(problem)
    ):
        raise Http404
    # re-check supervised-mode eligibility on every submit, not just at
    # registration — the client IP can change mid-contest.
    if contest is not None and not access_allowed(
        request.user, contest, request.META.get("REMOTE_ADDR")
    ):
        return problem, contest, HttpResponseBadRequest("Bu musobaqaga shu tarmoqdan yuborib bo‘lmaydi.")
    if (
        contest is not None
        and Participation.objects.filter(
            user=request.user, contest=contest, disqualified=True
        ).exists()
    ):
        return (
            problem,
            contest,
            HttpResponseBadRequest("Siz bu musobaqadan chetlatilgansiz."),
        )
    if (
        contest is not None
        and VoidedProblem.objects.filter(
            participation__user=request.user,
            participation__contest=contest,
            contest_problem__problem=problem,
            penalty=True,
        ).exists()
    ):
        # AI penalty: the problem is struck and blocked for the rest of the round
        return (
            problem,
            contest,
            HttpResponseBadRequest("Bu masala shu raundda bloklangan."),
        )
    return problem, contest, None


def _refused(request, problem, message, status):
    """A refused submit as a page, not bare text: the draft is still in the editor (localStorage), so the way
    back is one click. The status code stays what it was. The editor's own fetch gets the message as JSON."""
    if request.headers.get("X-Fetch") == "1":
        return JsonResponse({"error": message}, status=status)
    return render(request, "submissions/refused.html", {"message": message, "problem": problem}, status=status)


@login_required
@require_POST
def submit(request, slug):
    problem, contest, error = _gate(request, slug)
    if error:
        return _refused(request, problem, error.content.decode(), error.status_code)
    if rate_limited(request.user.id, "submit", RATE_LIMIT_MAX):
        return _refused(request, problem, "Juda tez yuboryapsiz. Bir daqiqa kuting va qayta yuboring.", 429)
    language = get_object_or_404(
        Language, code=request.POST.get("language"), is_active=True
    )
    source = request.POST.get("source", "")
    if not source.strip() or len(source) > MAX_SOURCE:
        return _refused(request, problem, "Kod bo‘sh yoki juda katta (64 KB gacha).", 400)
    if (
        request.POST.get("pledge") == "1" and not request.user.honor_pledged_at
    ):  # accepted in the dialog
        User.objects.filter(pk=request.user.pk).update(honor_pledged_at=timezone.now())
    telemetry = {}
    if contest is not None:
        seen = (
            Participation.objects.filter(user=request.user, contest=contest)
            .values_list("last_seen_at", flat=True)
            .first()
        )
        telemetry = {
            "device": request.POST.get("device", "")[:64],
            "tracker_seen_at": seen,
            "ip": request.META.get("REMOTE_ADDR") or None,
        }
    if contest is None:
        telemetry["virtual"] = active_virtual_for(request.user, problem)
    sub = Submission.objects.create(
        user=request.user,
        problem=problem,
        contest=contest,
        language=language,
        source=source,
        **telemetry,
    )
    django_rq.enqueue(run_submission, sub.pk)
    if request.headers.get("X-Fetch") == "1":  # the workspace shows the verdict itself (problems/detail.html)
        return JsonResponse({"id": sub.pk, "status": reverse("submissions:status", args=[sub.pk]),
                             "url": reverse("submissions:detail", args=[sub.pk])})
    return redirect(
        "submissions:detail", sub.pk
    )  # the result as it comes in; "Masalaga qaytish" leads back


@login_required
@require_POST
def trial(request, slug):
    """Run code on the samples (or one custom stdin) without creating a Submission."""
    problem, _, error = _gate(request, slug)
    if error:
        return JsonResponse({"error": error.content.decode()}, status=400)
    source, stdin = request.POST.get("source", ""), request.POST.get("stdin", "")
    if not source.strip() or len(source) > MAX_SOURCE or len(stdin) > MAX_TRIAL_INPUT:
        return JsonResponse({"error": "Kod bo‘sh yoki juda katta"}, status=400)
    if rate_limited(request.user.id, "trial", TRIAL_RATE_MAX):
        return JsonResponse(
            {"error": "Juda tez-tez — bir daqiqadan keyin urinib ko‘ring"}, status=429
        )
    if problem.kind == Problem.Kind.SQL:
        return _sql_trial(problem, source)
    language = get_object_or_404(
        Language, code=request.POST.get("language"), is_active=True
    )
    if stdin.strip():
        inputs, expected = [stdin], None
    else:
        samples = list(problem.samples)
        if not samples:
            return JsonResponse(
                {"error": "Namunaviy test yo‘q — o‘z inputingizni kiriting"}, status=400
            )
        inputs, expected = [t.input for t in samples], [t.expected for t in samples]
    job = django_rq.get_queue("run").enqueue(
        run_trial,
        language.code,
        source,
        inputs,
        expected,
        problem.tl_ms,
        problem.ml_mb,
        result_ttl=300,
        failure_ttl=300,
        meta={"user_id": request.user.pk},
    )
    return JsonResponse({"id": job.id})


def _sql_trial(problem, source):
    """The query on the sample data, answered right away: sqlite in memory, read-only and
    stopped at the time limit (judge.sql_judge), so no queue is needed."""
    dataset = getattr(problem, "sql_dataset", None)
    if dataset is None:
        return JsonResponse({"error": "Masalada ma‘lumotlar bazasi yo‘q"}, status=400)
    try:
        verdict, columns, rows = sql_judge.run_query_table(
            dataset.schema_sql, dataset.seed_sql, source, problem.tl_ms
        )
    except sql_judge.SQLJudgeError:
        verdict, columns, rows = "RE", [], []
    if verdict == "OK":
        verdict = (
            "AC"
            if sql_judge.rows_match(
                rows, dataset.expected_result, ordered=dataset.ordered
            )
            else "WA"
        )
    return JsonResponse(
        {
            "done": True,
            "sql": True,
            "verdict": verdict,
            "columns": columns,
            "rows": [
                ["NULL" if v is None else str(v) for v in row]
                for row in rows[:TRIAL_SQL_ROWS]
            ],
            "n_rows": len(rows),
            "expected": sql_judge.parse_rows(dataset.expected_result),
        }
    )


@login_required
def trial_status(request, job_id):
    job = django_rq.get_queue("run").fetch_job(job_id)
    if job is None or job.meta.get("user_id") != request.user.pk:
        raise Http404
    status = job.get_status()
    if status == "finished":
        return JsonResponse({"done": True, **job.return_value()})
    if status in ("failed", "stopped", "canceled"):
        return JsonResponse({"done": True, "verdict": "IE", "log": "", "cases": []})
    return JsonResponse({"done": False, "status": status})


def _own(request, pk):
    """Owner's submission. Staff may open anyone's; a user who solved the problem may read
    other people's accepted code (problem leaderboard), except while a contest with it runs."""
    s = get_object_or_404(
        Submission.objects.select_related("problem", "language", "user"), pk=pk
    )
    if (
        s.user_id == request.user.pk
        or request.user.is_staff
    ):
        return s
    if (
        s.verdict == "AC"
        and not in_running_contest(s.problem)
        and UserProblemSolved.objects.filter(
            user=request.user, problem=s.problem
        ).exists()
    ):
        return s
    raise Http404


def _beats(s) -> dict | None:
    """LeetCode's comparison after an accept: where this run's time and memory stand among the other accepted
    solutions of the problem in the same language (the share that did worse, ties counted half), with a
    histogram of their times. None until five others exist: a share of two is noise."""
    others = list(
        Submission.objects.filter(
            problem_id=s.problem_id, language_id=s.language_id, verdict="AC"
        )
        .exclude(pk=s.pk)
        .values_list("exec_ms", "mem_kb")
    )
    if len(others) < 5:
        return None

    def share(mine, values):
        worse = sum(1 for v in values if v > mine)
        ties = sum(1 for v in values if v == mine)
        return 100 * (worse + ties / 2) / len(values)

    times = [t for t, _ in others]
    mems = [m for _, m in others if m]
    lo, hi = min(times + [s.exec_ms]), max(times + [s.exec_ms])
    n_bins = 20
    width = max(1, -(-(hi - lo + 1) // n_bins))
    counts = [0] * n_bins
    for t in times:
        counts[min(n_bins - 1, (t - lo) // width)] += 1
    mine_bin = min(n_bins - 1, (s.exec_ms - lo) // width)
    top = max(counts) or 1
    bar_w, gap, h = 24, 6, 96
    bars = []
    for i, c in enumerate(counts):
        bh = max(3.0, c / top * h)
        bars.append(
            {
                "x": i * (bar_w + gap),
                "y": round(h - bh, 1),
                "h": round(bh, 1),
                "me": i == mine_bin,
            }
        )
    mark_x = mine_bin * (bar_w + gap) + bar_w / 2
    mark_y = h - bars[mine_bin]["h"] - 8
    return {
        "time": share(s.exec_ms, times),
        "mem": share(s.mem_kb, mems) if mems and s.mem_kb else None,
        "mem_mb": s.mem_kb / 1024,
        "n": len(others),
        "bars": bars,
        "bw": bar_w,
        "h": h,
        "w": n_bins * (bar_w + gap) - gap,
        "vb_w": n_bins * (bar_w + gap) - gap + 12,
        "vb_h": h + 54,
        "labels": [
            {"x": i * (bar_w + gap) + bar_w / 2, "y": h + 18, "ms": lo + i * width}
            for i in range(0, n_bins, 5)
        ],
        "mark": {"x": mark_x - 20, "y": mark_y - 20, "tx": mark_x, "ty": mark_y - 6},
    }


def _progress(s, saved: int, total: int) -> dict:
    """How far the judge is: the tests finished so far. While it runs, the judge keeps that count in the cache
    after each test (judge.runner), so the card can show 1/50, 2/50, 3/50…; the saved results only exist at the end."""
    from django.core.cache import cache

    done = saved if s.is_terminal else max(saved, cache.get(f"judge-progress:{s.pk}") or 0)
    done = min(done, total) if total else done
    return {"done": done, "total": total, "pct": int(done * 100 / total) if total else 0}


def _results_ctx(s):
    results = list(s.results.select_related("testcase"))
    first_fail = next((r for r in results if r.verdict != "AC"), None)
    if first_fail is not None:
        first_fail.index = results.index(first_fail) + 1
    total = s.total or s.problem.testcases.count()
    # one cell per test: passed, failed or never run (the judge stops at the first failure)
    n = min(total, 60)
    passed = min(s.passed, n)
    strip = ["ok"] * passed
    if s.is_terminal and s.verdict != Submission.Verdict.AC and passed < n:
        strip.append("bad")
    strip += ["no"] * (n - len(strip))
    return {
        "s": s,
        "results": results,
        "first_fail": first_fail,
        "strip": strip,
        "slowest": max((r.exec_ms for r in results), default=None),
        "beats": _beats(s) if s.verdict == "AC" else None,
        "progress": _progress(s, len(results), total),
        # the limits this run was held to (Python gets its time multiplier), for the usage bars
        "limits": {"ms": int(s.problem.tl_ms * s.language.tl_multiplier), "mb": s.problem.ml_mb,
                   "kb": s.problem.ml_mb * 1024},
    }


@login_required
def detail(request, pk):
    s = _own(request, pk)
    ctx = _results_ctx(s)
    # the code with its line numbers beside it, and after an accept the next problem to try
    ctx["line_numbers"] = range(1, len(s.source.splitlines()) + 1)
    # the neighbours among this person's attempts at the same problem, to step back and forth through them
    mine = Submission.objects.filter(
        user_id=s.user_id, problem_id=s.problem_id, contest_id=s.contest_id
    )
    ctx["prev_sub"] = mine.filter(pk__lt=s.pk).order_by("-pk").first()
    ctx["next_sub"] = mine.filter(pk__gt=s.pk).order_by("pk").first()
    if (
        s.user_id == request.user.pk
        and s.verdict == Submission.Verdict.AC
        and s.contest_id is None
    ):
        from apps.problems.skills import next_problems

        picks = next_problems(request.user, n=1, exclude=(s.problem_id,))
        ctx["next_pick"] = picks[0] if picks else None
    return render(request, "submissions/detail.html", ctx)


@login_required
def status(request, pk):
    s = _own(request, pk)
    ctx = _results_ctx(s)
    ctx["compact"] = request.GET.get("compact") == "1"
    if s.user_id == request.user.pk and s.verdict == Submission.Verdict.AC:
        # the accept may have lifted a badge: say so here and now, with the verdict, not on some later page
        from apps.accounts import badges

        badges.award(request.user, {"problems", "learn"})
        ctx["new_badges"] = badges.unseen(request.user)
    return render(request, "submissions/_status.html", ctx)


def mine(request):
    """The status page, after Codeforces': your own submissions, newest first (signed in), or with ?mine=0 everyone's. Other people's rows leave out anything that could give a contest away: problems that aren't
    public, and every problem a running or upcoming contest holds. Only the code stays private (_own).
    Staff see every row; a round's own list is contests:submissions."""
    # Signed-in people land on their own tries; "Hamma" is ?mine=0. Guests only ever see everyone's.
    mine_arg = request.GET.get("mine")
    own = mine_arg == "1" or (mine_arg is None and request.user.is_authenticated)
    if mine_arg == "1" and not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    qs = Submission.objects.select_related("problem", "language", "user")
    if own:
        qs = qs.filter(user=request.user)
    elif not request.user.is_staff:
        qs = qs.filter(problem__is_public=True, user__is_active=True).exclude(
            problem__contests__end__gt=timezone.now()
        )
    # the band's figures, over the whole list (yours or everyone's) before the filters
    total = qs.count()
    accepted = qs.filter(verdict=Submission.Verdict.AC).count()
    stats = {
        "total": total,
        "today": qs.filter(created__date=timezone.localdate()).count(),
        "ac_pct": round(100 * accepted / total) if total else None,
    }
    contest_id = request.GET.get("contest", "")
    if (
        own and contest_id.isdigit()
    ):  # a round's "Urinishlarim" tab: your tries in that round
        qs = qs.filter(contest_id=int(contest_id))
    verdict = request.GET.get("verdict", "")
    if verdict in Submission.TERMINAL:
        qs = qs.filter(verdict=verdict)
    q = request.GET.get("q", "").strip()[:60]
    if q:
        qs = (
            qs.filter(Q(problem__title__icontains=q) | Q(user__username__icontains=q))
            if not own
            else qs.filter(problem__title__icontains=q)
        )
    languages = list(Language.objects.filter(is_active=True).order_by("name"))
    lang = request.GET.get("lang", "")
    if lang.isdigit() and any(str(x.pk) == lang for x in languages):
        qs = qs.filter(language_id=int(lang))
    else:
        lang = ""
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    verdicts = list(VERDICT_LABELS.items())
    return render(
        request,
        "submissions/list.html",
        {
            "subs": page,
            "verdict": verdict,
            "verdicts": verdicts,
            "own": own,
            "stats": stats,
            "q": q,
            "languages": languages,
            "lang": lang,
        },
    )


GUEST_TRIAL_PER_MIN = 6
GUEST_TRIAL_PER_HOUR = 40


@require_POST
def guest_trial(request, slug):
    """"Sinab ko‘rish" without an account: the sample tests only, on an open practice problem, with a tight limit per
    address. Nothing is saved; sign-up is only needed to submit."""
    from apps.accounts import throttle

    if request.user.is_authenticated:
        return JsonResponse({"error": "Tizimga kirgansiz: sahifani yangilang."}, status=400)
    problem = get_object_or_404(Problem, slug=slug, is_public=True)
    from apps.contests.models import ContestProblem
    if problem.kind == Problem.Kind.SQL or ContestProblem.objects.filter(problem=problem, contest__end__gt=timezone.now()).exists():
        return JsonResponse({"error": "Bu masalada sinash uchun ro‘yxatdan o‘ting."}, status=403)
    source = request.POST.get("source", "")
    if not source.strip() or len(source) > MAX_SOURCE:
        return JsonResponse({"error": "Kod bo‘sh yoki juda katta"}, status=400)
    if (throttle.ip_blocked(request, "guest-trial-min", GUEST_TRIAL_PER_MIN, 60)
            or throttle.ip_blocked(request, "guest-trial-hour", GUEST_TRIAL_PER_HOUR, 3600)):
        return JsonResponse({"error": "Juda tez-tez. Ro‘yxatdan o‘tsangiz, limit ancha keng."}, status=429)
    language = get_object_or_404(Language, code=request.POST.get("language"), is_active=True)
    samples = list(problem.samples)
    if not samples:
        return JsonResponse({"error": "Namunaviy test yo‘q"}, status=400)
    job = django_rq.get_queue("run").enqueue(
        run_trial, language.code, source, [t.input for t in samples], [t.expected for t in samples],
        problem.tl_ms, problem.ml_mb, result_ttl=300, failure_ttl=300,
        meta={"guest_ip": request.META.get("REMOTE_ADDR", "")})
    return JsonResponse({"id": job.id})


def guest_trial_status(request, job_id):
    job = django_rq.get_queue("run").fetch_job(job_id)
    if job is None or not job.meta.get("guest_ip") or job.meta["guest_ip"] != request.META.get("REMOTE_ADDR", ""):
        raise Http404
    status = job.get_status()
    if status == "finished":
        return JsonResponse({"done": True, **job.return_value()})
    if status in ("failed", "stopped", "canceled"):
        return JsonResponse({"done": True, "verdict": "IE", "log": "", "cases": []})
    return JsonResponse({"done": False, "status": status})
