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

    author = User.objects.create_user("teacher", password="x", role="teacher")
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
    from apps.accounts.tiers import streak_badges
    b = streak_badges(current=0, best=6)
    assert b["earned"] == [] and b["next"]["name"] == "Chiroq" and b["next"]["left"] == 7
    b = streak_badges(current=3, best=40)
    assert [x["name"] for x in b["earned"]] == ["Chiroq", "Mash’al"] and b["next"]["left"] == 97


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
