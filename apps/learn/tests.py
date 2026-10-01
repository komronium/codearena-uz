from io import StringIO

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.learn.models import RESERVED_SLUGS, StudyPlan
from apps.learn.progress import plan_progress, plan_sections
from apps.problems.models import Language, Problem, Tag
from apps.submissions.models import Submission, UserProblemSolved


def _problem(slug, author, *tags, **kw):
    p = Problem.objects.create(slug=slug, title=slug.upper(), statement_md="x", author=author, **kw)
    p.tags.add(*[Tag.objects.get_or_create(name=t)[0] for t in tags])
    return p


def _solve(user, problem, when=None):
    lang, _ = Language.objects.get_or_create(code="python", defaults=dict(name="Python 3", docker_image="x",
                                                                          run_cmd="x"))
    s = Submission.objects.create(user=user, problem=problem, language=lang, source="x", verdict="AC")
    row = UserProblemSolved.objects.create(user=user, problem=problem, first_ac_submission=s)
    if when is not None:
        UserProblemSolved.objects.filter(pk=row.pk).update(solved_at=when)


def _course(slug, *tags, title="Kurs", **kw):
    course = StudyPlan.objects.create(slug=slug, title=title, **{"is_public": True, **kw})
    course.tags.add(*[Tag.objects.get_or_create(name=t)[0] for t in tags])
    return course


@pytest.fixture
def staff():
    return User.objects.create_user("admin", password="x", is_staff=True)


@pytest.fixture
def ali():
    return User.objects.create_user("ali", password="x")


# ---- progress ----------------------------------------------------------------

@pytest.mark.django_db
def test_progress_ignores_hidden_problems(staff, ali):
    shown, hidden = _problem("a", staff, "t"), _problem("b", staff, "t", is_public=False)
    course = _course("c", "t")
    _solve(ali, hidden)
    assert plan_progress(ali, [course])[course.pk] == {"done": 0, "total": 1, "pct": 0, "completed": False}
    _solve(ali, shown)
    assert plan_progress(ali, [course])[course.pk]["completed"] is True


@pytest.mark.django_db
def test_course_without_open_problems_is_never_completed(staff, ali):
    _problem("b", staff, "t", is_public=False)
    for course in (_course("c", "t"), _course("theory-only")):
        assert plan_progress(ali, [course])[course.pk] == {"done": 0, "total": 0, "pct": 0, "completed": False}


@pytest.mark.django_db
def test_a_problem_counts_in_every_course_it_belongs_to(staff, ali):
    p = _problem("lis", staff, "binary-search", "dynamic-programming")
    one, two = _course("bs", "binary-search"), _course("dp", "dynamic-programming")
    _solve(ali, p)
    progress = plan_progress(ali, [one, two])
    assert progress[one.pk]["completed"] and progress[two.pk]["completed"]


@pytest.mark.django_db
def test_course_groups_by_difficulty_easiest_first(staff, ali):
    _problem("h", staff, "t", difficulty=Problem.Difficulty.HARD)  # created first, listed last
    _problem("e", staff, "t", "u", difficulty=Problem.Difficulty.EASY)  # two of the course's tags: counted once
    first = _problem("b1", staff, "t", difficulty=Problem.Difficulty.BEGINNER)
    second = _problem("b2", staff, "u", difficulty=Problem.Difficulty.BEGINNER)
    course = _course("c", "t", "u")
    _solve(ali, first)
    assert plan_sections(ali, [course])[course.pk] == {
        "sections": [{"level": "beginner", "label": "Beginner", "done": 1, "total": 2, "complete": False},
                     {"level": "easy", "label": "Easy", "done": 0, "total": 1, "complete": False},
                     {"level": "hard", "label": "Hard", "done": 0, "total": 1, "complete": False}],
        "next_id": second.pk}


# ---- hub and course pages ----------------------------------------------------

@pytest.mark.django_db
def test_hub_and_course_render_for_anonymous(client, staff):
    _problem("a", staff, "t")
    _course("birinchi", "t", title="Birinchi qadam")
    r = client.get(reverse("learn:hub"))
    assert r.status_code == 200 and "Birinchi qadam" in r.content.decode()
    r = client.get(reverse("learn:course", args=["birinchi"]))
    assert r.status_code == 200 and ">A<" in r.content.decode()


@pytest.mark.django_db
def test_course_page_shows_progress_groups_and_next(client, staff, ali):
    a, b = (_problem(s, staff, "t", difficulty=Problem.Difficulty.BEGINNER) for s in "ab")
    _problem("c", staff, "t", difficulty=Problem.Difficulty.EASY)
    _course("p", "t")
    _solve(ali, a)
    _solve(ali, b)
    client.force_login(ali)
    body = client.get(reverse("learn:course", args=["p"])).content.decode()
    assert "2/2" in body and "0/1" in body  # Beginner done, Easy not yet
    assert body.index(">Beginner<") < body.index(">Easy<")
    assert 'href="/problems/c/?plan=p"' in body and "Davom etish" in body


@pytest.mark.django_db
def test_course_page_hides_hidden_problem(client, staff, ali):
    _problem("open-one", staff, "t")
    _problem("secret-one", staff, "t", is_public=False)
    _course("p", "t")
    client.force_login(ali)
    body = client.get(reverse("learn:course", args=["p"])).content.decode()
    assert "OPEN-ONE" in body and "SECRET-ONE" not in body and "0/1" in body


@pytest.mark.django_db
def test_private_course_404_for_students_not_staff(client, staff, ali):
    _course("p", title="Yashirin kurs", is_public=False)
    client.force_login(ali)
    assert client.get(reverse("learn:course", args=["p"])).status_code == 404
    assert "Yashirin kurs" not in client.get(reverse("learn:hub")).content.decode()
    client.force_login(staff)
    assert client.get(reverse("learn:course", args=["p"])).status_code == 200


@pytest.mark.django_db
def test_course_shows_theory_before_problems_exist(client):
    _course("heap", "heap", title="Ustuvor navbat", theory_md="Uyum eng kichik elementni **tez** beradi.")
    _course("complexity", title="Murakkablik", theory_md="O(n)")
    body = client.get(reverse("learn:course", args=["heap"])).content.decode()
    assert "<strong>tez</strong>" in body and "tayyorlanmoqda" in body
    assert "faqat nazariya" in client.get(reverse("learn:course", args=["complexity"])).content.decode()
    hub = client.get(reverse("learn:hub")).content.decode()
    assert "Tayyorlanmoqda" in hub and "Nazariya" in hub and "is-soon" in hub


@pytest.mark.django_db
def test_course_theory_is_sanitized(client):
    _course("x", theory_md="salom <script>alert(1)</script>")
    assert "<script>alert" not in client.get(reverse("learn:course", args=["x"])).content.decode()


@pytest.mark.django_db
def test_hub_groups_courses_by_stage_in_path_order(client, staff):
    _course("later", title="Graf kursi", stage=StudyPlan.Stage.GRAPHS, order=1)
    _course("first", title="Kiritish kursi", stage=StudyPlan.Stage.BASICS, order=9)
    body = client.get(reverse("learn:hub")).content.decode()
    assert body.index("Asoslar") < body.index("Kiritish kursi") < body.index(">Graflar<") < body.index("Graf kursi")


@pytest.mark.django_db
def test_hub_continues_the_course_solved_in_last(client, staff, ali):
    a1, _ = _problem("a1", staff, "a"), _problem("a2", staff, "a")
    b1, b2 = _problem("b1", staff, "b"), _problem("b2", staff, "b")
    _course("aa", "a", title="Birinchi", order=1)
    _course("bb", "b", title="Ikkinchi", order=2)
    client.force_login(ali)
    body = client.get(reverse("learn:hub")).content.decode()
    assert 'href="/problems/a1/?plan=aa"' in body  # nothing solved: the first course with problems
    now = timezone.now()
    _solve(ali, a1, when=now - timezone.timedelta(days=1))
    _solve(ali, b1, when=now)
    body = client.get(reverse("learn:hub")).content.decode()
    assert 'href="/problems/b2/?plan=bb"' in body and "Siz shu yerdasiz" in body
    _solve(ali, b2)  # a finished course is never "current"
    assert 'href="/problems/a2/?plan=aa"' in client.get(reverse("learn:hub")).content.decode()


# ---- old addresses -----------------------------------------------------------

@pytest.mark.django_db
def test_old_plan_addresses_redirect(client):
    r = client.get("/learn/plans/birinchi-qadam/")
    assert r.status_code == 302 and r.url == "/learn/input-output/"
    assert client.get("/learn/plans/arrays/").url == "/learn/arrays/"


@pytest.mark.django_db
def test_old_topic_addresses_redirect(client, staff):
    _course("dictionaries", "hash-table")
    _problem("a", staff, "implementation")
    assert client.get("/learn/topics/").url == "/learn/"
    assert client.get("/learn/topics/loops/").url == "/learn/for-loop/"
    assert client.get("/learn/topics/hash-table/").url == "/learn/dictionaries/"
    assert client.get("/learn/topics/implementation/").url == "/problems/?tag=implementation"
    assert client.get("/learn/topics/nope/").status_code == 404


@pytest.mark.django_db
def test_reserved_paths_are_not_courses(client, ali):
    _course("lists", title="Ro‘yxat kursi")  # can't be made through the form or add_courses; see below
    client.force_login(ali)
    assert "Ro‘yxat kursi" not in client.get("/learn/lists/").content.decode()


# ---- search (Ctrl K) ---------------------------------------------------------

@pytest.mark.django_db
def test_course_search_matches_title_and_theory(client, ali):
    _course("heap", title="Ustuvor navbat", theory_md="heapq bilan eng kichigi", stage=StudyPlan.Stage.STRUCTURES)
    _course("secret", title="Yashirin navbat", is_public=False)
    url = reverse("learn:search")
    assert client.get(url, {"q": "n"}).json() == {"results": []}
    rows = client.get(url, {"q": "navbat"}).json()["results"]
    assert [r["title"] for r in rows] == ["Ustuvor navbat"]
    assert rows[0] == {"title": "Ustuvor navbat", "url": "/learn/heap/", "icon": "book-open",
                       "hint": "Ma’lumot tuzilmalari"}
    assert client.get(url, {"q": "heapq"}).json()["results"][0]["hint"] == "nazariyada"


# ---- course strip on the problem page -----------------------------------------

@pytest.mark.django_db
def test_problem_page_shows_course_strip_with_neighbours(client, staff, ali):
    a, _, _ = (_problem(s, staff, "t") for s in ("a1", "b1", "c1"))
    _course("p", "t", title="Mening kursim")
    _solve(ali, a)
    client.force_login(ali)
    body = client.get(reverse("problems:detail", args=["b1"]) + "?plan=p").content.decode()
    assert "Mening kursim" in body and "1/3" in body
    assert 'href="/problems/c1/?plan=p"' in body and 'href="/problems/a1/?plan=p"' in body


@pytest.mark.django_db
def test_problem_page_ignores_bad_plan_param(client, staff, ali):
    _problem("a1", staff, "a")
    _problem("z1", staff, "z")
    _course("p", "z", title="Boshqa kurs")
    _course("h", "a", title="Yopiq kurs", is_public=False)
    client.force_login(ali)
    for q in ("?plan=nope", "?plan=p", "?plan=h", "?plan=", "?plan=%00"):
        r = client.get(reverse("problems:detail", args=["a1"]) + q)
        assert r.status_code == 200
        assert "Boshqa kurs" not in r.content.decode() and "Yopiq kurs" not in r.content.decode()


@pytest.mark.django_db
def test_profile_shows_completed_course_badge(client, staff, ali):
    a = _problem("a1", staff, "a")
    _problem("b1", staff, "b")
    _course("p", "a", title="Birinchi qadam")
    _course("q", "b", title="Tugamagan kurs")
    _course("r", title="Faqat nazariya")
    url = reverse("profile", args=[ali.username])
    assert "Birinchi qadam" not in client.get(url).content.decode()
    _solve(ali, a)
    body = client.get(url).content.decode()
    assert "Birinchi qadam" in body and "Tugamagan kurs" not in body and "Faqat nazariya" not in body


# ---- my lists ----------------------------------------------------------------

@pytest.mark.django_db
def test_list_privacy_and_ownership(client, staff, ali):
    from apps.learn.models import ProblemList

    p = _problem("a1", staff)
    mine = ProblemList.objects.create(owner=ali, name="Keyinroq")
    bob = User.objects.create_user("bob", password="x")
    client.force_login(bob)
    assert client.get(reverse("learn:list", args=[mine.pk])).status_code == 404
    assert client.post(reverse("learn:save", args=[p.slug]), {"list": mine.pk}).status_code == 404
    assert client.post(reverse("learn:list_edit", args=[mine.pk]), {"name": "x"}).status_code == 404
    assert client.post(reverse("learn:list_delete", args=[mine.pk])).status_code == 404
    assert not mine.items.exists() and ProblemList.objects.filter(pk=mine.pk, name="Keyinroq").exists()
    mine.is_public = True
    mine.save()
    assert client.get(reverse("learn:list", args=[mine.pk])).status_code == 200
    client.logout()
    assert client.get(reverse("learn:list", args=[mine.pk])).status_code == 200


@pytest.mark.django_db
def test_cannot_save_hidden_problem(client, staff, ali):
    from apps.learn.models import ProblemList

    hidden = _problem("h1", staff, is_public=False)
    mine = ProblemList.objects.create(owner=ali, name="L")
    client.force_login(ali)
    assert client.post(reverse("learn:save", args=[hidden.slug]), {"list": mine.pk}).status_code == 404
    assert not mine.items.exists()


@pytest.mark.django_db
def test_save_toggles_and_creates_list(client, staff, ali):
    from apps.learn.models import ProblemList

    p = _problem("saqla-meni", staff)
    client.force_login(ali)
    r = client.post(reverse("learn:save", args=[p.slug]), {"list": "new", "name": "Keyinroq"})
    assert r.status_code == 302 and r.url == "/problems/saqla-meni/"
    lst = ProblemList.objects.get(owner=ali)
    assert list(lst.items.values_list("problem__slug", flat=True)) == ["saqla-meni"]
    client.post(reverse("learn:save", args=[p.slug]), {"list": lst.pk})
    assert not lst.items.exists()
    client.post(reverse("learn:save", args=[p.slug]), {"list": lst.pk})
    assert lst.items.count() == 1
    body = client.get(reverse("learn:list", args=[lst.pk])).content.decode()
    assert "SAQLA-MENI" in body
    p.is_public = False
    p.save()
    body = client.get(reverse("learn:list", args=[lst.pk])).content.decode()
    assert "SAQLA-MENI" not in body and "1 ta masala hozir yopiq" in body
    client.post(reverse("learn:list_delete", args=[lst.pk]))
    assert not ProblemList.objects.exists()


@pytest.mark.django_db
def test_save_rejects_external_next(client, staff, ali):
    from apps.learn.models import ProblemList

    p = _problem("a1", staff)
    lst = ProblemList.objects.create(owner=ali, name="L")
    client.force_login(ali)
    r = client.post(reverse("learn:save", args=[p.slug]), {"list": lst.pk, "next": "https://evil.example/"})
    assert r.url == "/problems/a1/"
    r = client.post(reverse("learn:save", args=[p.slug]), {"list": lst.pk, "next": f"/learn/lists/{lst.pk}/"})
    assert r.url == f"/learn/lists/{lst.pk}/"


@pytest.mark.django_db
def test_list_limit_and_problem_page_menu(client, staff, ali):
    from apps.learn.models import MAX_LISTS, ProblemList

    _problem("a1", staff)
    ProblemList.objects.bulk_create([ProblemList(owner=ali, name=f"L{i}") for i in range(MAX_LISTS)])
    client.force_login(ali)
    r = client.post(reverse("learn:lists"), {"name": "yana"})
    assert r.status_code == 200 and "Ko‘pi bilan 50 ta ro‘yxat." in r.content.decode()
    assert ProblemList.objects.filter(owner=ali).count() == MAX_LISTS
    assert "L0" in client.get(reverse("problems:detail", args=["a1"])).content.decode()


# ---- staff editing -----------------------------------------------------------

def _course_post(**over):
    data = {"slug": "yangi", "title": "Yangi kurs", "stage": "basics", "order": "1", "level": "beginner",
            "icon": "book-open", "summary": "", "theory_md": "Nazariya", "description_md": "", "is_public": "on"}
    data.update(over)
    return data


@pytest.mark.django_db
def test_staff_creates_edits_and_deletes_a_course(client, staff):
    loops = Tag.objects.create(name="for-loop")
    _problem("a1", staff, "for-loop")
    client.force_login(staff)
    assert f'value="{loops.pk}"' in client.get(reverse("moderation:plan_new")).content.decode()  # tag checkbox
    r = client.post(reverse("moderation:plan_new"), _course_post(tags=[loops.pk]))
    assert r.status_code == 302 and r.url == "/learn/yangi/"
    course = StudyPlan.objects.get(slug="yangi")
    assert list(course.tags.all()) == [loops] and course.theory_md == "Nazariya"
    assert "1 masala" in client.get(reverse("moderation:plans")).content.decode()
    assert "Nazariya" in client.get(reverse("moderation:plan_edit", args=[course.pk])).content.decode()
    r = client.post(reverse("moderation:plan_edit", args=[course.pk]), _course_post(title="Sikllar", tags=[]))
    assert r.status_code == 302
    course.refresh_from_db()
    assert course.title == "Sikllar" and not course.tags.exists()
    client.post(reverse("moderation:plan_delete", args=[course.pk]))
    assert not StudyPlan.objects.exists() and Problem.objects.count() == 1 and Tag.objects.filter(pk=loops.pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("slug", sorted(RESERVED_SLUGS))
def test_course_form_rejects_reserved_slugs(client, staff, slug):
    client.force_login(staff)
    r = client.post(reverse("moderation:plan_new"), _course_post(slug=slug))
    assert r.status_code == 200 and "Bu nom band" in r.content.decode()
    assert not StudyPlan.objects.exists()


@pytest.mark.django_db
def test_course_pages_require_staff(client, ali):
    client.force_login(ali)
    for url in (reverse("moderation:plans"), reverse("moderation:plan_new")):
        assert client.get(url).status_code == 302


@pytest.mark.django_db
def test_staff_edits_a_tag_and_sees_its_courses(client, staff):
    tag = Tag.objects.create(name="stack")
    _course("stack-queue", "stack", title="Stek va navbat")
    client.force_login(staff)
    assert "Stek va navbat" in client.get(reverse("moderation:tag_edit", args=[tag.pk])).content.decode()
    assert "Stek va navbat" in client.get(reverse("moderation:tags")).content.decode()
    r = client.post(reverse("moderation:tag_edit", args=[tag.pk]), {"name": "stek", "kind": "code"})
    assert r.status_code == 302 and r.url == reverse("moderation:tags")
    tag.refresh_from_db()
    assert tag.name == "stek"


@pytest.mark.django_db
def test_staff_course_list_follows_course_order(client, staff):
    _course("aa", title="Alfa kurs", order=2)
    _course("zz", title="Zeta kurs", order=1)
    client.force_login(staff)
    body = client.get(reverse("moderation:plans")).content.decode()
    assert body.index("Zeta kurs") < body.index("Alfa kurs")


# ---- content commands ----------------------------------------------------------

@pytest.mark.django_db
def test_add_courses_is_idempotent_and_keeps_staff_edits(staff):
    from apps.learn.management.commands.add_courses import COURSES

    StudyPlan.objects.create(slug="birinchi-qadam", title="Eski reja")
    StudyPlan.objects.create(slug="arrays", title="Ro‘yxatlar", theory_md="o‘zim yozdim")
    _problem("a1", staff, "for-loop")
    out = StringIO()
    call_command("add_courses", stdout=out)
    call_command("add_courses", stdout=out)
    assert StudyPlan.objects.count() == len(COURSES) == 38
    assert not StudyPlan.objects.filter(slug="birinchi-qadam").exists()  # the first plans redirect now
    assert StudyPlan.objects.get(slug="arrays").theory_md == "o‘zim yozdim"
    assert not StudyPlan.objects.filter(theory_md="").exists()
    assert not {c[0] for c in COURSES} & RESERVED_SLUGS
    assert Tag.objects.get(name="window-functions").kind == Tag.Kind.SQL
    assert Tag.objects.get(name="for-loop").kind == Tag.Kind.CODE
    assert list(StudyPlan.objects.get(slug="complexity").tags.all()) == []
    sql = StudyPlan.objects.get(slug="sql-select").theory_md
    assert "## WHERE" in sql and "\n## " in sql  # one section per topic


@pytest.mark.django_db
def test_add_courses_dry_run_writes_nothing():
    out = StringIO()
    call_command("add_courses", "--dry-run", stdout=out)
    assert not StudyPlan.objects.exists() and "dry-run" in out.getvalue()


@pytest.mark.django_db
def test_retag_problems_splits_loops_and_math_and_reverses(staff):
    fact = _problem("faktorial", staff, "loops", "math")
    digits = _problem("p1-raqamlar-soni", staff, "loops")
    other = _problem("not-in-table", staff, "strings")
    call_command("retag_problems", "--dry-run", stdout=StringIO())
    assert set(fact.tags.values_list("name", flat=True)) == {"loops", "math"}
    call_command("retag_problems", stdout=StringIO())
    call_command("retag_problems", stdout=StringIO())
    assert set(fact.tags.values_list("name", flat=True)) == {"for-loop", "arithmetic"}
    assert set(digits.tags.values_list("name", flat=True)) == {"while-loop"}
    assert set(other.tags.values_list("name", flat=True)) == {"strings"}
    assert not Tag.objects.filter(name__in=["loops", "math"]).exists()
    call_command("retag_problems", "--reverse", stdout=StringIO())
    assert set(fact.tags.values_list("name", flat=True)) == {"loops", "math"}


@pytest.mark.django_db
def test_retag_keeps_loops_while_a_problem_outside_the_table_has_it(staff):
    _problem("unknown-loop", staff, "loops")
    out = StringIO()
    call_command("retag_problems", stdout=out)
    assert Tag.objects.filter(name="loops").exists() and "unknown-loop" in out.getvalue()


# ---- layout ------------------------------------------------------------------

@pytest.mark.django_db
def test_saved_lists_sit_under_masalalar(client, ali):
    client.force_login(ali)
    assert reverse("learn:lists") in client.get(reverse("problems:list")).content.decode()
    body = client.get(reverse("learn:lists")).content.decode()
    assert f'href="{reverse("problems:list")}" class="ca-sidebar-link is-active"' in body
