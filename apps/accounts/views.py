import datetime
import math

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, F, OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.contests.models import _UZ_MONTHS_SHORT, Participation
from apps.contests.views import _standings  # cached, the standings page's own rows
from apps.learn.models import StudyPlan
from apps.learn.progress import plan_progress
from apps.problems.models import Problem, Tag
from apps.problems.daily import streaks
from apps.problems.progress import solved_ring
from apps.problems.skills import skill_map
from apps.submissions.models import Submission

from .forms import ProfileEditForm, RegisterForm
from .models import User

from .tiers import RATING_TIERS as _RATING_TIERS
from .tiers import next_tier as _next_tier
from .tiers import rating_tier
from .tiers import streak_badges, tier_banner
from .tiers import tier_color as _tier_color

_CHART_W, _CHART_H = 700, 190
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

    gridlines = [{"y": round(y_for(floor), 1), "value": floor}
                 for floor, _ceiling, _name, _color in _RATING_TIERS if floor is not None and lo < floor < hi]
    # The chart's own top and bottom get a label too, unless a tier line sits too close to read both.
    for edge in (hi, lo):
        if all(abs(y_for(edge) - g["y"]) >= 14 for g in gridlines):
            gridlines.append({"y": round(y_for(edge), 1), "value": round(edge)})

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
                # the contest tiles' abbreviations: Iyun and Iyul both cut to "Iyu" otherwise
                month_labels.append({"week": len(weeks) - 1, "name": _UZ_MONTHS_SHORT[day.month - 1]})
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


def _safe_next(request):
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    ok = url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure())
    return nxt if ok else ""


def register(request):
    form = RegisterForm(request.POST or None)
    nxt = _safe_next(request)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        if user.teacher_requested:
            messages.success(request, "Xush kelibsiz! O‘qituvchi so‘rovingiz adminga yuborildi — tasdiqlangach, «Vazifalar» bo‘limida guruh ochasiz.")
        return redirect(nxt or "home")
    return render(request, "registration/register.html", {"form": form, "next": nxt})


class PasswordChange(SuccessMessageMixin, auth_views.PasswordChangeView):
    """Knowing the old password is enough — no email round trip."""
    success_url = reverse_lazy("profile_edit")
    success_message = "Parol almashtirildi."


@login_required
@require_POST
def teacher_request(request):
    user = request.user
    if user.role == User.Role.STUDENT and not user.is_staff and not user.teacher_requested:
        user.teacher_requested = True
        user.save(update_fields=["teacher_requested"])
        messages.success(request, "So‘rov yuborildi. Admin tasdiqlagach, «Vazifalar» bo‘limida guruh ochasiz.")
    return redirect("profile_edit")


@login_required
def profile_edit(request):
    form = ProfileEditForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("profile", request.user.username)
    return render(request, "accounts/profile_edit.html", {"form": form})


def _ranked(page):
    """A leaderboard page with each user's place on the whole board as .rank."""
    for i, u in enumerate(page):
        u.rank = page.start_index() + i
    return page


def practice_board():
    """Who stands on the practice-points board: active non-staff users with points. A 0 says nothing
    about anyone, and the admin account is not a student."""
    return User.objects.filter(is_active=True, is_staff=False, practice_points__gt=0)


def top(request):
    qs = (practice_board().annotate(solved_count=Count("userproblemsolved", distinct=True))
          .order_by("-practice_points", "username"))
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    return render(request, "accounts/top.html", {"users": _ranked(page), "total": qs.count()})


def _rating_spread(ratings: list[int], mine: int | None) -> dict:
    """Server-rendered SVG data for the rating page's histogram: how many people hold each 100 points, a bar per
    step in its tier colour, the scale reaching at least 2000 so the tiers above everyone still show, the
    viewer's own bar marked."""
    step = 100
    end = max(2000, (max(ratings, default=0) // step + 1) * step)
    counts = [0] * (end // step)
    for r in ratings:
        counts[max(r, 0) // step] += 1
    width, room, height = 380, 14, 110  # the drawing, the space over the bars for the "Siz" mark, the tallest bar
    bar = width / len(counts)
    biggest = max(counts) or 1
    bars = []
    for i, n in enumerate(counts):
        lo, h = i * step, round(height * n / biggest, 1)
        bars.append({"x": round(i * bar + 1, 1), "cx": round((i + .5) * bar, 1), "y": round(room + height - h, 1), "h": h, "n": n,
                     "lo": lo, "hi": lo + step - 1, "color": _tier_color(lo),
                     "mine": mine is not None and lo <= max(mine, 0) < lo + step})
    ticks = [{"x": round(v / step * bar, 1), "value": v,
              "anchor": "start" if v == 0 else "end" if v == end else "middle"} for v in range(0, end + 1, 500)]
    return {"w": width, "h": room + height + 16, "base": room + height, "bar_w": round(bar - 2, 1),
            "bars": bars, "ticks": ticks}


def rating(request):
    # Only users who finished a rated contest; a default 0 says nothing about anyone.
    rated = Participation.objects.filter(rating_after__isnull=False)
    last = rated.filter(user=OuterRef("pk")).order_by("-contest__end").annotate(d=F("rating_after") - F("rating_before"))
    qs = (User.objects.filter(is_active=True)
          .annotate(contest_count=Count("participations", filter=Q(participations__rating_after__isnull=False)),
                    last_delta=Subquery(last.values("d")[:1]))
          .filter(contest_count__gt=0).order_by("-rating", "username"))
    ratings = list(qs.values_list("rating", flat=True))  # highest first
    q = request.GET.get("q", "").strip()[:50]
    # the order of the rows only; a place is always the place by rating
    sort = request.GET.get("sort", "")
    order = {"delta": ("-last_delta", "-rating", "username"),
             "contests": ("-contest_count", "-rating", "username")}.get(sort)
    shown = qs.filter(username__icontains=q) if q else qs
    page = Paginator(shown.order_by(*order) if order else shown, 50).get_page(request.GET.get("page"))
    for u in page:  # the place on the whole board, equal ratings sharing it, a search included
        u.rank = sum(1 for r in ratings if r > u.rating) + 1
    tiers = [{"name": n, "color": c, "floor": f, "ceiling": ce,
              "count": sum(1 for r in ratings if (f is None or r >= f) and (ce is None or r < ce))}
             for f, ce, n, c in _RATING_TIERS]
    me = None
    if request.user.is_authenticated:
        mine = rated.filter(user=request.user).order_by("-contest__end").first()
        if mine is not None:
            row = list(qs.values_list("pk", flat=True)).index(request.user.pk)
            me = {"rank": sum(1 for r in ratings if r > request.user.rating) + 1, "page": row // 50 + 1,
                  "delta": mine.rating_after - mine.rating_before, "next": _next_tier(request.user.rating),
                  "contests": rated.filter(user=request.user).count()}
    spread = _rating_spread(ratings, request.user.rating if me else None)
    return render(request, "accounts/rating.html",
                  {"users": page, "total": len(ratings), "tiers": tiers, "spread": spread, "me": me, "q": q,
                   "sort": sort if order else ""})


def _contest_badges(user) -> list[dict]:
    """The badges of published rounds that award one (Contest.badge), for a participant who solved at
    least one of their problems and was not disqualified: a medal for the top three, else how many
    were solved. From the round's own standings, so a voided problem doesn't count."""
    badges = []
    for p in (Participation.objects.filter(user=user, disqualified=False, contest__published_at__isnull=False)
              .exclude(contest__badge="").select_related("contest").order_by("contest__end")):
        row = next((r for r in _standings(p.contest) if r["user"].pk == user.pk), None)
        if row is not None and row["solved"]:
            badges.append({"contest": p.contest, "name": p.contest.badge, "solved": row["solved"],
                           "total": len(row["cells"]), "medal": row["rank"] if row["rank"] <= 3 else None})
    return badges


def _plan_badges(user) -> list:
    """Public study plans the user finished: the quest's earned stages and other plans."""
    plans = list(StudyPlan.objects.filter(is_public=True))
    done = plan_progress(user, plans)
    return [p for p in plans if done[p.pk]["completed"]]


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
        # upcoming-contest problems stay secret here too, same rule as the problem list
        for pr in Problem.objects.filter(is_public=True).exclude(contests__start__gt=timezone.now()).distinct()
        .only("id", "slug", "title", "difficulty").order_by("id")
    ]
    # gauge: one arc per difficulty sharing a 270° sweep on r=54, 4 units of gap between arcs.
    sweep = 270 / len(Problem.Difficulty.choices)
    seg_len = round(2 * math.pi * 54 * sweep / 360 - 4, 1)
    by_diff = []
    for value, label in Problem.Difficulty.choices:
        total = sum(1 for pr, _ in problem_map if pr.difficulty == value)
        # from the map, like the total: a solved problem an upcoming contest holds is out of both
        done = sum(1 for pr, st in problem_map if pr.difficulty == value and st == "solved")
        by_diff.append({
            "key": value, "label": label, "solved": done, "total": total,
            "seg": seg_len, "arc": round(seg_len * done / total, 1) if total else 0,
            "angle": round(135 + sweep * len(by_diff), 1),
        })

    # blocked (inactive) users hold no place on the boards and push nobody down; the
    # rating rank only counts users who finished a rated contest, like /rating
    ranked = User.objects.filter(is_active=True)
    rated = ranked.filter(participations__rating_after__isnull=False).distinct()
    board = practice_board()  # the same people as /top: no points or staff, no place
    total_users, total_rated = board.count(), rated.count()
    rating_rank = points_rank = None
    if profile_user.is_active:
        if board.filter(pk=profile_user.pk).exists():
            points_rank = board.filter(practice_points__gt=profile_user.practice_points).count() + 1
        if rating_history:
            rating_rank = rated.filter(rating__gt=profile_user.rating).count() + 1

    cur_streak, best_streak = streaks(profile_user)
    skill_groups = _skill_groups(profile_user)
    return render(request, "accounts/profile.html", {
        "profile_user": profile_user,
        "total_users": total_users,
        "total_rated": total_rated,
        "rating_rank": rating_rank,
        "points_rank": points_rank,
        "solved": solved,
        "total_public_problems": len(problem_map),
        "solved_shown": sum(1 for _, st in problem_map if st == "solved"),
        "rest": len(problem_map) - sum(1 for _, st in problem_map if st == "solved"),
        # solved problems an upcoming contest holds: in the points (and the count beside them),
        # hidden from the map until the contest starts
        "solved_hidden": len(solved) - sum(1 for _, st in problem_map if st == "solved"),
        "attempting": len(attempted_ids),
        "by_diff": by_diff,
        # LeetCode's ring of what was solved per level, from the same counts
        "ring": solved_ring([{"value": d["key"], "label": d["label"], "done": d["solved"], "total": d["total"]}
                             for d in by_diff if d["total"]]),
        "problem_map": problem_map,
        "tier": rating_tier(profile_user.rating),
        "banner": tier_banner(profile_user.rating),
        "next_tier": _next_tier(profile_user.rating),
        "streak_badges": streak_badges(cur_streak, best_streak),
        "plan_badges": _plan_badges(profile_user),
        "contest_badges": _contest_badges(profile_user),
        "tier_color": _tier_color(profile_user.rating),
        "rating_history": rating_history,
        "max_rating": max((p.rating_after for p in rating_history), default=None),
        "rating_chart": _rating_chart(rating_history) if rating_history else None,
        "activity": _activity_calendar(profile_user),
        "skill_groups": skill_groups,
        # the topics table: one flat list (kind, row), the topics with most problems first
        "topic_rows": [(kind, r) for kind, _label, rows in skill_groups for r in rows],
        "streak": (cur_streak, best_streak),
        "last_delta": rating_history[-1].delta if rating_history else None,
        "top_pct": round(100 * rating_rank / total_rated, 1) if rating_rank and total_rated else None,
        "spark": _sparkline([p.rating_after for p in rating_history[-12:]]),
    })


def _sparkline(values: list[int], w: int = 88, h: int = 28) -> str:
    """SVG polyline points for a small trend line over `values` (needs two or more), else empty."""
    if len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    step = w / (len(values) - 1)
    return " ".join(f"{round(i * step, 1)},{round(2 + (hi - v) / span * (h - 4), 1)}" for i, v in enumerate(values))


def _skill_groups(user) -> list[tuple[str, str, list[dict]]]:
    """skill_map split by topic kind (programming, SQL), empty kinds left out."""
    rows = skill_map(user)
    return [(kind, label, group) for kind, label in Tag.Kind.choices
            if (group := [r for r in rows if r["tag"].kind == kind])]


def honor(request):
    """The honesty rules; a signed-in user accepts them once (POST), and the problem page asks
    before the first submission until they have."""
    if request.method == "POST" and request.user.is_authenticated:
        if not request.user.honor_pledged_at:
            User.objects.filter(pk=request.user.pk).update(honor_pledged_at=timezone.now())
        messages.success(request, "Rahmat! Halol ishlash — eng katta yutuq.")
        nxt = request.POST.get("next", "")
        if not url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
            nxt = "/"
        return redirect(nxt)
    return render(request, "accounts/honor.html", {"next": request.GET.get("next", "")})


@login_required
@require_POST
def verify_user(request, user_id):
    """A teacher (of one of the student's groups) or staff confirms this is the real student.
    Only verified users get an official rating, so it is rebuilt either way."""
    from django.core.exceptions import PermissionDenied
    from django.db import transaction
    from django.http import HttpResponseBadRequest

    from apps.classroom.access import teaches
    from apps.contests.rating import recalc_official
    from apps.integrity import audit

    student = get_object_or_404(User, pk=user_id)
    if not (request.user.is_staff or teaches(request.user, student.pk)):
        raise PermissionDenied
    want = {"1": True, "0": False}.get(request.POST.get("verified"))
    if want is None:
        return HttpResponseBadRequest("verified must be 0 or 1")
    if bool(student.verified_at) != want:
        with transaction.atomic():
            student.verified_at = timezone.now() if want else None
            student.verified_by = request.user if want else None
            student.verified_note = request.POST.get("note", "").strip()[:200] if want else ""
            student.save(update_fields=["verified_at", "verified_by", "verified_note"])
            recalc_official()
            audit.record(request, audit.Action.VERIFY if want else audit.Action.UNVERIFY,
                         subject=student, note=student.verified_note)
        messages.success(request, f"{student.username}: shaxs {'tasdiqlandi' if want else 'tasdig‘i bekor qilindi'}.")
    nxt = _safe_next(request)
    return redirect(nxt) if nxt else redirect("profile", student.username)
