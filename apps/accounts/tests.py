import pytest
from django.urls import reverse

from apps.problems.models import Language, Problem
from apps.submissions.models import Submission, UserProblemSolved

from .models import User


def _rated(*users):
    """A finished rated contest the given users took part in (rating_after set)."""
    from django.utils import timezone

    from apps.contests.models import Contest, Participation

    c = Contest.objects.create(title="R", is_rated=True, rating_applied=True,
                               start=timezone.now() - timezone.timedelta(hours=3),
                               end=timezone.now() - timezone.timedelta(hours=2))
    for u in users:
        Participation.objects.create(user=u, contest=c, rating_before=1200, rating_after=u.rating)


@pytest.mark.django_db
def test_register_creates_user_and_logs_in(client):
    r = client.post(reverse("register"), {
        "username": "ali", "email": "ali@example.com", "first_name": "Ali",
        "password1": "StrongPass123!", "password2": "StrongPass123!",
    })
    assert r.status_code == 302
    u = User.objects.get(username="ali")
    assert u.rating == 0 and u.practice_points == 0 and u.role == "student"  # shown rating starts at 0
    assert u.email == "ali@example.com" and u.first_name == "Ali"
    assert client.session["_auth_user_id"] == str(u.pk)


@pytest.mark.django_db
def test_register_rejects_duplicate_email(client):
    User.objects.create_user("existing", email="dup@example.com", password="x")
    r = client.post(reverse("register"), {
        "username": "ali", "email": "dup@example.com",
        "password1": "StrongPass123!", "password2": "StrongPass123!",
    })
    assert r.status_code == 200
    assert not User.objects.filter(username="ali").exists()


@pytest.mark.django_db
def test_login_page_renders(client):
    assert client.get(reverse("login")).status_code == 200


@pytest.mark.django_db
def test_top_lists_users_by_practice_points_desc(client):
    User.objects.create_user("low", password="x", practice_points=5)
    User.objects.create_user("high", password="x", practice_points=50)
    r = client.get(reverse("top"))
    assert r.status_code == 200
    users = list(r.context["users"])
    assert [u.username for u in users[:2]] == ["high", "low"]



@pytest.mark.django_db
def test_top_leaves_out_staff_and_users_without_points(client):
    User.objects.create_user("ali", password="x", practice_points=40)
    User.objects.create_user("yangi", password="x")
    User.objects.create_user("admin", password="x", is_staff=True, practice_points=90)
    r = client.get(reverse("top"))
    assert [u.username for u in r.context["users"]] == ["ali"] and r.context["total"] == 1
    # the profile's "Ballda o‘rni" counts the same board
    r = client.get(reverse("profile", args=["ali"]))
    assert r.context["points_rank"] == 1 and r.context["total_users"] == 1
    assert client.get(reverse("profile", args=["admin"])).context["points_rank"] is None

@pytest.mark.django_db
def test_profile_shows_stats_and_solved_problems(client):
    author = User.objects.create_user("teacher", password="x")
    user = User.objects.create_user("ali", password="x", practice_points=10, rating=1500)
    problem = Problem.objects.create(slug="a-plus-b", title="A + B", statement_md="x", author=author,
                                     tl_ms=1000, points=10)
    lang = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    sub = Submission.objects.create(user=user, problem=problem, language=lang, source="x", verdict="AC")
    UserProblemSolved.objects.create(user=user, problem=problem, first_ac_submission=sub)

    r = client.get(reverse("profile", args=["ali"]))
    assert r.status_code == 200
    assert r.context["profile_user"] == user
    assert list(r.context["solved"]) == [problem]


@pytest.mark.django_db
def test_profile_404_for_unknown_username(client):
    assert client.get(reverse("profile", args=["nobody"])).status_code == 404


def test_rating_chart_axis_labels_never_overlap():
    import datetime
    from types import SimpleNamespace

    from .views import _rating_chart

    end = datetime.datetime(2026, 9, 6)
    # 1224 pads the top to 1335, 15 px above the 1300 tier line: only one of the two may be labelled
    history = [SimpleNamespace(rating_after=r, contest=SimpleNamespace(end=end)) for r in (484, 689, 868, 1126, 1224)]
    ys = sorted(g["y"] for g in _rating_chart(history)["gridlines"])
    assert all(b - a >= 14 for a, b in zip(ys, ys[1:])), ys


@pytest.mark.django_db
def test_profile_shows_rating_history_graph(client):
    from django.utils import timezone

    from apps.contests.models import Contest, Participation

    user = User.objects.create_user("ali", password="x", rating=1550)
    contest = Contest.objects.create(
        title="Sprint 1", start=timezone.now() - timezone.timedelta(days=2),
        end=timezone.now() - timezone.timedelta(days=2, hours=-2), is_rated=True)
    Participation.objects.create(user=user, contest=contest, rank=1, rating_before=1500, rating_after=1550)

    r = client.get(reverse("profile", args=["ali"]))
    assert r.status_code == 200
    assert len(r.context["rating_history"]) == 1
    assert r.context["rating_chart"]["points"]
    assert b"Sprint 1" in r.content
    assert b"+50" in r.content


@pytest.mark.django_db
def test_profile_hides_rating_graph_without_rated_contests(client):
    User.objects.create_user("ali", password="x")
    r = client.get(reverse("profile", args=["ali"]))
    assert r.status_code == 200
    assert r.context["rating_history"] == []
    assert b"Rating tarixi" not in r.content


@pytest.mark.django_db
def test_rating_lists_users_by_rating_desc(client):
    low = User.objects.create_user("low", password="x", rating=1400)
    high = User.objects.create_user("high", password="x", rating=1800)
    User.objects.create_user("fresh", password="x", rating=2000)  # never rated: not on the board
    _rated(low, high)
    r = client.get(reverse("rating"))
    assert r.status_code == 200
    assert [u.username for u in r.context["users"]] == ["high", "low"] and r.context["total"] == 2


@pytest.mark.django_db
def test_rating_shows_your_place_the_next_tier_and_everyones_last_change(client):
    from .views import _next_tier

    low = User.objects.create_user("low", password="x", rating=1250)
    high = User.objects.create_user("high", password="x", rating=1650)
    _rated(low, high)  # both from 1200: +50 and +450
    client.force_login(low)
    r = client.get(reverse("rating"))
    assert r.context["me"] == {"rank": 2, "delta": 50, "page": 1, "contests": 1,
                               "next": {"name": "Candidate Master", "color": "#AA00AA", "need": 50, "pct": 75}}
    found = client.get(reverse("rating"), {"q": "hig"}).context["users"]
    assert [(u.username, u.rank) for u in found] == [("high", 1)]  # a search keeps the board place
    assert {t["name"]: t["count"] for t in r.context["tiers"] if t["count"]} == {"Expert": 1, "Master": 1}
    assert [u.last_delta for u in r.context["users"]] == [450, 50]
    assert _next_tier(1500)["name"] == "Grandmaster" and _next_tier(1500)["pct"] == 0
    assert _next_tier(0) == {"name": "Pupil", "color": "#008000", "need": 700, "pct": 0}
    assert _next_tier(2400) is None  # Legendary Grandmaster has nothing above it

    client.force_login(User.objects.create_user("fresh", password="x"))
    assert client.get(reverse("rating")).context["me"] is None  # no rated contest yet: no place


@pytest.mark.django_db
def test_blocked_users_get_no_place_on_boards(client):
    ok = User.objects.create_user("ok", password="x", rating=1400, practice_points=5)
    banned = User.objects.create_user("banned", password="x", rating=1800, practice_points=50, is_active=False)
    _rated(ok, banned)
    for name in ("top", "rating"):
        r = client.get(reverse(name))
        assert [u.username for u in r.context["users"]] == ["ok"] and r.context["total"] == 1

    r = client.get(reverse("profile", args=["ok"]))
    assert r.context["rating_rank"] == 1 and r.context["points_rank"] == 1
    assert r.context["total_users"] == 1 and r.context["total_rated"] == 1
    r = client.get(reverse("profile", args=["banned"]))
    assert r.context["rating_rank"] is None and r.context["points_rank"] is None


@pytest.mark.django_db
def test_password_reset_end_to_end(client, mailoutbox):
    User.objects.create_user("ali", email="ali@example.com", password="OldPass123!")

    r = client.post(reverse("password_reset"), {"email": "ali@example.com"})
    assert r.status_code == 302
    assert len(mailoutbox) == 1
    body = mailoutbox[0].body
    assert "/accounts/reset/" in body

    import re
    match = re.search(r"/accounts/reset/(?P<uidb64>[\w-]+)/(?P<token>[\w-]+)/", body)
    assert match

    # Django's PasswordResetConfirmView needs the raw token session-swapped
    # on first GET (it replaces it with "set-password" and stashes the real
    # one in session) before the form POST will accept new_password1/2.
    confirm_url = reverse("password_reset_confirm", kwargs=match.groupdict())
    r = client.get(confirm_url, follow=True)
    assert r.status_code == 200

    r = client.post(r.redirect_chain[-1][0], {
        "new_password1": "BrandNewPass456!", "new_password2": "BrandNewPass456!",
    })
    assert r.status_code == 302

    user = User.objects.get(username="ali")
    assert user.check_password("BrandNewPass456!")


@pytest.mark.django_db
def test_password_reset_unknown_email_does_not_leak(client, mailoutbox):
    r = client.post(reverse("password_reset"), {"email": "nobody@example.com"})
    assert r.status_code == 302  # same redirect whether or not the email exists
    assert len(mailoutbox) == 0


@pytest.mark.django_db
def test_recalc_practice_points_sums_current_points_of_solved_problems():
    from django.core.management import call_command

    author = User.objects.create_user("teacher", password="x")
    python = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    cheap = Problem.objects.create(slug="cheap", title="Cheap", statement_md="x", author=author, points=30)
    pricey = Problem.objects.create(slug="pricey", title="Pricey", statement_md="x", author=author, points=250)

    solver = User.objects.create_user("ali", password="x", practice_points=9999)  # stale, gets overwritten
    idle = User.objects.create_user("vosil", password="x", practice_points=42)  # never solved anything

    for problem in (cheap, pricey):
        sub = Submission.objects.create(user=solver, problem=problem, language=python, source="x", verdict="AC")
        UserProblemSolved.objects.create(user=solver, problem=problem, first_ac_submission=sub)

    call_command("recalc_practice_points")

    solver.refresh_from_db()
    idle.refresh_from_db()
    assert solver.practice_points == 30 + 250
    assert idle.practice_points == 0


@pytest.mark.django_db
def test_recalc_practice_points_drops_solves_the_rule_no_longer_allows():
    from django.core.management import call_command
    from django.utils import timezone

    from apps.contests.models import Contest, Participation

    author = User.objects.create_user("teacher", password="x")
    cheat = User.objects.create_user("cheat", password="x", practice_points=70)
    python = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    p = Problem.objects.create(slug="p", title="P", statement_md="x", author=author, points=70)
    c = Contest.objects.create(title="C", start=timezone.now() - timezone.timedelta(hours=3),
                               end=timezone.now() - timezone.timedelta(hours=2), published_at=timezone.now())
    Participation.objects.create(user=cheat, contest=c, disqualified=True)
    sub = Submission.objects.create(user=cheat, problem=p, contest=c, language=python, source="x", verdict="AC")
    UserProblemSolved.objects.create(user=cheat, problem=p, first_ac_submission=sub)  # left by the old publish

    call_command("recalc_practice_points")

    cheat.refresh_from_db()
    assert not UserProblemSolved.objects.filter(user=cheat).exists() and cheat.practice_points == 0


@pytest.mark.django_db
def test_register_rejects_email_as_username(client):
    r = client.post(reverse("register"), {
        "username": "ali@gmail.com", "email": "ali@gmail.com", "first_name": "Ali",
        "password1": "StrongPass123!", "password2": "StrongPass123!",
    })
    assert r.status_code == 200
    assert "bo‘lmasin" in r.content.decode()
    assert not User.objects.exists()


@pytest.mark.django_db
def test_login_accepts_email(client):
    User.objects.create_user("ozod", email="Ozod@Gmail.com", password="StrongPass123!")
    r = client.post(reverse("login"), {"username": "ozod@gmail.com", "password": "StrongPass123!"})
    assert r.status_code == 302 and "_auth_user_id" in client.session


@pytest.mark.django_db
def test_migration_strips_email_usernames_and_login_still_works(client):
    import importlib

    from django.apps import apps
    migration = importlib.import_module("apps.accounts.migrations.0005_usernames_without_email")
    User.objects.create_user("ozodbek", password="x")
    User.objects.create_user("ozodbek@gmail.com", email="ozodbek@gmail.com", password="StrongPass123!")
    User.objects.create_user("x.y@mail.uz", email="", password="x")
    migration.strip_email_usernames(apps, None)
    assert set(User.objects.values_list("username", flat=True)) == {"ozodbek", "ozodbek2", "x.y"}
    assert User.objects.get(username="x.y").email == "x.y@mail.uz"
    r = client.post(reverse("login"), {"username": "ozodbek@gmail.com", "password": "StrongPass123!"})
    assert r.status_code == 302


@pytest.mark.django_db
def test_unrated_profile_says_reytingsiz(client):
    vet = User.objects.create_user("vet", password="x", rating=1500)
    _rated(vet)
    User.objects.create_user("new", password="x", rating=1700)  # staff-set rating, no rated contest
    r = client.get(reverse("profile", args=["new"]))
    assert r.context["rating_rank"] is None and r.context["total_rated"] == 1
    assert "Reytingsiz" in r.content.decode()
    r = client.get(reverse("profile", args=["vet"]))
    assert r.context["rating_rank"] == 1 and "Reytingsiz" not in r.content.decode()


@pytest.mark.django_db
def test_profile_gauge_counts_solves_from_the_same_catalog_as_the_totals(client):
    """A public problem held by an upcoming contest is out of the catalog, so its old
    solve must not make "Easy" read 2/1."""
    from django.utils import timezone

    from apps.contests.models import Contest, ContestProblem

    author = User.objects.create_user("author", password="x")
    ali = User.objects.create_user("ali", password="x")
    lang = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    shown = Problem.objects.create(slug="a", title="A", statement_md="x", author=author, difficulty="easy")
    held = Problem.objects.create(slug="b", title="B", statement_md="x", author=author, difficulty="easy")
    c = Contest.objects.create(title="Soon", start=timezone.now() + timezone.timedelta(days=1),
                               end=timezone.now() + timezone.timedelta(days=2))
    ContestProblem.objects.create(contest=c, problem=held, label="A")
    for p in (shown, held):
        s = Submission.objects.create(user=ali, problem=p, language=lang, source="x", verdict="AC")
        UserProblemSolved.objects.create(user=ali, problem=p, first_ac_submission=s)

    r = client.get(reverse("profile", args=["ali"]))
    easy = next(d for d in r.context["by_diff"] if d["key"] == "easy")
    assert (easy["solved"], easy["total"]) == (1, 1)
    assert r.context["solved_shown"] == 1 and r.context["total_public_problems"] == 1


@pytest.mark.django_db
def test_activity_calendar_tells_june_from_july():
    from .views import _activity_calendar

    names = [m["name"] for m in _activity_calendar(User.objects.create_user("ali", password="x"))["month_labels"]]
    assert "Iyn" in names and "Iyl" in names and "Iyu" not in names


@pytest.mark.django_db
def test_tier_up_congratulates_once_and_first_visit_only_records(client):
    from apps.accounts.models import User as U
    u = U.objects.create_user("tiery", password="x", rating=600)
    client.force_login(u)
    assert "ca-tier-up" not in client.get("/").content.decode()  # first visit: just remembered
    assert U.objects.get(pk=u.pk).seen_tier == "Newbie"
    U.objects.filter(pk=u.pk).update(rating=750)
    assert "Tabriklaymiz! Siz endi Pupil" in client.get("/").content.decode()
    assert "ca-tier-up" not in client.get("/").content.decode()  # only once
    U.objects.filter(pk=u.pk).update(rating=650)
    assert "ca-tier-up" not in client.get("/").content.decode()  # a drop is silent


def test_next_streak_badge_counts_from_the_current_run():
    from apps.accounts.badges import next_streak
    assert next_streak(current=0, best=6) == {"name": "Olov II", "icon": "flame", "days": 7, "left": 7}
    assert next_streak(current=3, best=40)["name"] == "Olov IV" and next_streak(current=3, best=40)["left"] == 97
    assert next_streak(current=400, best=400) is None  # level V is the top


@pytest.mark.django_db
def test_tier_up_is_claimed_once_even_by_two_tabs():
    from apps.accounts.context_processors import _claim_tier_up
    from apps.accounts.models import User as U
    U.objects.create_user("twotabs", password="x", rating=750, seen_tier="Newbie")
    tab1, tab2 = U.objects.get(username="twotabs"), U.objects.get(username="twotabs")
    assert _claim_tier_up(tab1)["name"] == "Pupil"
    assert _claim_tier_up(tab2) is None  # the other tab read the old tier too, but lost the update


@pytest.mark.django_db
def test_rating_board_shows_handles_only_and_a_histogram_of_every_100_points(client):
    ann = User.objects.create_user("ann", password="x", first_name="Anna", last_name="Karimova", rating=1250)
    bek = User.objects.create_user("bek", password="x", rating=640)
    _rated(ann, bek)
    r = client.get(reverse("rating"))
    assert "Karimova" not in r.content.decode()  # the real name stays on the profile
    bars = r.context["spread"]["bars"]
    assert len(bars) == 20  # up to 2000 even when nobody is there: the tiers above everyone still show
    assert {b["lo"]: b["n"] for b in bars if b["n"]} == {600: 1, 1200: 1}
    assert not any(b["mine"] for b in bars)  # a guest has no bar of their own
    client.force_login(ann)
    assert [b["lo"] for b in client.get(reverse("rating")).context["spread"]["bars"] if b["mine"]] == [1200]


@pytest.mark.django_db
def test_profile_gives_no_points_place_without_points(client):
    User.objects.create_user("scorer", password="x", practice_points=10)
    User.objects.create_user("fresh", password="x")
    assert client.get(reverse("profile", args=["scorer"])).context["points_rank"] == 1
    # everyone at 0 would share the place after the last scorer: "2 / 34" with no points at all
    assert client.get(reverse("profile", args=["fresh"])).context["points_rank"] is None



# ---- badges ------------------------------------------------------------------

@pytest.mark.django_db
def test_a_badge_climbs_its_levels_and_keeps_them(client):
    from unittest.mock import patch

    from apps.accounts import badges
    from apps.accounts.models import User as U, UserBadge

    u = U.objects.create_user("ali", password="x")
    with patch.object(badges, "metrics", return_value={"wins": 12, "solved": 3}):
        board = {b["key"]: b for b in badges.board(u, {"duels", "problems"})}
    duelchi = board["duelchi"]
    assert (duelchi["tier"], duelchi["title"], duelchi["sub"], duelchi["pips"]) == (2, "Duelchi II", "10 ta g‘alaba",
                                                                                  [True, True, False, False, False])
    assert duelchi["next"] == {"roman": "III", "at": 50, "done": 2, "total": 40, "shown": "12 / 50"}
    assert board["yechuvchi"]["tier"] == 0 and board["yechuvchi"]["next"]["shown"] == "3 / 10"
    assert set(UserBadge.objects.filter(user=u).values_list("family", "tier")) == {("duelchi", 1), ("duelchi", 2)}
    # the count drops (say, a rejudge): the level stays
    with patch.object(badges, "metrics", return_value={"wins": 1}):
        assert {b["key"]: b for b in badges.board(u, {"duels"})}["duelchi"]["tier"] == 2
    toast = badges.unseen(u)
    assert [b["title"] for b in toast] == ["Duelchi II"] and badges.unseen(u) == []  # once


@pytest.mark.django_db
def test_new_level_toast_shows_once_and_the_profile_groups_badges(client):
    from unittest.mock import patch

    from apps.accounts import badges
    from apps.accounts.models import User as U

    from django.core.cache import cache

    cache.clear()  # the toast's sync throttle is a cache key
    u = U.objects.create_user("ali", password="x")
    other = U.objects.create_user("vali", password="x")
    client.force_login(u)
    with patch.object(badges, "metrics", side_effect=lambda user, only=None: {"wins": 5} if user == u else {}):
        page = client.get("/").content.decode()
        assert "Nishonni qo‘lga kiritdingiz!" in page and "Duelchi I" in page and 'id="ca-award"' in page
        assert 'id="ca-award"' not in client.get("/").content.decode()  # once
        mine = client.get(reverse("profile", args=["ali"]))
        groups = {g["label"]: [b["title"] for b in g["badges"]] for g in mine.context["badge_groups"]}
        assert "Duelchi I" in groups["Duellar"] and "Yechuvchi" in groups["Masalalar"]  # the owner sees locked ones too
        client.force_login(other)
        theirs = client.get(reverse("profile", args=["ali"])).context["badge_groups"]
        assert [(g["label"], [b["title"] for b in g["badges"]]) for g in theirs] == [("Duellar", ["Duelchi I"])]


@pytest.mark.django_db
def test_the_badges_page_and_the_badge_board_rank_by_levels(client):
    from apps.accounts.models import User as U, UserBadge

    a, b, c = (U.objects.create_user(n, password="x") for n in ("ali", "vali", "sami"))
    for user, rows in ((a, [("duelchi", 1), ("duelchi", 2), ("yechuvchi", 1)]), (b, [("olov", 1), ("olov", 2), ("olov", 3)]),
                       (c, [("choqqi", 1)])):
        for fam, tier in rows:
            UserBadge.objects.create(user=user, family=fam, tier=tier, seen=True)
    r = client.get(reverse("badge_board"))
    assert [(x["u"].username, x["rank"], x["levels"], x["families"]) for x in r.context["rows"]] == [
        ("ali", 1, 3, 2), ("vali", 2, 3, 1), ("sami", 3, 1, 1)]  # equal levels: more badges first
    assert [x["title"] for x in r.context["rows"][0]["badges"]] == ["Duelchi II", "Yechuvchi I"]
    client.force_login(c)
    page = client.get(reverse("badges"))
    assert page.context["me"]["rank"] == 3 and page.context["me"]["levels"] == 1
    duel = next(f for g in page.context["groups"] for f in g["families"] if f["key"] == "duelchi")
    assert [(l["at"], l["pct"]) for l in duel["levels"]][:3] == [(5, 33), (10, 33), (50, 0)]  # 1 of 3 players


@pytest.mark.django_db
def test_an_accept_awards_its_badge_on_the_submission_page_at_once(client):
    from apps.accounts.models import UserBadge
    from apps.problems.models import Language, Problem
    from apps.submissions.models import Submission, UserProblemSolved

    u = User.objects.create_user("ali", password="x")
    lang = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    problem = Problem.objects.create(slug="p", title="P", statement_md="x", author=u, difficulty="hard")
    s = Submission.objects.create(user=u, problem=problem, language=lang, source="x", verdict="AC")
    UserProblemSolved.objects.create(user=u, problem=problem, first_ac_submission=s)
    client.force_login(u)
    part = client.get(reverse("submissions:status", args=[s.pk])).content.decode()
    assert 'hx-swap-oob="beforeend:body"' in part and "Cho‘qqi I" in part  # the first Hard solve
    assert UserBadge.objects.filter(user=u, family="choqqi", tier=1, seen=True).exists()
    assert "ca-award" not in client.get(reverse("submissions:status", args=[s.pk])).content.decode()


# ---- the account gate (apps.accounts.onboarding) ----

def _gated(**kw):
    defaults = dict(email="ali@example.com", first_name="Ali", last_name="Valiyev", country="UZ", location="Toshkent")
    return User.objects.create_user("ali", password="x", **{**defaults, **kw})


@pytest.mark.django_db
def test_gate_sends_an_unconfirmed_user_to_the_welcome_page(client, settings):
    settings.ACCOUNT_GATE = True
    client.force_login(_gated(country=""))
    r = client.get(reverse("problems:list"))
    assert r.status_code == 302 and r.url == reverse("welcome")
    page = client.get(reverse("welcome")).content.decode()
    assert "Hisobingizni yakunlang" in page and "davlat" in page


@pytest.mark.django_db
def test_gate_leaves_staff_and_confirmed_users_alone(client, settings):
    from django.utils import timezone
    settings.ACCOUNT_GATE = True
    client.force_login(_gated(email_verified_at=timezone.now()))
    assert client.get(reverse("problems:list")).status_code == 200
    assert client.get(reverse("welcome")).status_code == 302  # nothing owed: home
    client.force_login(User.objects.create_user("boss", password="x", is_staff=True))
    assert client.get(reverse("problems:list")).status_code == 200


@pytest.mark.django_db
def test_welcome_form_saves_fields_and_mails_the_link_that_confirms(client, settings, mailoutbox):
    settings.ACCOUNT_GATE = True
    u = User.objects.create_user("ali", password="x", email="")
    client.force_login(u)
    r = client.post(reverse("welcome"), {"first_name": "Ali", "last_name": "Valiyev", "country": "UZ",
                                         "location": "Samarqand", "email": "ali@example.com"})
    assert r.status_code == 302
    u.refresh_from_db()
    assert (u.country, u.location, u.email) == ("UZ", "Samarqand", "ali@example.com") and u.email_verified_at is None
    assert len(mailoutbox) == 1 and mailoutbox[0].to == ["ali@example.com"]
    assert "Emailingizni tasdiqlang" in client.get(reverse("welcome")).content.decode()
    link = next(w for w in mailoutbox[0].body.split() if "/verify-email/" in w)
    assert client.get(link).status_code == 302
    u.refresh_from_db()
    assert u.email_verified_at is not None
    assert client.get(reverse("problems:list")).status_code == 200


@pytest.mark.django_db
def test_verify_link_is_void_once_the_email_changes(client):
    from . import onboarding
    u = _gated()
    token = onboarding.make_token(u)
    u.email = "other@example.com"
    u.save()
    client.get(reverse("verify_email", args=[token]))
    u.refresh_from_db()
    assert u.email_verified_at is None
    client.get(reverse("verify_email", args=["junk"]))  # a bad token is a message, not a 500


@pytest.mark.django_db
def test_resend_is_held_back_for_a_minute(client, settings, mailoutbox):
    settings.ACCOUNT_GATE = True
    client.force_login(_gated())
    client.post(reverse("welcome"), {"resend": "1"})
    client.post(reverse("welcome"), {"resend": "1"})
    assert len(mailoutbox) == 1


def _settings_post(u, **kw):
    data = {"username": u.username, "first_name": u.first_name, "last_name": u.last_name, "country": u.country,
            "location": u.location, "school": "", "email": u.email}
    return {**data, **kw}


@pytest.mark.django_db
def test_username_changes_once_in_90_days(client):
    from django.utils import timezone
    u = _gated(email_verified_at=timezone.now())
    client.force_login(u)
    assert client.post(reverse("profile_edit"), _settings_post(u, username="ali2")).status_code == 302
    u.refresh_from_db()
    assert u.username == "ali2" and u.username_changed_at is not None
    client.post(reverse("profile_edit"), _settings_post(u, username="ali3"))
    u.refresh_from_db()
    assert u.username == "ali2"  # the field is locked until the 90 days are up
    u.username_changed_at = timezone.now() - timezone.timedelta(days=91)
    u.save()
    client.post(reverse("profile_edit"), _settings_post(u, username="ali3"))
    u.refresh_from_db()
    assert u.username == "ali3"


@pytest.mark.django_db
def test_new_email_in_settings_must_be_confirmed_again(client, mailoutbox):
    from django.utils import timezone
    u = _gated(email_verified_at=timezone.now())
    User.objects.create_user("taken", password="x", email="taken@example.com")
    client.force_login(u)
    r = client.post(reverse("profile_edit"), _settings_post(u, email="TAKEN@example.com"))
    assert r.status_code == 200 and "boshqa hisobda" in r.content.decode()
    client.post(reverse("profile_edit"), _settings_post(u, email="new@example.com"))
    u.refresh_from_db()
    assert u.email == "new@example.com" and u.email_verified_at is None and mailoutbox[-1].to == ["new@example.com"]


@pytest.mark.django_db
def test_register_mails_the_confirmation_link(client, mailoutbox):
    client.post(reverse("register"), {"username": "vali", "email": "vali@example.com", "first_name": "Vali",
                                      "password1": "StrongPass123!"})
    assert [m.to for m in mailoutbox] == [["vali@example.com"]]


# ---- the bell (apps.accounts.notifications) ----

@pytest.mark.django_db
def test_bell_counts_unread_and_opening_one_reads_it(client):
    from .models import Notification
    from .notifications import notify
    u = User.objects.create_user("ali", password="x")
    notify(u.pk, "duel", "k1", "bob sizni duelga chaqirdi", "/classroom/duels/")
    notify(u.pk, "duel", "k1", "twice", "/x/")  # the same event is told once
    notify(u.pk, "badge", "k2", "Yangi nishon", "/accounts/badges/")
    client.force_login(u)
    page = client.get(reverse("problems:list")).content.decode()
    assert "Bildirishnomalar: 2 ta yangi" in page and "bob sizni duelga chaqirdi" in page and "twice" not in page
    n = Notification.objects.get(key="k1")
    r = client.get(reverse("notification_open", args=[n.pk]))
    assert r.status_code == 302 and r.url == "/classroom/duels/"
    n.refresh_from_db()
    assert n.read_at is not None
    client.post(reverse("notifications_read"))
    assert not Notification.objects.filter(user=u, read_at__isnull=True).exists()


@pytest.mark.django_db
def test_someone_elses_notification_is_a_404(client):
    from .models import Notification
    from .notifications import notify
    a, b = (User.objects.create_user(n, password="x") for n in ("a", "b"))
    notify(a.pk, "duel", "k", "t", "/")
    client.force_login(b)
    assert client.get(reverse("notification_open", args=[Notification.objects.get().pk])).status_code == 404


# ---- country -> city -> school pickers (apps.accounts.places) ----

def test_places_tidy_spellings_and_keep_unknown_text():
    from .places import canon_city, canon_school
    assert canon_city("UZ", "BUKHARA") == "Buxoro" and canon_city("UZ", "buxoro") == "Buxoro"
    assert canon_city("UZ", "Qo'qon") == "Qo‘qon" and canon_city("UZ", " Tashkent ") == "Toshkent"
    assert canon_city("UZ", "Qishloqcha") == "Qishloqcha" and canon_city("FR", "Parij") == "Parij"
    assert canon_school("UZ", "OXU 2-ATT-25") == "Osiyo xalqaro universiteti"
    assert canon_school("UZ", "osiyo xalqaro unversituti 2-kurs") == "Osiyo xalqaro universiteti"
    assert canon_school("UZ", "buxoro davlat universiteti") == "Buxoro davlat universiteti"
    for typed in ("2-ATT", "2-ATT-25", "OXU_2-ATT-25", "att 2- kurs", "ATT", "K4 ATT25 99 KURS"):
        assert canon_school("UZ", typed) == "Osiyo xalqaro universiteti"
    assert canon_school("UZ", "Battery maktabi") == "Battery maktabi"  # ATT only as a word of its own
    assert canon_school("UZ", "2-sonli maktab") == "2-sonli maktab"


@pytest.mark.django_db
def test_welcome_takes_a_listed_city_or_a_typed_one(client, settings):
    settings.ACCOUNT_GATE = True
    u = User.objects.create_user("ali", password="x", email="")
    client.force_login(u)
    base = {"first_name": "Ali", "last_name": "Valiyev", "country": "UZ", "email": "ali@example.com"}
    client.post(reverse("welcome"), {**base, "location": "__other__", "location_other": "Bukhara"})
    u.refresh_from_db()
    assert u.location == "Buxoro"  # typed in "Boshqa…", tidied to the list's spelling
    client.post(reverse("welcome"), {**base, "email": "ali2@example.com", "location": "__other__", "location_other": "Qishloqcha"})
    u.refresh_from_db()
    assert u.location == "Qishloqcha"
    r = client.post(reverse("welcome"), {**base, "email": "ali3@example.com", "location": "__other__", "location_other": " "})
    assert r.status_code == 200 and "Shaharni yozing." in r.content.decode()


@pytest.mark.django_db
def test_settings_school_from_the_picker_or_typed(client):
    from django.utils import timezone
    u = _gated(email_verified_at=timezone.now(), location="Buxoro")
    client.force_login(u)
    client.post(reverse("profile_edit"), _settings_post(u, school="Buxoro davlat universiteti"))
    u.refresh_from_db()
    assert u.school == "Buxoro davlat universiteti"
    client.post(reverse("profile_edit"), _settings_post(u, school="__other__", school_other="OXU, 2-kurs"))
    u.refresh_from_db()
    assert u.school == "Osiyo xalqaro universiteti"
    client.post(reverse("profile_edit"), _settings_post(u, school="__other__", school_other="12-maktab"))
    u.refresh_from_db()
    assert u.school == "12-maktab"
    page = client.get(reverse("profile_edit")).content.decode()
    assert 'id="places-data"' in page and 'data-value="12-maktab"' in page


# ---- place filters and flags on the boards (apps.accounts.geo) ----

def _rated_in(name, rating, **kw):
    """A user with one rated contest, so the rating board lists them."""
    from datetime import timedelta
    from django.utils import timezone
    from apps.contests.models import Contest, Participation
    u = User.objects.create_user(name, password="x", rating=rating, **kw)
    c = Contest.objects.create(title=f"c-{name}", start=timezone.now() - timedelta(days=2), end=timezone.now() - timedelta(days=1))
    Participation.objects.create(contest=c, user=u, rating_before=1200, rating_after=rating)
    return u


@pytest.mark.django_db
def test_rating_filters_by_country_city_and_school(client):
    _rated_in("ali", 1500, country="UZ", location="Buxoro", school="Osiyo xalqaro universiteti")
    _rated_in("vali", 1400, country="UZ", location="Toshkent")
    _rated_in("kair", 1300, country="KZ", location="Ostona")
    page = client.get(reverse("rating")).content.decode()
    assert "O‘zbekiston" in page and "Qozog‘iston" in page and "/static/flags/uz.svg" in page
    uz = client.get(reverse("rating"), {"country": "UZ"}).content.decode()
    assert "vali" in uz and "ali" in uz and "kair" not in uz and "Barcha shaharlar" in uz
    city = client.get(reverse("rating"), {"country": "UZ", "city": "Buxoro"}).content.decode()
    assert "ali" in city and "vali" not in city and "Barcha o‘quv joylari" in city
    school = client.get(reverse("rating"), {"country": "UZ", "city": "Buxoro", "school": "Osiyo xalqaro universiteti"})
    assert school.status_code == 200 and "vali" not in school.content.decode()


@pytest.mark.django_db
def test_place_filter_ranks_within_the_group_and_ignores_unknown_values(client):
    from .geo import board_geo
    _rated_in("top", 1900, country="KZ", location="Ostona")
    _rated_in("ali", 1500, country="UZ", location="Buxoro")
    r = client.get(reverse("rating"), {"country": "UZ"})
    assert [u.rank for u in r.context["users"]] == [1]  # first among Uzbeks, not second overall
    r = client.get(reverse("rating"), {"country": "XX", "city": "Nowhere", "school": "?"})
    assert r.status_code == 200 and len(r.context["users"]) == 2 and not r.context["geo"]["active"]
    from django.test import RequestFactory
    cond, ctx = board_geo(RequestFactory().get("/", {"country": "UZ", "city": "Qarshi"}), [("UZ", "Buxoro", "")])
    assert cond == {"country": "UZ"} and ctx["geo"]["city"] == ""  # a city nobody on the board has is dropped


@pytest.mark.django_db
def test_practice_board_filters_by_country(client):
    User.objects.create_user("ali", password="x", practice_points=50, country="UZ", location="Buxoro")
    User.objects.create_user("kair", password="x", practice_points=40, country="KZ", location="Ostona")
    page = client.get(reverse("top"), {"country": "KZ"}).content.decode()
    assert "kair" in page and "ali" not in page.split("<tbody>")[1]


@pytest.mark.django_db
def test_backfill_gives_uzbek_cities_their_country():
    import importlib
    from django.apps import apps as django_apps
    a = User.objects.create_user("a", password="x", location="Buxoro")
    b = User.objects.create_user("b", password="x", location="Parij")
    importlib.import_module("apps.accounts.migrations.0025_backfill_country").backfill(django_apps, None)
    a.refresh_from_db(); b.refresh_from_db()
    assert (a.country, b.country) == ("UZ", "")


@pytest.mark.django_db
def test_school_filter_is_independent_of_the_home_city(client):
    _rated_in("ali", 1500, country="UZ", location="Qarshi", school="Osiyo xalqaro universiteti")
    _rated_in("vali", 1400, country="UZ", location="Buxoro", school="Osiyo xalqaro universiteti")
    page = client.get(reverse("rating"), {"country": "UZ", "school": "Osiyo xalqaro universiteti"}).content.decode()
    assert "Qarshi" in page and "Buxoro" in page  # both home cities are still offered
    r = client.get(reverse("rating"), {"country": "UZ", "city": "Qarshi", "school": "Osiyo xalqaro universiteti"})
    assert [u.username for u in r.context["users"]] == ["ali"]
