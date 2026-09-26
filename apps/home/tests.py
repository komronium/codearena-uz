import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Group, User
from apps.classroom.models import Assignment, AssignmentProblem, Duel
from apps.contests.models import Contest
from apps.problems.models import Language, Problem
from apps.submissions.models import Submission


@pytest.fixture
def world(db):
    author = User.objects.create_user("author", password="x")
    problems = [Problem.objects.create(slug=f"p{i}", title=f"Masala {i}", statement_md="x", author=author,
                                       difficulty="easy") for i in range(4)]
    Contest.objects.create(title="Keyingi raund", start=timezone.now() + timezone.timedelta(days=1),
                           end=timezone.now() + timezone.timedelta(days=1, hours=2))
    return problems


@pytest.mark.django_db
def test_guests_get_the_landing_page(client, world):
    r = client.get("/")
    page = r.content.decode()
    assert r.status_code == 200 and "home/landing.html" in [t.name for t in r.templates]
    assert "Ro‘yxatdan o‘tish" in page and "Keyingi raund" in page and "0 ishtirokchi" in page
    assert r.context["daily"] is not None and r.context["stats"]["problems"] == 4


@pytest.mark.django_db
def test_signed_in_home_gathers_what_to_do_next(client, world):
    ali = User.objects.create_user("ali", password="x", first_name="Ali")
    bob = User.objects.create_user("bob", password="x")
    teacher = User.objects.create_user("ustoz", password="x")
    g = Group.objects.create(name="201", teacher=teacher)
    g.members.add(ali)
    now = timezone.now()
    soon = Assignment.objects.create(group=g, title="Tez orada", created_by=teacher,
                                     start=now - timezone.timedelta(days=1), deadline=now + timezone.timedelta(hours=5))
    later = Assignment.objects.create(group=g, title="Keyinroq", created_by=teacher,
                                      start=now, deadline=now + timezone.timedelta(days=5))
    past = Assignment.objects.create(group=g, title="O‘tgan", created_by=teacher,
                                     start=now - timezone.timedelta(days=9), deadline=now - timezone.timedelta(days=2))
    for a in (soon, later, past):
        AssignmentProblem.objects.create(assignment=a, problem=world[0])
        AssignmentProblem.objects.create(assignment=a, problem=world[1])
    lang = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    Submission.objects.create(user=ali, problem=world[0], language=lang, source="x", verdict="AC")
    Duel.objects.create(challenger=bob, opponent=ali, difficulty="easy")

    client.force_login(ali)
    r = client.get("/")
    page = r.content.decode()
    assert "home/dashboard.html" in [t.name for t in r.templates]
    assert [a.title for a in r.context["homework"]] == ["Tez orada", "Keyinroq"]  # open ones, due soonest first
    assert r.context["homework"][0].my_solved == 1 and r.context["homework"][0].my_total == 2
    assert [d.challenger.username for d in r.context["challenges"]] == ["bob"]
    assert "Salom, Ali" in page and "Keyingi raund" in page and "Tez orada" in page
    assert r.context["recent"][0].problem == world[0]


@pytest.mark.django_db
def test_login_lands_on_home(client, world):
    User.objects.create_user("ali", password="StrongPass123!")
    r = client.post(reverse("login"), {"username": "ali", "password": "StrongPass123!"})
    assert r.status_code == 302 and r.url == reverse("home")


@pytest.mark.parametrize("n, shown", [(0, "0"), (874, "874"), (1000, "1 ming"), (1284, "1,3 ming"),
                                      (12_940, "13 ming"), (2_400_000, "2,4 mln")])
def test_compact_counts(n, shown):
    from apps.problems.templatetags.numbers import compact

    assert compact(n) == shown
