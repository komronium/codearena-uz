import pytest
from django.urls import reverse

from apps.problems.models import Language, Problem
from apps.submissions.models import Submission, UserProblemSolved

from .models import User


@pytest.mark.django_db
def test_register_creates_user_and_logs_in(client):
    r = client.post(reverse("register"), {
        "username": "ali", "password1": "StrongPass123!", "password2": "StrongPass123!",
    })
    assert r.status_code == 302
    u = User.objects.get(username="ali")
    assert u.rating == 1500 and u.practice_points == 0 and u.role == "student"
    assert client.session["_auth_user_id"] == str(u.pk)


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
def test_rating_lists_users_by_rating_desc(client):
    User.objects.create_user("low", password="x", rating=1400)
    User.objects.create_user("high", password="x", rating=1800)
    r = client.get(reverse("rating"))
    assert r.status_code == 200
    users = list(r.context["users"])
    assert [u.username for u in users[:2]] == ["high", "low"]
