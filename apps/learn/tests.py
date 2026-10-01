import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.learn.models import PlanItem, PlanSection, StudyPlan
from apps.learn.progress import plan_progress
from apps.problems.models import Language, Problem
from apps.submissions.models import Submission, UserProblemSolved


def _problem(slug, author, **kw):
    return Problem.objects.create(slug=slug, title=slug.upper(), statement_md="x", author=author, **kw)


def _solve(user, problem):
    lang, _ = Language.objects.get_or_create(code="python", defaults=dict(name="Python 3", docker_image="x",
                                                                          run_cmd="x"))
    s = Submission.objects.create(user=user, problem=problem, language=lang, source="x", verdict="AC")
    UserProblemSolved.objects.create(user=user, problem=problem, first_ac_submission=s)


def _plan(slug, problems, title="Reja", **kw):
    plan = StudyPlan.objects.create(slug=slug, title=title, is_public=True, **kw)
    section = PlanSection.objects.create(plan=plan, title="Bo‘lim")
    for i, p in enumerate(problems):
        PlanItem.objects.create(section=section, problem=p, order=i)
    return plan


@pytest.fixture
def staff():
    return User.objects.create_user("admin", password="x", is_staff=True)


@pytest.fixture
def ali():
    return User.objects.create_user("ali", password="x")


@pytest.mark.django_db
def test_progress_ignores_hidden_problems(staff, ali):
    shown, hidden = _problem("a", staff), _problem("b", staff, is_public=False)
    plan = _plan("p", [shown, hidden])
    _solve(ali, hidden)
    assert plan_progress(ali, [plan])[plan.pk] == {"done": 0, "total": 1, "pct": 0, "completed": False}
    _solve(ali, shown)
    assert plan_progress(ali, [plan])[plan.pk]["completed"] is True


@pytest.mark.django_db
def test_empty_plan_is_not_completed(staff, ali):
    plan = _plan("p", [_problem("b", staff, is_public=False)])
    assert plan_progress(ali, [plan])[plan.pk] == {"done": 0, "total": 0, "pct": 0, "completed": False}


# ---- hub and plan pages ------------------------------------------------------

@pytest.mark.django_db
def test_hub_and_plan_render_for_anonymous(client, staff):
    plan = _plan("birinchi", [_problem("a", staff)], title="Birinchi qadam", in_quest=True)
    r = client.get(reverse("learn:hub"))
    assert r.status_code == 200 and "Birinchi qadam" in r.content.decode()
    r = client.get(reverse("learn:plan", args=[plan.slug]))
    assert r.status_code == 200 and "A" in r.content.decode()


@pytest.mark.django_db
def test_plan_page_shows_progress(client, staff, ali):
    a, b, c = (_problem(s, staff) for s in "abc")
    plan = _plan("p", [a, b, c])
    _solve(ali, a)
    _solve(ali, b)
    client.force_login(ali)
    body = client.get(reverse("learn:plan", args=[plan.slug])).content.decode()
    assert "2/3" in body
    assert f'href="/problems/c/?plan=p"' in body


@pytest.mark.django_db
def test_plan_page_hides_hidden_problem(client, staff, ali):
    plan = _plan("p", [_problem("open-one", staff), _problem("secret-one", staff, is_public=False)])
    client.force_login(ali)
    body = client.get(reverse("learn:plan", args=[plan.slug])).content.decode()
    assert "OPEN-ONE" in body and "SECRET-ONE" not in body and "0/1" in body


@pytest.mark.django_db
def test_private_plan_404_for_students_not_staff(client, staff, ali):
    plan = _plan("p", [_problem("a", staff)], title="Yashirin reja")
    plan.is_public = False
    plan.save()
    client.force_login(ali)
    assert client.get(reverse("learn:plan", args=[plan.slug])).status_code == 404
    assert "Yashirin reja" not in client.get(reverse("learn:hub")).content.decode()
    client.force_login(staff)
    assert client.get(reverse("learn:plan", args=[plan.slug])).status_code == 200


# ---- topics ------------------------------------------------------------------

@pytest.mark.django_db
def test_topic_page_lists_only_open_problems(client, staff):
    from apps.problems.models import Tag

    tag = Tag.objects.update_or_create(name="loops", defaults={"about_md": "**Sikl** — takrorlash."})[0]
    shown, hidden = _problem("open-one", staff), _problem("secret-one", staff, is_public=False)
    shown.tags.add(tag)
    hidden.tags.add(tag)
    _plan("p", [shown], title="Sikllar rejasi")
    assert "loops" in client.get(reverse("learn:topics")).content.decode()
    body = client.get(reverse("learn:topic", args=["loops"])).content.decode()
    assert "OPEN-ONE" in body and "SECRET-ONE" not in body
    assert "<strong>Sikl</strong>" in body and "Sikllar rejasi" in body


@pytest.mark.django_db
def test_unknown_topic_404(client, staff):
    from apps.problems.models import Tag

    Tag.objects.create(name="empty")
    assert client.get(reverse("learn:topic", args=["nope"])).status_code == 404
    assert client.get(reverse("learn:topic", args=["empty"])).status_code == 404


@pytest.mark.django_db
def test_topic_theory_is_sanitized(client, staff):
    from apps.problems.models import Tag

    tag = Tag.objects.create(name="xss", about_md="salom <script>alert(1)</script>")
    _problem("a", staff).tags.add(tag)
    assert "<script>alert" not in client.get(reverse("learn:topic", args=["xss"])).content.decode()


# ---- plan strip on the problem page -------------------------------------------

@pytest.mark.django_db
def test_problem_page_shows_plan_strip_with_next(client, staff, ali):
    a, b, c = (_problem(s, staff) for s in ("a1", "b1", "c1"))
    _plan("p", [a, b, c], title="Mening rejam")
    _solve(ali, a)
    client.force_login(ali)
    body = client.get(reverse("problems:detail", args=["b1"]) + "?plan=p").content.decode()
    assert "Mening rejam" in body and "1/3" in body
    assert 'href="/problems/c1/?plan=p"' in body and 'href="/problems/a1/?plan=p"' in body


@pytest.mark.django_db
def test_problem_page_ignores_bad_plan_param(client, staff, ali):
    a, other = _problem("a1", staff), _problem("z1", staff)
    _plan("p", [other], title="Boshqa reja")
    hidden = _plan("h", [a], title="Yopiq reja")
    hidden.is_public = False
    hidden.save()
    client.force_login(ali)
    for q in ("?plan=nope", "?plan=p", "?plan=h", "?plan=", "?plan=%00"):
        r = client.get(reverse("problems:detail", args=["a1"]) + q)
        assert r.status_code == 200
        assert "Boshqa reja" not in r.content.decode() and "Yopiq reja" not in r.content.decode()


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

def _plan_post(**over):
    data = {"slug": "yangi", "title": "Yangi reja", "summary": "", "description_md": "", "level": "beginner",
            "icon": "book-open", "order": "1", "is_public": "on",
            "sections-TOTAL_FORMS": "2", "sections-INITIAL_FORMS": "0", "sections-MIN_NUM_FORMS": "0",
            "sections-MAX_NUM_FORMS": "1000",
            "sections-0-title": "Sikllar", "sections-0-intro_md": "Kirish", "sections-0-order": "0",
            "sections-0-slugs": "b1\n# izoh\n\na1\n",
            "sections-1-title": "", "sections-1-intro_md": "", "sections-1-order": "0", "sections-1-slugs": ""}
    data.update(over)
    return data


@pytest.mark.django_db
def test_staff_creates_plan_with_sections(client, staff):
    _problem("a1", staff)
    _problem("b1", staff)
    client.force_login(staff)
    r = client.post(reverse("moderation:plan_new"), _plan_post())
    assert r.status_code == 302, r.content.decode()[:2000]
    plan = StudyPlan.objects.get(slug="yangi")
    section = plan.sections.get()
    assert list(section.items.values_list("problem__slug", flat=True)) == ["b1", "a1"]
    # editing keeps the section and rewrites its problems in the new order
    data = _plan_post(**{"sections-INITIAL_FORMS": "1", "sections-0-id": str(section.pk), "sections-0-plan": str(plan.pk),
                         "sections-0-slugs": "a1"})
    assert client.post(reverse("moderation:plan_edit", args=[plan.pk]), data).status_code == 302
    assert list(section.items.values_list("problem__slug", flat=True)) == ["a1"]
    assert client.get(reverse("moderation:plans")).status_code == 200
    client.post(reverse("moderation:plan_delete", args=[plan.pk]))
    assert not StudyPlan.objects.exists() and Problem.objects.count() == 2


@pytest.mark.django_db
def test_plan_form_rejects_bad_slugs(client, staff):
    _problem("a1", staff)
    _problem("p1", staff, status=Problem.Status.PENDING, is_public=False)
    client.force_login(staff)
    for slugs, words in (("a1\nnope", "nope"), ("a1\np1", "p1"), ("a1\na1", "a1")):
        r = client.post(reverse("moderation:plan_new"), _plan_post(**{"sections-0-slugs": slugs}))
        assert r.status_code == 200 and words in r.content.decode()
    r = client.post(reverse("moderation:plan_new"), _plan_post(**{"sections-1-title": "Yana", "sections-1-slugs": "a1",
                                                                  "sections-1-order": "1", "sections-0-slugs": "a1"}))
    assert r.status_code == 200 and "bir necha bo‘limda" in r.content.decode()
    assert not StudyPlan.objects.exists()


@pytest.mark.django_db
def test_plan_pages_require_staff(client, ali):
    client.force_login(ali)
    for url in (reverse("moderation:plans"), reverse("moderation:plan_new")):
        assert client.get(url).status_code == 302


@pytest.mark.django_db
def test_staff_edits_topic_theory(client, staff):
    from apps.problems.models import Tag

    tag = Tag.objects.create(name="stack")
    client.force_login(staff)
    r = client.post(reverse("moderation:tag_edit", args=[tag.pk]),
                    {"name": "stack", "kind": "code", "about_md": "LIFO"})
    assert r.status_code == 302
    tag.refresh_from_db()
    assert tag.about_md == "LIFO"


# ---- quest badges and starter content ---------------------------------------

@pytest.mark.django_db
def test_profile_shows_completed_plan_badge(client, staff, ali):
    a = _problem("a1", staff)
    _plan("p", [a], title="Birinchi qadam", in_quest=True)
    _plan("q", [_problem("b1", staff)], title="Tugamagan reja")
    url = reverse("profile", args=[ali.username])
    assert "Birinchi qadam" not in client.get(url).content.decode()
    _solve(ali, a)
    body = client.get(url).content.decode()
    assert "Birinchi qadam" in body and "Tugamagan reja" not in body


@pytest.mark.django_db
def test_add_study_plans_is_idempotent_and_skips_missing(staff):
    from io import StringIO

    from django.core.management import call_command

    from apps.learn.management.commands.add_study_plans import PLANS
    from apps.problems.models import Tag

    first_slug = PLANS[0]["sections"][0]["slugs"][0]
    _problem(first_slug, staff)
    Tag.objects.update_or_create(name="loops", defaults={"about_md": "o‘zim yozdim"})
    out = StringIO()
    call_command("add_study_plans", stdout=out)
    call_command("add_study_plans", stdout=out)
    assert StudyPlan.objects.count() == len(PLANS)
    assert PlanItem.objects.count() == 1 and "topilmadi" in out.getvalue()
    assert Tag.objects.get(name="loops").about_md == "o‘zim yozdim"  # staff text is never overwritten
    assert Tag.objects.exclude(about_md="").count() > 5
    # sections without problems yet are kept, so the course shows its whole outline
    assert PlanSection.objects.count() == sum(len(p["sections"]) for p in PLANS)
    # topics that don't exist on the portal yet are created with theory and the right kind
    assert Tag.objects.get(name="heap").kind == Tag.Kind.CODE and Tag.objects.get(name="heap").about_md
    assert Tag.objects.get(name="window-functions").kind == Tag.Kind.SQL


@pytest.mark.django_db
def test_staff_plan_list_follows_plan_order(client, staff):
    a = _problem("a1", staff)
    _plan("aa-reja", [a], title="Alfa reja", order=2)
    _plan("zz-reja", [a, _problem("b1", staff)], title="Zeta reja", order=1)
    client.force_login(staff)
    body = client.get(reverse("moderation:plans")).content.decode()
    assert body.index("Zeta reja") < body.index("Alfa reja")


# ---- Kurslar / Qo‘llanma restructure -----------------------------------------------------------

@pytest.mark.django_db
def test_plan_sections_counts_each_section_and_finds_the_next_unsolved(staff, ali):
    from apps.learn.progress import plan_sections

    a, b, c = (_problem(s, staff) for s in "abc")
    plan = _plan("p", [a, b])
    second = PlanSection.objects.create(plan=plan, title="Ikkinchi", order=1)
    PlanItem.objects.create(section=second, problem=c)
    PlanSection.objects.create(plan=plan, title="Tez orada", order=2)  # nothing open yet: listed, never complete
    _solve(ali, a)
    assert plan_sections(ali, [plan])[plan.pk] == {
        "sections": [{"done": 1, "total": 2, "complete": False}, {"done": 0, "total": 1, "complete": False},
                     {"done": 0, "total": 0, "complete": False}],
        "next_id": b.pk}


@pytest.mark.django_db
def test_hub_shows_each_course_once_and_continues_with_the_next_problem(client, staff, ali):
    a, b = _problem("a", staff), _problem("b", staff)
    _plan("birinchi", [a, b], title="Birinchi qadam", in_quest=True)
    _plan("sql", [_problem("s", staff)], title="SQL asoslari")
    _solve(ali, a)
    client.force_login(ali)
    body = client.get(reverse("learn:hub")).content.decode()
    # the path course used to be listed again under "O‘quv rejalar"
    assert body.count('href="/learn/plans/birinchi/"') == 2  # its card + the "continue" title, nothing more
    assert "Qo‘shimcha kurslar" in body and "SQL asoslari" in body
    assert f'href="{reverse("problems:detail", args=["b"])}?plan=birinchi"' in body


@pytest.mark.django_db
def test_guide_lists_only_topics_with_theory(client, staff):
    from apps.problems.models import Tag

    with_theory = Tag.objects.create(name="sikllar", about_md="# Sikl\n\nTakrorlash uchun **for** ishlatiladi.")
    bare = Tag.objects.create(name="yalang")
    p = _problem("a", staff)
    p.tags.add(with_theory, bare)
    body = client.get(reverse("learn:topics")).content.decode()
    assert "sikllar" in body and "Takrorlash uchun for ishlatiladi." in body
    assert "yalang" not in body


@pytest.mark.django_db
def test_course_section_links_to_its_topic_theory(client, staff):
    from apps.problems.models import Tag

    tag = Tag.objects.create(name="sikllar", about_md="Nazariya")
    a = _problem("a", staff)
    a.tags.add(tag, Tag.objects.create(name="matn"))  # no theory: not a candidate
    plan = _plan("p", [a])
    body = client.get(reverse("learn:plan", args=[plan.slug])).content.decode()
    assert f'href="{reverse("learn:topic", args=["sikllar"])}"' in body and "Nazariya: sikllar" in body


@pytest.mark.django_db
def test_saved_lists_sit_under_masalalar(client, ali):
    client.force_login(ali)
    assert reverse("learn:lists") in client.get(reverse("problems:list")).content.decode()
    body = client.get(reverse("learn:lists")).content.decode()
    assert f'href="{reverse("problems:list")}" class="ca-sidebar-link is-active"' in body


@pytest.mark.django_db
def test_section_theory_prefers_the_topic_its_intro_links_to(client, staff):
    from apps.problems.models import Tag

    io, math = (Tag.objects.update_or_create(name=n, defaults={"about_md": "x"})[0] for n in ("input-output", "math"))
    a = _problem("a", staff)
    a.tags.add(io, math)
    plan = _plan("p", [a])
    plan.sections.update(intro_md="Nazariya: [input-output](/learn/topics/input-output/).")
    assert "Nazariya: input-output" in client.get(reverse("learn:plan", args=[plan.slug])).content.decode()


@pytest.mark.django_db
def test_topic_and_course_show_theory_before_any_problem_exists(client, staff):
    from apps.problems.models import Tag

    Tag.objects.create(name="heap", about_md="Uyum eng kichik elementni tez beradi.")
    Tag.objects.create(name="no-theory")
    guide = client.get(reverse("learn:topics")).content.decode()
    assert "heap" in guide and "Masalalar tez orada" in guide and "no-theory" not in guide
    r = client.get(reverse("learn:topic", args=["heap"]))
    assert r.status_code == 200 and "tez orada" in r.content.decode()
    assert client.get(reverse("learn:topic", args=["no-theory"])).status_code == 404

    plan = StudyPlan.objects.create(slug="ds", title="Tuzilmalar", is_public=True, in_quest=True)
    PlanSection.objects.create(plan=plan, title="Uyum", intro_md="Nazariya: [heap](/learn/topics/heap/).")
    body = client.get(reverse("learn:plan", args=["ds"])).content.decode()
    assert "Uyum" in body and "Masalalar tez orada" in body and "Nazariya: heap" in body
    assert "Masalalar tez orada" in client.get(reverse("learn:hub")).content.decode()
    assert "Tuzilmalar" in client.get(reverse("learn:topic", args=["heap"])).content.decode()  # linked course
