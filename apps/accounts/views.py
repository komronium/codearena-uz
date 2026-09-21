import datetime

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.contests.models import Participation
from apps.problems.models import Problem
from apps.submissions.models import Submission

from .forms import ProfileEditForm, RegisterForm
from .models import User

_UZ_MONTHS = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
              "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"]

# (floor, ceiling, name, color) — floor None = -inf, ceiling None = +inf.
_RATING_TIERS = [
    (None, 1300, "Newbie", "#6B7280"),
    (1300, 1500, "Pupil", "#16A34A"),
    (1500, 1700, "Specialist", "#06B6D4"),
    (1700, 1900, "Expert", "#3B82F6"),
    (1900, 2100, "Candidate Master", "#8B5CF6"),
    (2100, 2300, "Master", "#D97706"),
    (2300, 2400, "International Master", "#EA580C"),
    (2400, None, "Grandmaster", "#DC2626"),
]


def rating_tier(rating: int) -> str:
    for floor, ceiling, name, _color in _RATING_TIERS:
        if (floor is None or rating >= floor) and (ceiling is None or rating < ceiling):
            return name
    return _RATING_TIERS[-1][2]


def _tier_color(rating: int) -> str:
    for floor, ceiling, _name, color in _RATING_TIERS:
        if (floor is None or rating >= floor) and (ceiling is None or rating < ceiling):
            return color
    return _RATING_TIERS[-1][3]


_CHART_W, _CHART_H = 700, 220
_CHART_L, _CHART_R = 56, 680
_CHART_TOP, _CHART_BOTTOM = 10, 165


def _rating_chart(history: list) -> dict:
    """Server-rendered SVG data for a rank-tier-banded rating chart. Plain SVG
    like the old sparkline — no charting library needed for a line+bands plot."""
    ratings = [p.rating_after for p in history]
    lo, hi = min(ratings), max(ratings)
    pad = max(50, int((hi - lo) * 0.15))
    lo, hi = lo - pad, hi + pad
    span = hi - lo or 1

    def y_for(rating):
        return _CHART_TOP + (hi - rating) / span * (_CHART_BOTTOM - _CHART_TOP)

    bands = []
    for floor, ceiling, name, color in _RATING_TIERS:
        seg_lo = lo if floor is None else max(floor, lo)
        seg_hi = hi if ceiling is None else min(ceiling, hi)
        if seg_hi <= seg_lo:
            continue
        y_top, y_bottom = y_for(seg_hi), y_for(seg_lo)
        bands.append({
            "y": round(y_top, 1), "h": round(y_bottom - y_top, 1),
            "color": color, "label": name if y_bottom - y_top >= 14 else "",
        })

    gridlines = []
    for floor, _ceiling, _name, _color in _RATING_TIERS:
        if floor is not None and lo < floor < hi:
            gridlines.append({"y": round(y_for(floor), 1), "value": floor})
    gridlines.append({"y": round(y_for(hi), 1), "value": round(hi)})
    gridlines.append({"y": round(y_for(lo), 1), "value": round(lo)})

    n = len(history)
    step = (_CHART_R - _CHART_L) / (n - 1) if n > 1 else 0
    points = []
    for i, p in enumerate(history):
        x = _CHART_L + i * step if n > 1 else (_CHART_L + _CHART_R) / 2
        points.append({
            "x": round(x, 1), "y": round(y_for(p.rating_after), 1),
            "color": _tier_color(p.rating_after),
            "date": p.contest.end.strftime("%d.%m.%y"),
        })
    polyline = " ".join(f"{pt['x']},{pt['y']}" for pt in points)

    return {
        "w": _CHART_W, "h": _CHART_H, "left": _CHART_L, "right": _CHART_R,
        "width": _CHART_R - _CHART_L, "top": _CHART_TOP, "bottom": _CHART_BOTTOM,
        "bands": bands, "gridlines": gridlines, "points": points, "polyline": polyline,
    }


def _activity_level(count: int) -> int:
    if count == 0:
        return 0
    if count <= 1:
        return 1
    if count <= 3:
        return 2
    if count <= 6:
        return 3
    return 4


def _activity_calendar(user: User) -> dict:
    """Past-year heatmap: week columns (Mon..Sun) ending today, plus summary stats."""
    today = timezone.localdate()
    first = today - datetime.timedelta(days=364)
    first -= datetime.timedelta(days=first.weekday())  # align to Monday
    counts = dict(
        Submission.objects.filter(user=user, created__date__gte=first)
        .values("created__date")
        .annotate(n=Count("id"))
        .values_list("created__date", "n")
    )
    weeks, month_labels = [], []
    streak = max_streak = 0
    day = first
    while day <= today:
        if day.weekday() == 0:
            weeks.append([])
            if day.day <= 7:
                month_labels.append({"week": len(weeks) - 1, "name": _UZ_MONTHS[day.month - 1][:3]})
        n = counts.get(day, 0)
        streak = streak + 1 if n else 0
        max_streak = max(max_streak, streak)
        weeks[-1].append({"date": day, "level": _activity_level(n), "count": n})
        day += datetime.timedelta(days=1)
    return {
        "weeks": weeks,
        "month_labels": month_labels,
        "total": sum(counts.values()),
        "active_days": len(counts),
        "max_streak": max_streak,
    }


def register(request):
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("problems:list")
    return render(request, "registration/register.html", {"form": form})


@login_required
def profile_edit(request):
    form = ProfileEditForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("profile", request.user.username)
    return render(request, "accounts/profile_edit.html", {"form": form})


def top(request):
    qs = (User.objects.annotate(solved_count=Count("userproblemsolved", distinct=True))
          .order_by("-practice_points", "username"))
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    return render(request, "accounts/top.html", {"users": page, "total": qs.count()})


def rating(request):
    qs = (User.objects.annotate(contest_count=Count("participations", filter=Q(participations__rating_after__isnull=False)))
          .order_by("-rating", "username"))
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    tiers = [{"name": n, "color": c, "floor": f, "ceiling": ce} for f, ce, n, c in _RATING_TIERS]
    return render(request, "accounts/rating.html", {"users": page, "total": qs.count(), "tiers": tiers})


def profile(request, username):
    profile_user = get_object_or_404(User, username=username)
    solved = Problem.objects.filter(userproblemsolved__user=profile_user, is_public=True).order_by("title")
    rating_history = list(
        Participation.objects.filter(user=profile_user, rating_after__isnull=False)
        .select_related("contest")
        .annotate(n_participants=Count("contest__participations",
                                       filter=Q(contest__participations__rating_after__isnull=False)))
        .order_by("contest__end")
    )
    for p in rating_history:
        p.delta = p.rating_after - p.rating_before

    solved_ids = {p.id for p in solved}
    attempted_ids = set(
        Submission.objects.filter(user=profile_user).exclude(problem_id__in=solved_ids)
        .values_list("problem_id", flat=True).distinct()
    )
    # ponytail: full public list in one query; paginate the map if catalog grows past ~1k.
    problem_map = [
        (pr, "solved" if pr.id in solved_ids else "attempted" if pr.id in attempted_ids else "todo")
        for pr in Problem.objects.filter(is_public=True).only("id", "slug", "title", "difficulty").order_by("id")
    ]
    by_diff = []
    for value, label in Problem.Difficulty.choices:
        total = sum(1 for pr, _ in problem_map if pr.difficulty == value)
        done = sum(1 for pr in solved if pr.difficulty == value)
        by_diff.append({
            "key": value, "label": label, "solved": done, "total": total,
            # gauge: 5 equal 54° arcs on r=54 (arc length 50.9 each, 4 gap); start angle 135° + i*54.
            "arc": round(46.9 * done / total, 1) if total else 0,
            "angle": 135 + 54 * len(by_diff),
        })

    total_users = User.objects.count()
    rating_rank = User.objects.filter(rating__gt=profile_user.rating).count() + 1
    points_rank = User.objects.filter(practice_points__gt=profile_user.practice_points).count() + 1

    return render(request, "accounts/profile.html", {
        "profile_user": profile_user,
        "total_users": total_users,
        "rating_rank": rating_rank,
        "points_rank": points_rank,
        "solved": solved,
        "total_public_problems": len(problem_map),
        "attempting": len(attempted_ids),
        "by_diff": by_diff,
        "problem_map": problem_map,
        "tier": rating_tier(profile_user.rating),
        "tier_color": _tier_color(profile_user.rating),
        "rating_history": rating_history,
        "rating_chart": _rating_chart(rating_history) if rating_history else None,
        "activity": _activity_calendar(profile_user),
    })
