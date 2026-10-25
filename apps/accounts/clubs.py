"""Schools and clubs: a public page with the members and how they did, a join link, a ranking of clubs. Deliberately
not a classroom: no assignments, no teacher role, nothing a member cannot see. The creator can rename the club and
share the link; everyone can leave."""
import secrets

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from apps.contests.models import Participation

from . import throttle
from .models import Club, User
from django.utils.translation import gettext as _t
from django.utils.translation import gettext as _t

TEAM_SIZE = 5  # a club's rating is the sum of its best five members' ratings


def team_rating(members) -> int:
    return sum(sorted((m.rating for m in members if m.rating > 0), reverse=True)[:TEAM_SIZE])


def club_list(request):
    clubs = list(Club.objects.annotate(n=Count("members")).filter(n__gt=0))
    members = {}
    for u in User.objects.filter(club__in=clubs, is_active=True).only("club_id", "rating"):
        members.setdefault(u.club_id, []).append(u)
    for c in clubs:
        c.n = len(members.get(c.pk, []))
        c.team = team_rating(members.get(c.pk, []))
    clubs = [c for c in clubs if c.n]
    clubs.sort(key=lambda c: (-c.team, -c.n, c.name))
    for i, c in enumerate(clubs):
        c.rank = 1 + sum(1 for o in clubs if o.team > c.team)
    return render(request, "accounts/clubs.html", {"clubs": clubs})


def club_detail(request, slug):
    club = get_object_or_404(Club, slug=slug)
    members = list(club.members.filter(is_active=True).order_by("-rating", "username"))
    mine = request.user.is_authenticated and request.user.club_id == club.pk
    code_ok = request.GET.get("code", "") == club.join_code
    seen = {}
    for p in (Participation.objects.filter(user__club=club, rank__isnull=False, contest__end__lte=timezone.now(),
                                           disqualified=False)
              .select_related("contest", "user").order_by("-contest__end", "rank")[:200]):
        row = seen.setdefault(p.contest_id, {"contest": p.contest, "best": p, "n": 0})
        row["n"] += 1
        if len(seen) > 6 and p.contest_id not in seen:
            break
    rounds = list(seen.values())[:6]
    return render(request, "accounts/club.html", {
        "club": club, "members": members, "team": team_rating(members), "mine": mine, "code_ok": code_ok,
        "is_owner": request.user.is_authenticated and club.owner_id == request.user.pk, "rounds": rounds,
        "invite": request.build_absolute_uri(reverse("club", args=[club.slug])) + f"?code={club.join_code}"})


def _unique_slug(name: str) -> str:
    base = slugify(name)[:60] or "klub"
    slug, n = base, 2
    while Club.objects.filter(slug=slug).exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


@login_required
@require_POST
def club_create(request):
    name = " ".join(request.POST.get("name", "").split())[:80]
    if request.user.club_id:
        messages.error(request, _t("Avval hozirgi klubingizdan chiqing."))
    elif len(name) < 3:
        messages.error(request, _t("Klub nomi kamida 3 belgi bo‘lsin."))
    elif Club.objects.filter(name__iexact=name).exists():
        messages.error(request, _t("Bunday nomli klub bor: unga qo‘shiling."))
    elif throttle.blocked(f"thr:club-create:{request.user.pk}", 3, 86400):
        messages.error(request, _t("Kuniga 3 tadan ko‘p klub ochib bo‘lmaydi."))
    else:
        try:
            with transaction.atomic():
                club = Club.objects.create(name=name, slug=_unique_slug(name), join_code=secrets.token_urlsafe(8),
                                           owner=request.user)
                User.objects.filter(pk=request.user.pk).update(club=club)
        except IntegrityError:
            messages.error(request, _t("Bunday nomli klub bor."))
        else:
            messages.success(request, _t("«{club_name}» klubi ochildi. Havolani do‘stlaringizga yuboring.").format(club_name=club.name))
            return redirect("club", club.slug)
    return redirect("clubs")


@login_required
@require_POST
def club_join(request, slug):
    club = get_object_or_404(Club, slug=slug)
    if request.POST.get("code", "") != club.join_code:
        messages.error(request, _t("Qo‘shilish havolasi noto‘g‘ri yoki eskirgan."))
    elif request.user.club_id and request.user.club_id != club.pk:
        messages.error(request, _t("Avval hozirgi klubingizdan chiqing."))
    else:
        User.objects.filter(pk=request.user.pk).update(club=club)
        messages.success(request, _t("«{club_name}» klubiga qo‘shildingiz.").format(club_name=club.name))
    return redirect("club", club.slug)


@login_required
@require_POST
def club_leave(request, slug):
    club = get_object_or_404(Club, slug=slug)
    if request.user.club_id == club.pk:
        User.objects.filter(pk=request.user.pk).update(club=None)
        if club.owner_id == request.user.pk:  # the club goes to its longest-standing member, or closes when empty
            heir = club.members.filter(is_active=True).order_by("date_joined").first()
            if heir:
                club.owner = heir
                club.save(update_fields=["owner"])
            else:
                club.delete()
                messages.success(request, _t("Klubdan chiqdingiz; u bo‘sh qolgani uchun yopildi."))
                return redirect("clubs")
        messages.success(request, _t("Klubdan chiqdingiz."))
    return redirect("clubs")
