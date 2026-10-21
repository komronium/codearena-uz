import datetime
import math

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Max, OuterRef, Q, Subquery, Window
from django.db.models.functions import Rank
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.contests.models import _UZ_MONTHS_SHORT, Participation
from apps.contests.views import _standings  # cached, the standings page's own rows
from apps.problems.models import Problem, Tag
from apps.problems.daily import streaks
from apps.problems.progress import solved_ring
from apps.problems.skills import skill_map
from apps.submissions.models import Submission

from . import onboarding, throttle
from .forms import ProfileEditForm, RegisterForm, WelcomeForm
from .geo import board_geo
from .models import Follow, Notification, TelegramLink, User

from .tiers import RATING_TIERS as _RATING_TIERS
from .tiers import next_tier as _next_tier
from .tiers import rating_tier
from . import badges as badge_system
from .tiers import tier_banner
from .tiers import tier_color as _tier_color
from .telegram import bot_configured
from django.utils.translation import gettext as _t
from django.utils.translation import gettext as _t

_CHART_W, _CHART_H = 640, 300
_CHART_L, _CHART_R = 46, 600
_CHART_TOP, _CHART_BOTTOM = 14, 268


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
        nice = round(edge / 10) * 10  # 1271 reads as 1270, at the place 1270 has
        if lo <= nice <= hi and all(abs(y_for(nice) - g["y"]) >= 14 for g in gridlines):
            gridlines.append({"y": round(y_for(nice), 1), "value": nice})

    n = len(history)
    step = (_CHART_R - _CHART_L) / (n - 1) if n > 1 else 0
    points = []
    for i, p in enumerate(history):
        x = _CHART_L + i * step if n > 1 else (_CHART_L + _CHART_R) / 2
        points.append({
            "x": round(x, 1), "y": round(y_for(p.rating_after), 1),
            "color": _tier_color(p.rating_after),
            "date": p.contest.end.strftime("%d.%m.%y"),
            # what the point's hover card says: the round, the place, the change, the rating after it
            "title": getattr(p.contest, "title", ""), "rank": getattr(p, "rank", None), "of": getattr(p, "n_participants", None),
            "delta": p.rating_after - getattr(p, "rating_before", p.rating_after), "rating": p.rating_after,
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
    """Past-year heatmap: week columns (Mon..Sun) from this day last year to today, plus summary stats."""
    today = timezone.localdate()
    try:
        first = today.replace(year=today.year - 1)
    except ValueError:  # 29 February
        first = today.replace(year=today.year - 1, day=28)
    counts = dict(
        Submission.objects.filter(user=user, created__date__gte=first)
        .values("created__date")
        .annotate(n=Count("id"))
        .values_list("created__date", "n")
    )
    weeks, month_labels = [[None] * first.weekday()], []  # the first week starts blank up to the first day
    streak = max_streak = 0
    day = first
    while day <= today:
        if day.weekday() == 0 and day != first:
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
        "weeks": weeks, "first": first, "last": today,
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
    if request.GET.get("ref"):
        request.session["ref"] = request.GET["ref"].strip()[:150]
    if request.method == "POST":
        # a bot fills the hidden "website" field; a person never sees it. Per address, a class of students fits.
        if request.POST.get("website") or throttle.ip_blocked(request, "register", 40, 3600):
            form.add_error(None, throttle.TOO_MANY)
            return render(request, "registration/register.html", {"form": form, "next": nxt}, status=429)  # (no Google button here)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                user = form.save()
        except IntegrityError:
            # A concurrent signup can pass the form's uniqueness checks before the other
            # request commits. Turn that race into an ordinary validation error, not a 500.
            if User.objects.filter(username__iexact=form.cleaned_data["username"]).exists():
                form.add_error("username", _t("Bu foydalanuvchi nomi band."))
            elif User.objects.filter(email__iexact=form.cleaned_data["email"]).exists():
                form.add_error("email", _t("Bu email allaqachon ro‘yxatdan o‘tgan."))
            else:
                form.add_error(None, _t("Ro‘yxatdan o‘tishda xatolik yuz berdi. Qayta urinib ko‘ring."))
        else:
            inviter = User.objects.filter(username__iexact=request.session.pop("ref", ""), is_active=True).exclude(pk=user.pk).first()
            if inviter:
                User.objects.filter(pk=user.pk).update(invited_by=inviter)
            login(request, user)
            onboarding.send_verification(request, user, force=True)
            return redirect(nxt or "home")
    from . import google
    return render(request, "registration/register.html", {"form": form, "next": nxt, "google_login": google.configured()})


class Login(auth_views.LoginView):
    """The sign-in page, with "Telegram orqali kirish" offered once the bot is set up."""

    def get_context_data(self, **kwargs):
        from . import google
        from .telegram import bot_configured
        return super().get_context_data(**kwargs, telegram_login=bot_configured(), google_login=google.configured())

    def post(self, request, *args, **kwargs):
        who = (request.POST.get("username") or "").strip().lower()[:150]
        if throttle.ip_blocked(request, "login", 60, 600) or (who and throttle.blocked(f"thr:login-who:{who}", 10, 600)):
            form = self.get_form()
            return self.render_to_response(self.get_context_data(form=form, throttled=True), status=429)
        return super().post(request, *args, **kwargs)


class PasswordReset(auth_views.PasswordResetView):
    """The reset mail, at most a few per address and per mailbox an hour (it spends the mail quota)."""

    def post(self, request, *args, **kwargs):
        who = (request.POST.get("email") or "").strip().lower()[:254]
        if throttle.ip_blocked(request, "reset", 10, 3600) or (who and throttle.blocked(f"thr:reset-who:{who}", 3, 3600)):
            form = self.get_form()
            form.add_error(None, throttle.TOO_MANY)
            return self.render_to_response(self.get_context_data(form=form), status=429)
        return super().post(request, *args, **kwargs)


class PasswordChange(SuccessMessageMixin, auth_views.PasswordChangeView):
    """Knowing the old password is enough — no email round trip."""
    success_url = reverse_lazy("profile_edit")
    success_message = "Parol almashtirildi."


@login_required
def profile_edit(request):
    # a fresh copy: a form that fails must not leave its values on request.user (the top bar shows it)
    user = User.objects.get(pk=request.user.pk)
    old_name, old_email = user.username, user.email.lower()
    form = ProfileEditForm(request.POST or None, request.FILES or None, instance=user)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        if user.username != old_name:
            user.username_changed_at = timezone.now()
        email_changed = user.email.lower() != old_email
        if email_changed:
            user.email_verified_at = None
        user.save()
        if email_changed:
            onboarding.send_verification(request, user, force=True)
            messages.info(request, f"{user.email} manziliga tasdiqlash havolasi yuborildi.")
        return redirect("profile", user.username)
    return render(request, "accounts/profile_edit.html", {
        "form": form,
        "telegram_link": TelegramLink.objects.filter(user=request.user).first(),
        "telegram_configured": bot_configured(),
        "invited_count": user.invited_users.count(),
    })


@login_required
def welcome(request):
    """The account gate's page (apps.accounts.onboarding): the profile fields still empty, then the email
    confirmation. A user with nothing owed goes home."""
    user = request.user
    if not onboarding.needs_gate(user):
        return redirect(request.session.pop("gate_next", None) or "home")
    old_email = user.email.lower()
    form = WelcomeForm(request.POST or None, instance=User.objects.get(pk=user.pk))
    if request.method == "POST" and "resend" in request.POST:
        if throttle.ip_blocked(request, "verify-mail", 20, 3600):
            messages.warning(request, throttle.TOO_MANY)
        elif onboarding.send_verification(request, user):
            messages.success(request, _t("Havola {user_email} manziliga qayta yuborildi.").format(user_email=user.email))
        else:
            messages.warning(request, _t("Havola hozirgina yuborildi. Bir daqiqadan keyin qayta urinib ko‘ring."))
        return redirect("welcome")
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        email_changed = user.email.lower() != old_email
        if email_changed:
            user.email_verified_at = None
        user.save()
        if user.email_verified_at is None:
            onboarding.send_verification(request, user, force=email_changed)
        return redirect("welcome")
    return render(request, "accounts/welcome.html", {
        "form": form, "missing": onboarding.missing(user), "email_pending": not onboarding.missing(user)})


@login_required
def notification_open(request, pk):
    """A line in the bell: mark it read and go where it points."""
    n = get_object_or_404(Notification, pk=pk, user=request.user)
    if n.read_at is None:
        n.read_at = timezone.now()
        n.save(update_fields=["read_at"])
    return redirect(n.url if n.url.startswith("/") else "home")


@login_required
@require_POST
def notifications_read(request):
    """The bell's "Hammasini o‘qildi": every unread line read at once."""
    Notification.objects.filter(user=request.user, read_at__isnull=True).update(read_at=timezone.now())
    return redirect(_safe_next(request) or "home")


def verify_email(request, token):
    """The link from the confirmation mail. Works signed in or not (the mail may be opened on a phone)."""
    data = onboarding.read_token(token)
    user = data and User.objects.filter(pk=data[0], is_active=True).first()
    if not user or not onboarding.confirm(user, data[1]):
        messages.error(request, _t("Havola eskirgan yoki noto‘g‘ri. Yangi havola so‘rang."))
        return redirect("welcome" if request.user.is_authenticated else "login")
    messages.success(request, "Email tasdiqlandi. Xush kelibsiz!")
    if request.user.is_authenticated and request.user.pk == user.pk:
        return redirect("home")
    return redirect("login")


def practice_board():
    """Who stands on the practice-points board: active non-staff users with points. A 0 says nothing
    about anyone, and the admin account is not a student."""
    return User.objects.filter(is_active=True, is_staff=False, practice_points__gt=0)


def top(request):
    """The practice-points board. Equal points share a place (two people on 1650 are both 4th), and a search shows
    each match with the place they hold on the whole board."""
    q = request.GET.get("q", "").strip()[:40]
    everyone = practice_board()
    cond, geo = board_geo(request, list(everyone.values_list("country", "location", "school")))
    board = everyone.filter(**cond)  # a place filter makes the places those within the group
    qs = (board.annotate(solved_count=Count("userproblemsolved", distinct=True),
                         rank=Window(expression=Rank(), order_by=F("practice_points").desc()))
          .order_by("-practice_points", "username"))
    if q:
        found = list(qs.filter(username__icontains=q)[:50])
        for u in found:  # the window ran over the filtered rows: count the places above on the whole board
            u.rank = board.filter(practice_points__gt=u.practice_points).count() + 1
        return render(request, "accounts/top.html", {"users": found, "total": board.count(), "q": q, "found": len(found), **geo})
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    return render(request, "accounts/top.html", {"users": page, "total": qs.count(), "q": "", **geo})


@login_required
def feed(request):
    """Do‘stlar: what the people you follow and your classmates did in the last two weeks."""
    from . import feed as feeds

    people = feeds.circle(request.user)
    suggestions = (User.objects.filter(is_active=True, is_staff=False).exclude(pk__in=people | {request.user.pk})
                   .order_by("-rating")[:5]) if len(people) < 5 else []
    return render(request, "accounts/feed.html", {"events": feeds.events(request.user), "n_circle": len(people),
                                                 "suggestions": suggestions, "days": feeds.DAYS})


@login_required
@require_POST
def follow_toggle(request, username):
    from .models import Follow

    target = get_object_or_404(User, username=username, is_active=True)
    if target.pk == request.user.pk:
        return redirect("profile", username)
    link, created = Follow.objects.get_or_create(user=request.user, target=target)
    if not created:
        link.delete()
    return redirect("profile", username)


def duel_board(request):
    """Everyone with a finished duel, by duel rating (its own Elo; the contest rating is untouched). The rating is the
    one for the running season: a month that began since someone's last duel has already pulled theirs back."""
    from collections import Counter

    from apps.classroom import duels as duel_rules
    from apps.classroom.models import Duel, DuelSeasonResult
    duel_rules.close_seasons()
    season = duel_rules.current_season()
    played, wins = Counter(), Counter()
    for challenger, opponent, winner in Duel.objects.filter(status=Duel.Status.FINISHED, mode=Duel.Mode.QUIZ).values_list(
            "challenger_id", "opponent_id", "winner_id"):
        played.update((challenger, opponent))
        if winner:
            wins[winner] += 1
    played.pop(None, None)
    people = list(User.objects.filter(pk__in=played, is_active=True))
    for u in people:
        u.eff = duel_rules.carried(u.duel_rating, u.duel_season, season)
    people.sort(key=lambda u: (-u.eff, u.username))
    q = request.GET.get("q", "").strip()[:40]
    cond, geo = board_geo(request, [(u.country, u.location, u.school) for u in people])
    scope = [u for u in people if all(getattr(u, k) == v for k, v in cond.items())]  # a place filter: places within it
    shown = [u for u in scope if q.lower() in u.username.lower()] if q else scope
    page = Paginator(shown, 50).get_page(request.GET.get("page"))
    users = page
    effs = [p.eff for p in scope]
    for u in users:  # equal duel ratings share a place, as on every other board ("1, 2, 2, 2, 5")
        u.rank = sum(1 for e in effs if e > u.eff) + 1
        u.duels, u.wins = played[u.pk], wins[u.pk]
    podium_season = (DuelSeasonResult.objects.filter(rank__gt=0).order_by("-season").values_list("season", flat=True).first())
    podium = list(DuelSeasonResult.objects.filter(season=podium_season, rank__gt=0).select_related("user")) if podium_season else []
    return render(request, "accounts/duel_board.html", {
        "users": users, "total": len(scope), "found": len(shown), "q": q, "season": season,
        "season_ends": duel_rules.season_ends(),
        "podium": podium, "podium_season": podium_season, "min_duels": duel_rules.SEASON_MIN_DUELS, **geo})


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


from apps.contests.rating import INACTIVE_DAYS  # no rated contest for this long: off the board (the rating is kept)


def _board_cutoff():
    return timezone.now() - datetime.timedelta(days=INACTIVE_DAYS)


def rating(request):
    # Only users who finished a rated contest lately; a default 0 says nothing about anyone, and a rating that
    # nobody has earned for INACTIVE_DAYS days holds no place.
    rated = Participation.objects.filter(rating_after__isnull=False)
    last = rated.filter(user=OuterRef("pk")).order_by("-contest__end").annotate(d=F("rating_after") - F("rating_before"))
    qs = (User.objects.filter(is_active=True)
          .annotate(contest_count=Count("participations", filter=Q(participations__rating_after__isnull=False)),
                    last_delta=Subquery(last.values("d")[:1]),
                    last_rated=Max("participations__contest__end", filter=Q(participations__rating_after__isnull=False)))
          .filter(contest_count__gt=0, last_rated__gte=_board_cutoff()).order_by("-rating", "username"))
    rows = list(qs.values_list("rating", "country", "location", "school"))  # highest first
    everyone = [r[0] for r in rows]
    cond, geo = board_geo(request, [r[1:] for r in rows])
    scope = qs.filter(**cond) if cond else qs  # a place filter makes the places those within the group
    ratings = list(scope.values_list("rating", flat=True)) if cond else everyone
    q = request.GET.get("q", "").strip()[:50]
    # the order of the rows only; a place is always the place by rating
    sort = request.GET.get("sort", "")
    order = {"delta": ("-last_delta", "-rating", "username"),
             "contests": ("-contest_count", "-rating", "username")}.get(sort)
    shown = scope.filter(username__icontains=q) if q else scope
    tier_sel = request.GET.get("tier", "")
    band = next(((f, ce) for f, ce, n, _c in _RATING_TIERS if n == tier_sel), None)
    if band:  # one tier's players; the places stay the places on the whole board
        lo, hi = band
        shown = shown.filter(rating__gte=lo if lo is not None else -10**9, rating__lt=hi if hi is not None else 10**9)
    else:
        tier_sel = ""
    page = Paginator(shown.order_by(*order) if order else shown, 50).get_page(request.GET.get("page"))
    sums = badge_system.summaries([u.pk for u in page])
    for u in page:  # the place on the whole board, equal ratings sharing it, a search included
        u.rank = sum(1 for r in ratings if r > u.rating) + 1
        u.badge_sum = sums.get(u.pk)
    tiers = [{"name": n, "color": c, "floor": f, "ceiling": ce,
              "count": sum(1 for r in ratings if (f is None or r >= f) and (ce is None or r < ce))}
             for f, ce, n, c in _RATING_TIERS]
    me = None
    if request.user.is_authenticated:
        mine = rated.filter(user=request.user).order_by("-contest__end").first()
        if mine is not None:
            for t in tiers:  # how far through your own tier you are, for the bar in its tile
                lo, hi = t["floor"] or 0, t["ceiling"]
                if request.user.rating >= lo and (hi is None or request.user.rating < hi):
                    t["here"] = True
                    t["pct"] = round(100 * (request.user.rating - lo) / (hi - lo)) if hi else 100
            pks = list(qs.values_list("pk", flat=True))
            row = pks.index(request.user.pk) if request.user.pk in pks else None  # None: inactive, no place
            me = None if row is None else {"rank": sum(1 for r in everyone if r > request.user.rating) + 1, "page": row // 50 + 1,
                  "delta": mine.rating_after - mine.rating_before, "next": _next_tier(request.user.rating),
                  "contests": rated.filter(user=request.user).count()}
    spread = _rating_spread(ratings, request.user.rating if me else None)
    return render(request, "accounts/rating.html",
                  {"users": page, "total": len(ratings), "tiers": tiers, "spread": spread, "me": me, "q": q,
                   "sort": sort if order else "", "tier_sel": tier_sel, **geo})


def badges_page(request):
    """Nishonlar: every badge with all its levels, what each takes and how rare it is, in two sections; for a
    signed-in user where they stand, their place on the badge board and the three badges closest to a new level."""
    families = badge_system.ladders(request.user)
    groups = [{"label": label, "families": [f for f in families if f["section"] == i]}
              for i, label in enumerate(badge_system.SECTIONS)]
    me, near = None, []
    if request.user.is_authenticated:
        mine = badge_system.summaries([request.user.pk]).get(request.user.pk, {"count": 0, "levels": 0})
        board = _badge_ranking()
        me = {**mine, "rank": next((r["rank"] for r in board if r["user"] == request.user.pk), None),
              "max_levels": sum(len(f.levels) for f in badge_system.FAMILIES)}
        near = sorted((f for f in families if f["mine"] and f["mine"]["next"] and f["mine"]["next"]["done"] > 0),
                      key=lambda f: -f["mine"]["next"]["done"] / f["mine"]["next"]["total"])[:3]
    return render(request, "accounts/badges.html", {"groups": groups, "me": me, "near": near,
                                                     "n_families": len(families), "metals": badge_system.METALS[1:]})


def _badge_ranking() -> list[dict]:
    """Everyone with a badge, by levels earned, then badges held, then who got there first; equal levels and
    badges share a place."""
    from django.db.models import Max

    from .models import UserBadge

    rows = list(UserBadge.objects.filter(user__is_active=True, user__is_staff=False).values("user")
                .annotate(levels=Count("id"), families=Count("family", distinct=True), last=Max("earned_at"))
                .order_by("-levels", "-families", "last", "user"))
    for i, r in enumerate(rows):
        same = i and (rows[i - 1]["levels"], rows[i - 1]["families"]) == (r["levels"], r["families"])
        r["rank"] = rows[i - 1]["rank"] if same else i + 1
    return rows


def badge_board(request):
    """The rating by badges: levels earned across all badges, each player's best badges beside them."""
    everyone = _badge_ranking()
    people = User.objects.in_bulk([r["user"] for r in everyone])
    q = request.GET.get("q", "").strip()[:40]
    cond, geo = board_geo(request, [(u.country, u.location, u.school) for u in people.values()])
    rows = [r for r in everyone if all(getattr(people[r["user"]], k) == v for k, v in cond.items())]  # places within it
    if cond:  # the places of the group, not of the whole board
        for i, r in enumerate(rows):
            same = i and (rows[i - 1]["levels"], rows[i - 1]["families"]) == (r["levels"], r["families"])
            r["rank"] = rows[i - 1]["rank"] if same else i + 1
    shown = [r for r in rows if q.lower() in people[r["user"]].username.lower()] if q else rows
    page = Paginator(shown, 50).get_page(request.GET.get("page"))
    users = {pk: people[pk] for pk in (r["user"] for r in page)}
    sums = badge_system.summaries(users)
    for r in page:
        r["u"], r["badges"] = users[r["user"]], sums.get(r["user"], {}).get("badges", [])
    me = next((r for r in rows if request.user.is_authenticated and r["user"] == request.user.pk), None)
    return render(request, "accounts/badge_board.html", {
        "rows": page, "total": len(rows), "found": len(shown), "q": q, **geo,
        "me": me, "me_page": (rows.index(me) // 50 + 1) if me else None,
        "max_levels": sum(len(f.levels) for f in badge_system.FAMILIES)})


def _contest_badges(user) -> list[dict]:
    """The badges of published rounds that award one (Contest.badge), for a participant who solved at
    least one of their problems and was not disqualified: a medal for the top three, else how many
    were solved. From the round's own standings, so a voided problem doesn't count."""
    badges = []
    for p in (Participation.objects.filter(user=user, disqualified=False, contest__published_at__isnull=False)
              .exclude(contest__badge="").select_related("contest").order_by("contest__end")):
        row = next((r for r in _standings(p.contest) if r["user"].pk == user.pk), None)
        if row is not None and row["solved"] and not row["author"]:  # a round's author is out of competition: no badge
            badges.append({"contest": p.contest, "name": p.contest.badge, "solved": row["solved"],
                           "total": len(row["cells"]), "medal": row["rank"] if row["rank"] <= 3 else None})
    return badges


def _badges(user, owner: bool) -> dict:
    """The profile's badges by group: every family for the owner (the ones not reached yet locked, with the
    way to level I), only the reached ones for anyone else."""
    board = badge_system.board(user)
    groups = []
    for b in board:
        if not (b["tier"] or owner):
            continue
        if not groups or groups[-1]["label"] != b["group_label"]:
            groups.append({"label": b["group_label"], "badges": []})
        groups[-1]["badges"].append(b)
    earned = sorted((b for b in board if b["tier"]), key=lambda b: -b["tier"])
    return {"badge_groups": groups, "held_badges": earned, "badge_owner": owner, "badges_total": len(board), "top_badges": earned[:6],
            "badges_earned": sum(1 for b in board if b["tier"]), "levels_earned": sum(b["tier"] for b in board)}


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
    rated = ranked.filter(participations__rating_after__isnull=False,
                          participations__contest__end__gte=_board_cutoff()).distinct()  # active ones, like /rating
    board = practice_board()  # the same people as /top: no points or staff, no place
    total_users, total_rated = board.count(), rated.count()
    rating_rank = points_rank = None
    if profile_user.is_active:
        if board.filter(pk=profile_user.pk).exists():
            points_rank = board.filter(practice_points__gt=profile_user.practice_points).count() + 1
        if rating_history and rated.filter(pk=profile_user.pk).exists():
            rating_rank = rated.filter(rating__gt=profile_user.rating).count() + 1

    cur_streak, best_streak = streaks(profile_user)
    skill_groups = _skill_groups(profile_user)
    topic_rows = [(kind, r) for kind, _label, rows in skill_groups for r in rows]
    topic_map, weakest = _topic_map(topic_rows, problem_map)
    h2h, is_following = None, False
    if request.user.is_authenticated and request.user != profile_user:
        from apps.classroom.views import _rival
        h2h = _rival(request.user, profile_user)
        is_following = Follow.objects.filter(user=request.user, target=profile_user).exists()
    return render(request, "accounts/profile.html", {
        "h2h": h2h, "is_following": is_following,
        "profile_user": profile_user,
        "total_users": total_users,
        "total_rated": total_rated,
        "rating_rank": rating_rank,
        "rating_inactive": bool(rating_history) and rating_rank is None and profile_user.is_active,
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
                             for d in by_diff if d["total"]], user=profile_user),
        "problem_map": problem_map,
        "tier": rating_tier(profile_user.rating),
        "banner": tier_banner(profile_user.rating),
        "next_tier": _next_tier(profile_user.rating),
        **_badges(profile_user, request.user == profile_user),
        "contest_badges": _contest_badges(profile_user),
        "tier_color": _tier_color(profile_user.rating),
        "rating_history": rating_history,
        "max_rating": max((p.rating_after for p in rating_history), default=None),
        "rating_chart": _rating_chart(rating_history) if rating_history else None,
        "activity": _activity_calendar(profile_user),
        "skill_groups": skill_groups,
        # the topics table: one flat list (kind, row), the topics with most problems first
        "topic_rows": topic_rows,
        # the topics again, most solved first: one bar each (solved, tried, left) and the next to solve
        "topic_map": topic_map, "weakest": weakest,
        "streak": (cur_streak, best_streak),
        "last_delta": rating_history[-1].delta if rating_history else None,
        "top_pct": round(100 * rating_rank / total_rated, 1) if rating_rank and total_rated else None,
        "spark": _sparkline([p.rating_after for p in rating_history[-12:]]),
    })


def _topic_map(topic_rows, problem_map):
    """The profile's topics, most solved first: per topic how many problems are solved, tried and left (one bar),
    and the next to solve (a tried one first, else the easiest new one); and the weakest topic with a try in it."""
    status = {pr.id: (pr, st) for pr, st in problem_map}
    tags_of: dict[int, list[int]] = {}
    for problem_id, tag_id in Problem.tags.through.objects.filter(problem_id__in=list(status)).values_list("problem_id", "tag_id"):
        tags_of.setdefault(tag_id, []).append(problem_id)
    order = {"attempted": 0, "todo": 1, "solved": 2}
    levels = {v: i for i, v in enumerate(Problem.Difficulty.values)}
    rows = []
    for kind, r in topic_rows:
        marks = sorted((status[i] for i in tags_of.get(r["tag"].pk, []) if i in status),
                       key=lambda m: (order[m[1]], levels.get(m[0].difficulty, 9), m[0].pk))
        if not marks:
            continue
        todo = [pr for pr, st in marks if st != "solved"]
        tried = sum(1 for _, st in marks if st == "attempted")
        total = len(marks)
        solved = total - len(todo)
        rows.append({"kind": kind, "row": r, "tried": tried, "solved": solved, "total": total,
                     # the bar's three parts, in percent of the topic
                     "pct_solved": round(100 * solved / total), "pct_tried": round(100 * tried / total),
                     "next": todo[0] if todo else None,
                     "easiest": min(todo, key=lambda pr: (levels.get(pr.difficulty, 9), pr.pk)) if todo else None})
    rows.sort(key=lambda x: (-x["solved"], -x["total"], x["row"]["tag"].name))
    open_rows = [x for x in rows if x["solved"] < x["total"] and (x["tried"] or x["solved"])]
    weakest = min(open_rows, key=lambda x: (x["solved"] / x["total"], -x["tried"])) if open_rows else None
    return rows, weakest


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


def how_ratings(request):
    """"Reyting qanday ishlaydi": what the four numbers are and what moves them."""
    return render(request, "accounts/how_ratings.html")


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
    """Staff confirm this is the real student.
    Only verified users get an official rating, so it is rebuilt either way."""
    from django.core.exceptions import PermissionDenied
    from django.db import transaction
    from django.http import HttpResponseBadRequest

    from apps.contests.rating import recalc_official
    from apps.integrity import audit

    student = get_object_or_404(User, pk=user_id)
    if not request.user.is_staff:
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
        messages.success(request, f"{student.username}: shaxs {'tasdiqlandi' if want else _t('tasdig‘i bekor qilindi')}.")
    nxt = _safe_next(request)
    return redirect(nxt) if nxt else redirect("profile", student.username)


@login_required
def export_data(request):
    """"Ma'lumotlarimni yuklab olish": everything the site holds about the signed-in user as one JSON file."""
    from apps.classroom.models import Duel

    user = request.user
    data = {
        "exported_at": timezone.now().isoformat(),
        "profile": {
            "username": user.username, "first_name": user.first_name, "last_name": user.last_name, "email": user.email,
            "country": user.country, "city": user.location, "school": user.school,
            "joined": user.date_joined.isoformat(), "rating": user.rating, "practice_points": user.practice_points,
            "duel_rating": user.duel_rating,
        },
        "submissions": [
            {"id": s.pk, "problem": s.problem.slug, "language": s.language.code, "verdict": s.verdict,
             "created": s.created.isoformat(), "contest": s.contest_id, "source": s.source}
            for s in Submission.objects.filter(user=user).select_related("problem", "language").order_by("pk")],
        "contests": [
            {"contest": p.contest_id, "title": p.contest.title, "rank": p.rank, "score": p.score,
             "rating_before": p.rating_before, "rating_after": p.rating_after, "registered": p.registered_at.isoformat()}
            for p in Participation.objects.filter(user=user).select_related("contest").order_by("pk")],
        "duels": [
            {"id": d.pk, "challenger": d.challenger.username, "opponent": d.opponent.username if d.opponent else None,
             "language": d.language, "status": d.status, "created": d.created.isoformat(),
             "winner": d.winner.username if d.winner else None}
            for d in Duel.objects.filter(Q(challenger=user) | Q(opponent=user))
            .select_related("challenger", "opponent", "winner").order_by("pk")],
        "badges": list(user.badges.values("family", "tier", "earned_at")),
    }
    response = JsonResponse(data, json_dumps_params={"ensure_ascii": False, "indent": 2})
    response["Content-Disposition"] = f'attachment; filename="codearena-{user.username}.json"'
    return response


@login_required
@require_POST
def delete_account(request):
    """"Hisobni o‘chirish": the person's identity goes (name, email, photo, Telegram link, bell), the account is closed and
    the password cannot be used again. What they did stays under a neutral name, because contest standings and
    other people's ratings were worked out from it. Staff accounts are closed by another admin, not by themselves."""
    user = request.user
    if user.is_staff or not user.check_password(request.POST.get("password", "")):
        messages.error(request, _t("Parol noto‘g‘ri") if not user.is_staff else _t("Xodim hisobi bu yerdan o‘chirilmaydi."))
        return redirect("profile_edit")
    TelegramLink.objects.filter(user=user).delete()
    Notification.objects.filter(user=user).delete()
    Follow.objects.filter(Q(user=user) | Q(target=user)).delete()
    if user.avatar:
        user.avatar.delete(save=False)
    user.username = f"deleted-{user.pk}"
    user.first_name = user.last_name = user.email = user.school = user.location = ""
    user.country = ""
    user.avatar = None
    user.is_active = False
    user.set_unusable_password()
    user.save()
    from django.contrib.auth import logout
    logout(request)
    messages.success(request, _t("Hisobingiz o‘chirildi."))
    return redirect("home")
