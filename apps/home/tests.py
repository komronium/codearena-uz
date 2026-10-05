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
    # the decorative code sample scrolls on a phone; inert keeps it out of the tab order, aria-hidden alone does not
    assert '<div class="relative mx-auto w-full min-w-0 max-w-lg lg:mr-0" inert>' in page



@pytest.mark.django_db
def test_landing_hero_announces_the_running_or_next_round(client, world):
    now = timezone.now()
    r = client.get("/")
    assert r.context["next_round"].title == "Keyingi raund" and "Kelgusi musobaqa" in r.content.decode()
    group = Group.objects.create(name="201", teacher=User.objects.get(username="author"))
    Contest.objects.create(title="Guruh raundi", start=now - timezone.timedelta(minutes=5),
                           end=now + timezone.timedelta(hours=1), require_group=group)
    assert client.get("/").context["next_round"].title == "Keyingi raund"  # a group's own round isn't advertised
    Contest.objects.create(title="Jonli raund", start=now - timezone.timedelta(minutes=5), end=now + timezone.timedelta(hours=1))
    r = client.get("/")
    assert r.context["next_round"].title == "Jonli raund" and "Jonli musobaqa" in r.content.decode()


@pytest.mark.django_db
def test_daily_box_shows_no_zero_streak_records(client, world):
    client.force_login(User.objects.create_user("yangi", password="x"))
    page = client.get("/").content.decode()
    assert "Seriyani bugun boshlang" in page and "eng uzuni 0" not in page

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


@pytest.mark.django_db
def test_robots_keep_crawlers_out_of_staff_and_personal_pages_and_name_the_sitemap(client):
    r = client.get("/robots.txt")
    assert r.status_code == 200 and r["Content-Type"].startswith("text/plain")
    body = r.content.decode()
    assert "Disallow: /moderation/" in body and "Disallow: /submissions/" in body
    assert "Disallow: /media/avatars/" in body  # students' photos stay out of image search
    # a list's search, sorting and random pick are endless addresses for one list; its pages stay open
    assert "Disallow: /*?sort=" in body and "Disallow: /*&sort=" in body and "Disallow: /*?random=" in body
    assert "page=" not in body and "tag=" not in body
    assert "Sitemap: http://testserver/sitemap.xml" in body


def _sitemap(client, section=None) -> str:
    r = client.get(f"/sitemap-{section}.xml" if section else "/sitemap.xml")
    assert r.status_code == 200
    return r.content.decode()


@pytest.mark.django_db
def test_sitemap_lists_only_what_a_guest_can_open(client, world):
    from apps.contests.models import ContestProblem
    from apps.learn.models import StudyPlan

    open_problem, hidden, sealed, _ = world
    hidden.is_public = False
    hidden.save()
    upcoming = Contest.objects.get(title="Keyingi raund")
    ContestProblem.objects.create(contest=upcoming, problem=sealed, label="A")  # not before the start
    StudyPlan.objects.create(slug="sikllar", title="Sikllar", is_public=True)
    StudyPlan.objects.create(slug="qoralama", title="Qoralama")
    teacher = User.objects.create_user("ustoz-sm", password="x")
    now = timezone.now()
    own = Contest.objects.create(title="Guruh raundi", start=now, end=now,
                                 require_group=Group.objects.create(name="G", teacher=teacher))
    ended = Contest.objects.create(title="O‘tgan raund", start=now - timezone.timedelta(days=2),
                                   end=now - timezone.timedelta(days=2, hours=-2))

    index = _sitemap(client)  # one sitemap per kind, so Search Console reports each apart
    for section in ("sections", "problems", "courses", "contests", "standings", "profiles"):
        assert f"http://testserver/sitemap-{section}.xml" in index
    problems = _sitemap(client, "problems")
    assert "/problems/p0/" in problems and "/problems/p1/" not in problems and "/problems/p2/" not in problems
    assert "<lastmod>" in problems
    courses = _sitemap(client, "courses")
    assert "/learn/sikllar/" in courses and "/learn/qoralama/" not in courses
    contests = _sitemap(client, "contests")
    assert f"/contests/{upcoming.pk}/" in contests and f"/contests/{own.pk}/" not in contests
    # results once a round has begun, dated by its end
    standings = _sitemap(client, "standings")
    assert f"/contests/{ended.pk}/standings/" in standings and f"/contests/{upcoming.pk}/standings/" not in standings
    assert f"<lastmod>{ended.end:%Y-%m-%d}" in standings
    assert "/accounts/register/" not in _sitemap(client, "sections")


def _jsonld(page: str) -> list[dict]:
    """The page's JSON-LD blocks, parsed."""
    import json

    return [json.loads(chunk.split(">", 1)[1].split("</script>", 1)[0])
            for chunk in page.split('<script type="application/ld+json"')[1:]]


def _robots(page: str) -> str:
    return page.split('<meta name="robots" content="', 1)[1].split('"', 1)[0]


@pytest.mark.django_db
def test_profiles_are_indexed_once_they_have_something_on_them(client, world):
    from apps.contests.models import Participation
    from apps.submissions.models import UserProblemSolved

    lang = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    users = {n: User.objects.create_user(n, password="x") for n in ("solver", "empty", "blocked")}
    solver, blocked = users["solver"], users["blocked"]
    for u in (solver, blocked):
        sub = Submission.objects.create(user=u, problem=world[0], language=lang, source="x", verdict="AC")
        UserProblemSolved.objects.get_or_create(user=u, problem=world[0], defaults={"first_ac_submission": sub})
    blocked.is_active = False
    blocked.save()
    rated = User.objects.create_user("rated", password="x")
    past = Contest.objects.create(title="R", is_rated=True, start=timezone.now() - timezone.timedelta(days=3),
                                  end=timezone.now() - timezone.timedelta(days=3, hours=-2))
    Participation.objects.create(user=rated, contest=past, rating_before=0, rating_after=40)

    profiles = _sitemap(client, "profiles")
    assert "/accounts/profile/solver/" in profiles and "/accounts/profile/rated/" in profiles
    assert "/accounts/profile/empty/" not in profiles and "/accounts/profile/blocked/" not in profiles
    robots = {name: _robots(client.get(reverse("profile", args=[name])).content.decode())
              for name in ("solver", "rated", "empty", "blocked")}
    assert robots["solver"] == robots["rated"] == "max-image-preview:large"
    assert robots["empty"] == robots["blocked"] == "noindex, follow"
    page = client.get(reverse("profile", args=["solver"])).content.decode()
    assert '"@type": "ProfilePage"' in page and '"name": "solver"' in page
    assert '<meta property="og:type" content="profile">' in page


@pytest.mark.django_db
def test_home_names_the_site_for_google(client, world, settings):
    settings.SITE_SAME_AS = ["https://t.me/codearena_uz"]
    page = client.get("/").content.decode()
    site, org = _jsonld(page)
    assert site["@type"] == "WebSite" and site["name"] == "CodeArena" and site["url"] == "http://testserver/"
    assert "CodeArena.uz" in site["alternateName"]  # other sites are called CodeArena too
    assert org["@type"] == "Organization" and org["logo"] == "http://testserver/static/img/icon-512.png"
    assert org["sameAs"] == ["https://t.me/codearena_uz"]
    assert '<meta property="og:site_name" content="CodeArena">' in page


@pytest.mark.django_db
def test_icons_google_and_phones_can_use(client):
    page = client.get(reverse("login")).content.decode()
    # Google reads no SVG for a result's icon: a PNG over 48px beside it, and the root .ico
    assert 'href="/static/img/favicon-96x96.png" type="image/png" sizes="96x96"' in page
    assert '<link rel="icon" href="/favicon.ico"' in page and 'rel="apple-touch-icon"' in page
    r = client.get("/favicon.ico")
    assert r.status_code == 200 and r["Content-Type"] == "image/x-icon" and b"".join(r.streaming_content)[:4] == b"\0\0\1\0"
    m = client.get("/manifest.webmanifest")
    assert m["Content-Type"] == "application/manifest+json"
    assert {i["sizes"] for i in m.json()["icons"]} == {"192x192", "512x512"} and m.json()["name"] == "CodeArena"


@pytest.mark.django_db
def test_head_names_the_page_for_search_and_link_previews(client, world):
    p = world[0]
    p.statement_md = 'Agar son juft bo‘lsa, "HA" chiqaring.\n\n**Cheklov:** 1 < n'
    p.title = "</script> & co"  # JSON-LD must not end early
    p.save()
    page = client.get(reverse("problems:detail", args=[p.slug])).content.decode()
    assert "<title>&lt;/script&gt; &amp; co — CodeArena</title>" in page
    # the statement as plain text, escaped once, for both search and link previews
    described = 'content="Agar son juft bo‘lsa, &quot;HA&quot; chiqaring. Cheklov: 1 &lt; n"'
    assert f'<meta name="description" {described}>' in page and f'<meta property="og:description" {described}>' in page
    assert '<meta property="og:title" content="&lt;/script&gt; &amp; co — CodeArena">' in page
    assert f'<link rel="canonical" href="http://testserver/problems/{p.slug}/">' in page
    assert 'property="og:image" content="http://testserver/static/img/og.png"' in page
    assert '<meta name="twitter:card" content="summary_large_image">' in page
    # the trail desktop results show: Masalalar › the problem
    (trail,) = _jsonld(page)
    assert [(i["name"], i["item"]) for i in trail["itemListElement"]] == [
        ("Masalalar", "http://testserver/problems/"), ("</script> & co", f"http://testserver/problems/{p.slug}/")]
    assert "\\u003C/script\\u003E \\u0026 co" in page
    # filters fold into the list itself; a plain list keeps its page and says so in its title
    listing = reverse("problems:list")
    assert f'rel="canonical" href="http://testserver{listing}"' in client.get(listing + "?tag=x&page=2").content.decode()
    paged = client.get(listing + "?page=2").content.decode()
    assert f'rel="canonical" href="http://testserver{listing}?page=2"' in paged
    assert "<title>Masalalar — 2-sahifa — CodeArena</title>" in paged


@pytest.mark.django_db
def test_private_pages_and_group_rounds_stay_out_of_the_index(client, world, settings):
    assert _robots(client.get(reverse("problems:list")).content.decode()) == "max-image-preview:large"
    client.force_login(User.objects.create_user("boss", password="x", is_staff=True))
    assert _robots(client.get(reverse("moderation:dashboard")).content.decode()) == "noindex"
    client.logout()
    teacher = User.objects.create_user("ustoz-r", password="x")
    own = Contest.objects.create(title="Guruh", start=timezone.now(), end=timezone.now() + timezone.timedelta(hours=1),
                                 require_group=Group.objects.create(name="G", teacher=teacher))
    assert _robots(client.get(reverse("contests:detail", args=[own.pk])).content.decode()) == "noindex"
    assert _robots(client.get(reverse("contests:standings", args=[own.pk])).content.decode()) == "noindex"
    open_round = Contest.objects.get(title="Keyingi raund")
    page = client.get(reverse("contests:detail", args=[open_round.pk])).content.decode()
    assert _robots(page) == "max-image-preview:large" and '"@type": "BreadcrumbList"' in page
    # the verification tags of Search Console and Yandex, once their codes are set
    assert "google-site-verification" not in page
    settings.SITE_VERIFICATION = {"google-site-verification": "abc", "yandex-verification": ""}
    page = client.get("/").content.decode()
    assert '<meta name="google-site-verification" content="abc">' in page and "yandex-verification" not in page


@pytest.mark.django_db
def test_footer_links_every_public_place(client):
    footer = client.get(reverse("login")).content.decode().split('<footer class="ca-footer">', 1)[1].split("</footer>")[0]
    for name in ("problems:list", "learn:hub", "contests:list", "rating", "top", "honor"):
        assert f'href="{reverse(name)}"' in footer


def test_no_template_comment_spreads_over_lines():
    """{# #} ends on its own line; one spread over several lines is printed as page text."""
    from pathlib import Path

    templates = Path(__file__).resolve().parents[2] / "templates"
    bad = [f"{path.relative_to(templates)}:{n}" for path in templates.rglob("*.html")
           for n, line in enumerate(path.read_text().splitlines(), 1) if "{#" in line and "#}" not in line]
    assert bad == []
