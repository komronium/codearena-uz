import pytest
from django.urls import reverse

from apps.problems.models import Language, Problem
from apps.submissions.models import Submission, UserProblemSolved

from .models import User


@pytest.mark.django_db
def test_register_creates_user_and_logs_in(client):
    r = client.post(reverse("register"), {
        "username": "ali", "email": "ali@example.com", "first_name": "Ali",
        "password1": "StrongPass123!", "password2": "StrongPass123!",
    })
    assert r.status_code == 302
    u = User.objects.get(username="ali")
    assert u.rating == 1200 and u.practice_points == 0 and u.role == "student"
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
    User.objects.create_user("low", password="x", rating=1400)
    User.objects.create_user("high", password="x", rating=1800)
    r = client.get(reverse("rating"))
    assert r.status_code == 200
    users = list(r.context["users"])
    assert [u.username for u in users[:2]] == ["high", "low"]


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
