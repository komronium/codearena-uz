from django.contrib.auth import login
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from apps.contests.models import Participation
from apps.problems.models import Problem

from .forms import RegisterForm
from .models import User

_SPARK_W, _SPARK_H, _SPARK_PAD = 640, 120, 8


def _rating_sparkline_points(ratings: list[int]) -> str:
    """SVG polyline points for a rating-history sparkline. Plain SVG, no chart lib."""
    if not ratings:
        return ""
    lo, hi = min(ratings), max(ratings)
    span = hi - lo or 1
    n = len(ratings)
    step = (_SPARK_W - 2 * _SPARK_PAD) / (n - 1) if n > 1 else 0
    coords = []
    for i, r in enumerate(ratings):
        x = _SPARK_PAD + i * step
        y = _SPARK_H - _SPARK_PAD - (r - lo) / span * (_SPARK_H - 2 * _SPARK_PAD)
        coords.append(f"{x:.1f},{y:.1f}")
    return " ".join(coords)


def register(request):
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("problems:list")
    return render(request, "registration/register.html", {"form": form})


def top(request):
    qs = User.objects.order_by("-practice_points", "username")
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    return render(request, "accounts/top.html", {"users": page})


def rating(request):
    qs = User.objects.order_by("-rating", "username")
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    return render(request, "accounts/rating.html", {"users": page})


def profile(request, username):
    profile_user = get_object_or_404(User, username=username)
    solved = Problem.objects.filter(userproblemsolved__user=profile_user, is_public=True).order_by("title")
    rating_history = list(
        Participation.objects.filter(user=profile_user, rating_after__isnull=False)
        .select_related("contest").order_by("contest__end")
    )
    for p in rating_history:
        p.delta = p.rating_after - p.rating_before
    return render(request, "accounts/profile.html", {
        "profile_user": profile_user,
        "solved": solved,
        "rating_history": rating_history,
        "rating_points": _rating_sparkline_points([p.rating_after for p in rating_history]),
        "spark_w": _SPARK_W,
        "spark_h": _SPARK_H,
    })
