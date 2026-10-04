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


@pytest.mark.django_db
def test_landing_podium_is_the_last_rated_contests_real_standings(client, world):
    from apps.contests.models import ContestProblem, Participation

    now = timezone.now()
    c = Contest.objects.create(title="1-raund", is_rated=True, start=now - timezone.timedelta(hours=3),
                               end=now - timezone.timedelta(hours=1))
    ContestProblem.objects.create(contest=c, problem=world[0], label="A")
    lang = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    users = {n: User.objects.create_user(n, password="x") for n in ("a1", "a2", "a3", "a4")}
    for i, u in enumerate(users.values()):  # stored rank/score deliberately stale: standings decide
        Participation.objects.create(user=u, contest=c, rating_before=1200, rating_after=1200, rank=4 - i, score=999)
    for name, minutes in (("a3", 10), ("a2", 20)):
        s = Submission.objects.create(user=users[name], problem=world[0], contest=c, language=lang,
                                      source="x", verdict="AC")
        Submission.objects.filter(pk=s.pk).update(created=c.start + timezone.timedelta(minutes=minutes))
    r = client.get("/")
    assert r.context["last_rated"] == c and len(r.context["podium"]) == 3
    assert [row["user"].username for row in r.context["podium"][:2]] == ["a3", "a2"]
    assert "1-raund" in r.content.decode()


@pytest.mark.django_db
def test_home_rating_card_and_date(client, world):
    from apps.contests.models import Participation

    ali = User.objects.create_user("ali", password="x", rating=1180)
    rated = Contest.objects.create(title="R", is_rated=True, start=timezone.now() - timezone.timedelta(days=3),
                                   end=timezone.now() - timezone.timedelta(days=3) + timezone.timedelta(hours=2))
    Participation.objects.create(user=ali, contest=rated, rating_before=1200, rating_after=1180)
    client.force_login(ali)
    r = client.get("/")
    card = r.context["rating_card"]
    assert card["delta"] == -20 and card["rank"] == 1 and card["total"] == 1
    assert card["next"]["name"] == "Candidate Master" and card["next"]["need"] == 120
    weekday, day_month = r.context["today_label"].split(", ")
    assert weekday in {"Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"}
    assert day_month == f"{timezone.localdate().day}-" + day_month.split("-", 1)[1]
    assert "Master</span> darajasigacha" in r.content.decode()


@pytest.mark.django_db
def test_top_bar_offers_admin_to_staff_only(client, world):
    client.force_login(User.objects.create_user("ali", password="x"))
    links = client.get("/").content.decode().split('class="ca-nav-links"', 1)[1].split("</nav>", 1)[0]
    assert reverse("problems:list") in links and reverse("moderation:dashboard") not in links
    client.force_login(User.objects.create_user("boss", password="x", is_staff=True))
    links = client.get("/").content.decode().split('class="ca-nav-links"', 1)[1].split("</nav>", 1)[0]
    assert reverse("moderation:dashboard") in links


@pytest.mark.django_db
def test_nav_shows_a_running_contest_and_homework_due_soon(client):
    from datetime import timedelta

    from django.core.cache import cache
    from django.utils import timezone

    from apps.accounts.models import Group, User
    from apps.classroom.models import Assignment, AssignmentProblem
    from apps.contests.models import Contest, Participation
    from apps.problems.models import Problem

    cache.clear()
    teacher = User.objects.create_user("navt", password="x")
    me = User.objects.create_user("navs", password="x")
    now = timezone.now()
    live = Contest.objects.create(title="Jonli sinov", start=now - timedelta(hours=1), end=now + timedelta(hours=1))
    Participation.objects.create(user=me, contest=live)
    g = Group.objects.create(name="G", teacher=teacher)
    g.members.add(me)
    p = Problem.objects.create(slug="navp", title="P", statement_md="x", author=teacher)
    a = Assignment.objects.create(group=g, title="Uy ishi", start=now - timedelta(days=1), deadline=now + timedelta(hours=20))
    AssignmentProblem.objects.create(assignment=a, problem=p, order=0)
    client.force_login(me)

    page = client.get("/problems/").content.decode()
    assert "ca-live-pill" in page and "Musobaqangiz davom etmoqda" in page  # the clock, from any page
    assert "ca-badge-live" in page and "1 ta vazifa muddati 2 kun ichida tugaydi" in page
    assert "ca-live-pill" not in client.get("/").content.decode()  # home has its own live strip


@pytest.mark.django_db
def test_nav_does_not_advertise_a_contest_for_another_group(client):
    from datetime import timedelta

    from django.utils import timezone

    from apps.accounts.models import Group, User
    from apps.contests.models import Contest

    teacher = User.objects.create_user("gt", password="x")
    inside, outside = User.objects.create_user("gin", password="x"), User.objects.create_user("gout", password="x")
    g = Group.objects.create(name="2-kurs", teacher=teacher)
    g.members.add(inside)
    now = timezone.now()
    Contest.objects.create(title="Faqat 2-kurs", start=now - timedelta(hours=1), end=now + timedelta(hours=1), require_group=g)

    client.force_login(outside)
    assert "ca-live-pill" not in client.get("/problems/").content.decode()
    client.force_login(inside)
    page = client.get("/problems/").content.decode()
    assert "ca-live-pill" in page and "Jonli musobaqa" in page


@pytest.mark.django_db
def test_home_strip_and_nav_point_at_the_contest_you_are_in(client):
    """Two contests at once: both the home strip and the top-bar pill take yours, not the one ending first."""
    from datetime import timedelta

    from django.utils import timezone

    from unittest.mock import patch

    from apps.accounts.models import User
    from apps.contests.models import Contest, Participation
    from apps.home.context_processors import live_contest_for

    me = User.objects.create_user("two", password="x")
    now = timezone.now()
    Contest.objects.create(title="Tezroq tugaydi", start=now - timedelta(hours=1), end=now + timedelta(minutes=30))
    mine = Contest.objects.create(title="Meniki", start=now - timedelta(hours=1), end=now + timedelta(hours=2))
    Participation.objects.create(user=me, contest=mine)
    starts_soon = Contest.objects.create(title="Hozir boshlanadi", start=now + timedelta(seconds=5),
                                         end=now + timedelta(hours=1))
    client.force_login(me)

    home = client.get("/")
    assert home.context["live"]["contest"] == mine and home.context["live"]["joined"]
    assert 'title="Meniki (+1 ta boshqa jonli)"' in client.get("/problems/").content.decode()
    # the list was cached before the third contest started; it still counts the moment it does
    assert live_contest_for(me)["count"] == 2
    with patch("apps.home.context_processors.timezone.now", return_value=starts_soon.start + timedelta(seconds=1)):
        assert live_contest_for(me)["count"] == 3


def test_server_error_page_renders_without_any_context():
    """Django renders 500.html with no request or context processors: the brand mark include must still work."""
    from django.template.loader import render_to_string

    html = render_to_string("500.html")
    assert "Serverda xatolik" in html and 'class="ca-brand-star"' in html

