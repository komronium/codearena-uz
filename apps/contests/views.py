from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Contest, Participation
from .standings import compute_standings


def contest_list(request):
    contests = Contest.objects.order_by("-start")
    return render(request, "contests/list.html", {"contests": contests})


def contest_detail(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    problems = contest.contest_problems.select_related("problem")
    registered = (
        request.user.is_authenticated
        and Participation.objects.filter(user=request.user, contest=contest).exists()
    )
    return render(request, "contests/detail.html", {
        "contest": contest, "problems": problems, "registered": registered,
    })


@login_required
@require_POST
def register(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    if contest.has_ended:
        return HttpResponseBadRequest("contest has ended")
    Participation.objects.get_or_create(user=request.user, contest=contest)
    return redirect("contests:detail", pk=pk)


def standings(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    cache_key = f"contest-standings-{pk}"
    rows = cache.get(cache_key)
    if rows is None:
        rows = compute_standings(contest)
        cache.set(cache_key, rows, 30)
    return render(request, "contests/standings.html", {"contest": contest, "rows": rows})
