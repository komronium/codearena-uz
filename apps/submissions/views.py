import django_rq
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.contests.models import Participation
from apps.contests.services import access_allowed, active_contest_for, in_running_contest, in_upcoming_contest
from apps.problems.models import Language, Problem
from judge.runner import run_submission, run_trial

from .models import Submission, UserProblemSolved
from .ratelimit import rate_limited

MAX_SOURCE = 64 * 1024
RATE_LIMIT_MAX = 10       # submissions per minute
TRIAL_RATE_MAX = 20       # "Sinab ko'rish" runs per minute: cheaper than a submit, but still a container
MAX_TRIAL_INPUT = 64 * 1024


def _gate(request, slug):
    """(problem, contest, error) for someone about to run code against `slug`."""
    try:
        problem = Problem.objects.get(slug=slug)
    except Problem.DoesNotExist:
        raise Http404
    contest = active_contest_for(request.user, problem)
    is_owner_or_staff = request.user.is_staff or problem.author_id == request.user.id
    if not is_owner_or_staff and ((not problem.is_public and contest is None) or in_upcoming_contest(problem)):
        raise Http404
    # re-check supervised-mode eligibility on every submit, not just at
    # registration — group membership or client IP can change mid-contest.
    if contest is not None and not access_allowed(request.user, contest, request.META.get("REMOTE_ADDR")):
        return problem, contest, HttpResponseBadRequest("not eligible for this contest")
    if contest is not None and Participation.objects.filter(user=request.user, contest=contest, disqualified=True).exists():
        return problem, contest, HttpResponseBadRequest("disqualified from this contest")
    return problem, contest, None


@login_required
@require_POST
def submit(request, slug):
    problem, contest, error = _gate(request, slug)
    if error:
        return error
    if rate_limited(request.user.id, "submit", RATE_LIMIT_MAX):
        return HttpResponse("too many submissions, slow down", status=429)
    language = get_object_or_404(Language, code=request.POST.get("language"), is_active=True)
    source = request.POST.get("source", "")
    if not source.strip() or len(source) > MAX_SOURCE:
        return HttpResponseBadRequest("source empty or too large")
    sub = Submission.objects.create(user=request.user, problem=problem, contest=contest,
                                    language=language, source=source)
    django_rq.enqueue(run_submission, sub.pk)
    return redirect("problems:detail", problem.slug)


@login_required
@require_POST
def trial(request, slug):
    """Run code on the samples (or one custom stdin) without creating a Submission."""
    problem, _, error = _gate(request, slug)
    if error:
        return JsonResponse({"error": error.content.decode()}, status=400)
    if problem.kind == Problem.Kind.SQL:
        return JsonResponse({"error": "SQL masalalarda sinov yo‘q"}, status=400)
    language = get_object_or_404(Language, code=request.POST.get("language"), is_active=True)
    source, stdin = request.POST.get("source", ""), request.POST.get("stdin", "")
    if not source.strip() or len(source) > MAX_SOURCE or len(stdin) > MAX_TRIAL_INPUT:
        return JsonResponse({"error": "Kod bo‘sh yoki juda katta"}, status=400)
    if rate_limited(request.user.id, "trial", TRIAL_RATE_MAX):
        return JsonResponse({"error": "Juda tez-tez — bir daqiqadan keyin urinib ko‘ring"}, status=429)
    if stdin.strip():
        inputs, expected = [stdin], None
    else:
        samples = list(problem.samples)
        if not samples:
            return JsonResponse({"error": "Namunaviy test yo‘q — o‘z inputingizni kiriting"}, status=400)
        inputs, expected = [t.input for t in samples], [t.expected for t in samples]
    job = django_rq.get_queue("run").enqueue(
        run_trial, language.code, source, inputs, expected, problem.tl_ms, problem.ml_mb,
        result_ttl=300, failure_ttl=300, meta={"user_id": request.user.pk})
    return JsonResponse({"id": job.id})


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
    s = get_object_or_404(Submission.objects.select_related("problem", "language", "user"), pk=pk)
    if s.user_id == request.user.pk or request.user.is_staff:
        return s
    if (s.verdict == "AC" and not in_running_contest(s.problem)
            and UserProblemSolved.objects.filter(user=request.user, problem=s.problem).exists()):
        return s
    raise Http404


def _results_ctx(s):
    results = list(s.results.select_related("testcase"))
    first_fail = next((r for r in results if r.verdict != "AC"), None)
    if first_fail is not None:
        first_fail.index = results.index(first_fail) + 1
    total = s.total or s.problem.testcases.count()
    return {"s": s, "results": results, "first_fail": first_fail,
            "progress": {"done": len(results), "total": total,
                         "pct": int(len(results) * 100 / total) if total else 0}}


@login_required
def detail(request, pk):
    return render(request, "submissions/detail.html", _results_ctx(_own(request, pk)))


@login_required
def status(request, pk):
    ctx = _results_ctx(_own(request, pk))
    ctx["compact"] = request.GET.get("compact") == "1"
    return render(request, "submissions/_status.html", ctx)


@login_required
def mine(request):
    qs = Submission.objects.filter(user=request.user).select_related("problem", "language")
    verdict = request.GET.get("verdict", "")
    if verdict in Submission.TERMINAL:
        qs = qs.filter(verdict=verdict)
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    verdicts = [("AC", "AC"), ("WA", "WA"), ("TLE", "TL"), ("MLE", "ML"), ("OLE", "OL"), ("RE", "RE"), ("CE", "CE")]
    return render(request, "submissions/list.html", {"subs": page, "verdict": verdict, "verdicts": verdicts})
