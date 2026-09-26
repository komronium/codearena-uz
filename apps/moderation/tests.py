import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.problems.models import Problem


def _formset_data(prefix="testcases", n=3):
    # order stays at the model default (0) for every row: matching an unbound
    # extra form's initial is what makes Django's formset treat an untouched
    # blank row as unchanged and skip full_clean on it.
    data = {f"{prefix}-TOTAL_FORMS": str(n), f"{prefix}-INITIAL_FORMS": "0",
            f"{prefix}-MIN_NUM_FORMS": "0", f"{prefix}-MAX_NUM_FORMS": "1000"}
    for i in range(n):
        data[f"{prefix}-{i}-input"] = ""
        data[f"{prefix}-{i}-expected"] = ""
        data[f"{prefix}-{i}-order"] = "0"
    return data


@pytest.mark.django_db
def test_submit_requires_login(client):
    r = client.get(reverse("moderation:submit"))
    assert r.status_code == 302


@pytest.mark.django_db
def test_student_cannot_submit_problems(client):
    client.force_login(User.objects.create_user("ali", password="x"))
    assert client.get(reverse("moderation:submit")).status_code == 302
    assert Problem.objects.count() == 0


@pytest.mark.django_db
def test_staff_submission_is_approved_and_public(client):
    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    client.force_login(staff)
    data = {"title": "Staff Problem", "statement_md": "x", "difficulty": "easy", "kind": "code",
            "tl_ms": "1000", "ml_mb": "256", "points": "100", "is_public": "on"}
    data.update(_formset_data())
    data["testcases-0-input"] = "1\n"
    data["testcases-0-expected"] = "1\n"

    r = client.post(reverse("moderation:submit"), data)
    problem = Problem.objects.get(title="Staff Problem")
    assert r.status_code == 302
    assert problem.status == Problem.Status.APPROVED
    assert problem.is_public is True


@pytest.mark.django_db
def test_submit_rejects_no_testcases(client):
    user = User.objects.create_user("ali", password="x", is_staff=True)
    client.force_login(user)
    data = {"title": "No Cases", "statement_md": "x", "difficulty": "easy", "kind": "code",
            "tl_ms": "1000", "ml_mb": "256", "points": "100"}
    data.update(_formset_data())

    r = client.post(reverse("moderation:submit"), data)
    assert r.status_code == 200
    assert not Problem.objects.filter(title="No Cases").exists()
    assert "Kamida bitta test kerak" in r.content.decode()


@pytest.mark.django_db
def test_author_can_preview_own_pending_problem(client):
    user = User.objects.create_user("ali", password="x")
    problem = Problem.objects.create(slug="p", title="P", statement_md="x", author=user,
                                     status=Problem.Status.PENDING, is_public=False)
    client.force_login(user)
    assert client.get(reverse("problems:detail", args=[problem.slug])).status_code == 200


@pytest.mark.django_db
def test_queue_requires_staff(client):
    user = User.objects.create_user("ali", password="x")
    client.force_login(user)
    assert client.get(reverse("moderation:queue")).status_code == 302


@pytest.mark.django_db
def test_staff_can_approve_pending_problem(client):
    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    author = User.objects.create_user("ali", password="x")
    problem = Problem.objects.create(slug="p", title="P", statement_md="x", author=author,
                                     status=Problem.Status.PENDING, is_public=False)
    client.force_login(staff)
    r = client.post(reverse("moderation:approve", args=[problem.pk]))
    assert r.status_code == 302
    problem.refresh_from_db()
    assert problem.status == Problem.Status.APPROVED
    assert problem.is_public is True


@pytest.mark.django_db
def test_staff_can_reject_pending_problem(client):
    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    author = User.objects.create_user("ali", password="x")
    problem = Problem.objects.create(slug="p", title="P", statement_md="x", author=author,
                                     status=Problem.Status.PENDING, is_public=False)
    client.force_login(staff)
    r = client.post(reverse("moderation:reject", args=[problem.pk]))
    assert r.status_code == 302
    problem.refresh_from_db()
    assert problem.status == Problem.Status.REJECTED
    assert problem.is_public is False


@pytest.mark.django_db
def test_queue_only_lists_pending(client):
    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    author = User.objects.create_user("ali", password="x")
    Problem.objects.create(slug="approved", title="Approved One", statement_md="x", author=author,
                           status=Problem.Status.APPROVED, is_public=True)
    Problem.objects.create(slug="pending", title="Pending One", statement_md="x", author=author,
                           status=Problem.Status.PENDING, is_public=False)
    client.force_login(staff)
    r = client.get(reverse("moderation:queue"))
    assert b"Pending One" in r.content
    assert b"Approved One" not in r.content


@pytest.mark.django_db
def test_staff_can_bulk_upload_tests_as_zip(client):
    import io
    import zipfile

    from django.core.files.uploadedfile import SimpleUploadedFile

    client.force_login(User.objects.create_user("teacher", password="x", is_staff=True))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("tests/10.in", "10\n")
        z.writestr("tests/10.out", "20\n")
        z.writestr("tests/2.in", "2\n")
        z.writestr("tests/2.ans", "4\n")
        z.writestr("tests/readme.md", "ignored")
    data = {"title": "Zipped", "statement_md": "x", "difficulty": "easy", "kind": "code",
            "tl_ms": "1000", "ml_mb": "256", "points": "100",
            "tests_zip": SimpleUploadedFile("t.zip", buf.getvalue(), content_type="application/zip")}
    data.update(_formset_data())

    r = client.post(reverse("moderation:submit"), data)
    assert r.status_code == 302
    tests = list(Problem.objects.get(title="Zipped").testcases.order_by("order").values_list("input", "expected"))
    assert tests == [("2\n", "4\n"), ("10\n", "20\n")]  # natural order: 2 before 10


@pytest.mark.django_db
def test_admin_urls_are_gone(client):
    assert client.get("/admin/").status_code == 404


@pytest.mark.django_db
def test_staff_pages_require_staff(client):
    client.force_login(User.objects.create_user("ali", password="x"))
    for name in ["dashboard", "problems", "contests", "users", "groups", "tags"]:
        assert client.get(reverse(f"moderation:{name}")).status_code == 302, name


@pytest.mark.django_db
def test_staff_can_edit_problem_and_toggle_visibility(client):
    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    problem = Problem.objects.create(slug="p", title="Old", statement_md="x", author=staff)
    problem.testcases.create(input="1\n", expected="1\n")
    client.force_login(staff)

    data = {"title": "New title", "statement_md": "x", "difficulty": "easy", "kind": "code",
            "tl_ms": "1000", "ml_mb": "256", "points": "100", "is_public": "on"}
    data.update(_formset_data(n=1))
    data["testcases-0-input"] = "2\n"
    data["testcases-0-expected"] = "2\n"
    assert client.post(reverse("moderation:problem_edit", args=[problem.pk]), data).status_code == 302
    problem.refresh_from_db()
    assert problem.title == "New title" and problem.slug == "p"
    assert problem.testcases.count() == 2

    client.post(reverse("moderation:problem_toggle", args=[problem.pk]))
    problem.refresh_from_db()
    assert problem.is_public is False


@pytest.mark.django_db
def test_staff_can_create_contest_with_problems(client):
    from apps.contests.models import Contest

    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    p = Problem.objects.create(slug="p", title="P", statement_md="x", author=staff, is_public=False)
    client.force_login(staff)
    data = {"title": "Round 1", "description_md": "", "start": "2030-01-01T10:00", "end": "2030-01-01T12:00",
            "is_rated": "on", "allowed_ip_prefix": "", "require_group": "",
            "cp-TOTAL_FORMS": "1", "cp-INITIAL_FORMS": "0", "cp-MIN_NUM_FORMS": "0", "cp-MAX_NUM_FORMS": "1000",
            "cp-0-label": "A", "cp-0-problem": str(p.pk), "cp-0-points": "100", "cp-0-order": "0"}
    assert client.post(reverse("moderation:contest_new"), data).status_code == 302
    contest = Contest.objects.get(title="Round 1")
    assert list(contest.contest_problems.values_list("label", "problem_id")) == [("A", p.pk)]


@pytest.mark.django_db
def test_contest_end_must_follow_start(client):
    client.force_login(User.objects.create_user("teacher", password="x", is_staff=True))
    data = {"title": "Bad", "start": "2030-01-01T12:00", "end": "2030-01-01T10:00",
            "cp-TOTAL_FORMS": "0", "cp-INITIAL_FORMS": "0", "cp-MIN_NUM_FORMS": "0", "cp-MAX_NUM_FORMS": "1000"}
    r = client.post(reverse("moderation:contest_new"), data)
    assert r.status_code == 200
    assert "boshlanishdan keyin" in r.content.decode()


@pytest.mark.django_db
def test_staff_can_edit_user_but_not_demote_self(client):
    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    student = User.objects.create_user("ali", password="x")
    client.force_login(staff)
    base = {"username": "ali", "email": "", "first_name": "", "last_name": "", "role": "student",
            "rating": "1500", "practice_points": "999", "school": "", "location": "", "is_active": "on"}
    assert client.post(reverse("moderation:user_edit", args=[student.pk]), {**base, "is_staff": "on"}).status_code == 302
    student.refresh_from_db()
    assert student.is_staff is True and student.rating == 1500 and student.practice_points == 0

    r = client.post(reverse("moderation:user_edit", args=[staff.pk]), {**base, "username": "teacher"})
    assert r.status_code == 200
    staff.refresh_from_db()
    assert staff.is_staff is True


@pytest.mark.django_db
def test_contest_publish_opens_problems_and_grants_points(client):
    from django.utils import timezone

    from apps.contests.models import Contest, ContestProblem, Participation
    from apps.problems.models import Language
    from apps.submissions.models import Submission, UserProblemSolved

    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    ali = User.objects.create_user("ali", password="x")
    cheat = User.objects.create_user("cheat", password="x")
    p = Problem.objects.create(slug="p", title="P", statement_md="x", author=staff, is_public=False, points=70)
    c = Contest.objects.create(title="C", start=timezone.now() - timezone.timedelta(hours=3),
                               end=timezone.now() - timezone.timedelta(hours=1))
    ContestProblem.objects.create(contest=c, problem=p, label="A")
    Participation.objects.create(user=cheat, contest=c, disqualified=True)
    lang = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    for v in ("WA", "AC", "AC"):
        Submission.objects.create(user=ali, problem=p, contest=c, language=lang, source="x", verdict=v)
    Submission.objects.create(user=cheat, problem=p, contest=c, language=lang, source="x", verdict="AC")

    client.force_login(staff)
    assert client.post(reverse("moderation:contest_publish", args=[c.pk])).status_code == 302
    p.refresh_from_db(); ali.refresh_from_db(); cheat.refresh_from_db(); c.refresh_from_db()
    assert p.is_public is True and c.published_at is not None
    assert ali.practice_points == 70  # once, not per AC
    assert cheat.practice_points == 0 and not UserProblemSolved.objects.filter(user=cheat).exists()
    published_at = c.published_at
    client.post(reverse("moderation:contest_publish", args=[c.pk]))  # publishing again changes nothing
    ali.refresh_from_db(); c.refresh_from_db()
    assert ali.practice_points == 70 and c.published_at == published_at


@pytest.mark.django_db
def test_publish_button_shows_until_published(client):
    from django.utils import timezone

    from apps.contests.models import Contest, ContestProblem

    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    public = Problem.objects.create(slug="p", title="P", statement_md="x", author=staff, is_public=True)
    c = Contest.objects.create(title="C", start=timezone.now() - timezone.timedelta(hours=3),
                               end=timezone.now() - timezone.timedelta(hours=1))
    ContestProblem.objects.create(contest=c, problem=public, label="A")
    client.force_login(staff)
    publish_url = reverse("moderation:contest_publish", args=[c.pk]).encode()
    assert publish_url in client.get(reverse("moderation:contests")).content  # all problems public, still unpublished
    client.post(reverse("moderation:contest_publish", args=[c.pk]))
    assert publish_url not in client.get(reverse("moderation:contests")).content


@pytest.mark.django_db
def test_contest_form_rejects_already_ended_on_create(client):
    client.force_login(User.objects.create_user("teacher", password="x", is_staff=True))
    data = {"title": "Old", "start": "2020-01-01T10:00", "end": "2020-01-01T12:00",
            "cp-TOTAL_FORMS": "0", "cp-INITIAL_FORMS": "0", "cp-MIN_NUM_FORMS": "0", "cp-MAX_NUM_FORMS": "1000"}
    r = client.post(reverse("moderation:contest_new"), data)
    assert r.status_code == 200 and "tib ketgan" in r.content.decode()


# ---- AI problem generation ----------------------------------------------------

def _ai_problem(title="Ikki son yig'indisi", n_tests=20):
    return {
        "title": title, "statement_md": "A va B ni qo'shing.",
        "input_md": "Bitta qatorda A va B.", "output_md": "Yig'indi.",
        "difficulty": "easy", "tl_ms": 1000, "ml_mb": 256, "points": 100,
        "tags": ["arifmetika"],
        "testcases": [{"input": f"{i} {i}\n", "expected": f"{2*i}\n", "is_sample": i == 0}
                      for i in range(n_tests)],
    }


class _FakeStream:
    def __init__(self, response):
        self._response = response

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self._response


def _fake_client(payload: dict):
    response = SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(payload))])
    return SimpleNamespace(messages=SimpleNamespace(stream=lambda **kw: _FakeStream(response)))


def test_generate_problems_parses_structured_response():
    from apps.moderation.ai import generate_problems

    payload = {"problems": [_ai_problem("A"), _ai_problem("B")]}
    result = generate_problems("ikki masala", count=2, client=_fake_client(payload))
    assert [p["title"] for p in result] == ["A", "B"]


def test_generate_problems_wraps_bad_json():
    from apps.moderation.ai import AIGenerationError, generate_problems

    client = SimpleNamespace(messages=SimpleNamespace(
        stream=lambda **kw: _FakeStream(SimpleNamespace(content=[SimpleNamespace(type="text", text="not json")]))
    ))
    with pytest.raises(AIGenerationError):
        generate_problems("x", client=client)


def test_generate_problems_rejects_too_few_testcases():
    from apps.moderation.ai import AIGenerationError, generate_problems

    payload = {"problems": [_ai_problem("Kam testli", n_tests=5)]}
    with pytest.raises(AIGenerationError):
        generate_problems("x", count=1, client=_fake_client(payload))


def test_generate_problems_rejects_count_mismatch():
    from apps.moderation.ai import AIGenerationError, generate_problems

    payload = {"problems": [_ai_problem("A")]}
    with pytest.raises(AIGenerationError):
        generate_problems("x", count=2, client=_fake_client(payload))


@pytest.mark.django_db
def test_ai_generate_creates_pending_problems_for_review(client):
    from apps.problems.models import TestCase

    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    client.force_login(staff)

    drafts = [_ai_problem("Birinchi masala"), _ai_problem("Ikkinchi masala")]
    with patch("apps.moderation.views.generate_problems", return_value=drafts):
        r = client.post(reverse("moderation:ai_generate"),
                         {"prompt": "arifmetika", "model": "claude-sonnet-5", "count": "2"})
    assert r.status_code == 302 and r.url == reverse("moderation:queue")

    problems = Problem.objects.filter(title__in=["Birinchi masala", "Ikkinchi masala"])
    assert problems.count() == 2
    for p in problems:
        assert p.status == Problem.Status.PENDING
        assert p.is_public is False
        assert p.author == staff
        assert TestCase.objects.filter(problem=p).count() == 20

    # listed on the review queue, not on the public site
    q = client.get(reverse("moderation:queue")).content.decode()
    assert "Birinchi masala" in q and "Ikkinchi masala" in q


@pytest.mark.django_db
def test_ai_generate_requires_prompt(client):
    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    client.force_login(staff)
    r = client.post(reverse("moderation:ai_generate"), {"prompt": "", "model": "claude-sonnet-5", "count": "2"})
    assert r.status_code == 302 and r.url == reverse("moderation:ai_generate")
    assert Problem.objects.count() == 0


@pytest.mark.django_db
def test_staff_sees_every_users_submissions(client):
    from apps.problems.models import Language
    from apps.submissions.models import Submission
    boss = User.objects.create_user("boss", password="x", is_staff=True)
    ali = User.objects.create_user("ali", password="x")
    lang = Language.objects.create(code="python", name="Python 3", docker_image="i", run_cmd="r")
    p = Problem.objects.create(slug="p1", title="P1", statement_md="x", author=boss)
    s = Submission.objects.create(user=ali, problem=p, language=lang, source="print('ali')", verdict="WA")
    client.force_login(boss)
    r = client.get(reverse("moderation:submissions") + "?user=ali&verdict=WA")
    assert r.status_code == 200 and f"#{s.pk:06d}".encode() in r.content
    assert f"#{s.pk:06d}".encode() not in client.get(reverse("moderation:submissions") + "?user=nobody").content
    client.force_login(ali)
    assert client.get(reverse("moderation:submissions")).status_code in (302, 403)
    client.force_login(boss)
    assert b"print(&#x27;ali&#x27;)" in client.get(reverse("submissions:detail", args=[s.pk])).content


def _contest_data(problem, rated=True):
    """POST body for moderation:contest_new with one problem row."""
    data = {"title": "Round", "description_md": "", "start": "2030-01-01T10:00", "end": "2030-01-01T12:00",
            "allowed_ip_prefix": "", "require_group": "",
            "cp-TOTAL_FORMS": "1", "cp-INITIAL_FORMS": "0", "cp-MIN_NUM_FORMS": "0", "cp-MAX_NUM_FORMS": "1000",
            "cp-0-label": "A", "cp-0-problem": str(problem.pk), "cp-0-points": "100", "cp-0-order": "0"}
    if rated:
        data["is_rated"] = "on"
    return data


def _contest_edit_data(contest):
    """POST body that saves `contest` and its problem rows unchanged."""
    from django.utils import timezone

    fmt = "%Y-%m-%dT%H:%M"
    rows = list(contest.contest_problems.all())
    data = {"title": contest.title, "description_md": "", "allowed_ip_prefix": "", "require_group": "",
            "start": timezone.localtime(contest.start).strftime(fmt),
            "end": timezone.localtime(contest.end).strftime(fmt),
            "cp-TOTAL_FORMS": str(len(rows)), "cp-INITIAL_FORMS": str(len(rows)),
            "cp-MIN_NUM_FORMS": "0", "cp-MAX_NUM_FORMS": "1000"}
    if contest.is_rated:
        data["is_rated"] = "on"
    for i, cp in enumerate(rows):
        data |= {f"cp-{i}-id": str(cp.pk), f"cp-{i}-label": cp.label, f"cp-{i}-problem": str(cp.problem_id),
                 f"cp-{i}-points": str(cp.points), f"cp-{i}-order": str(cp.order)}
    return data


@pytest.mark.django_db
def test_rated_contest_takes_only_fresh_problems(client):
    from django.utils import timezone

    from apps.contests.models import Contest, ContestProblem

    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    client.force_login(staff)
    public = Problem.objects.create(slug="pub", title="Pub", statement_md="x", author=staff, is_public=True)
    r = client.post(reverse("moderation:contest_new"), _contest_data(public))
    assert r.status_code == 200 and "Ochiq masala" in r.content.decode()

    used = Problem.objects.create(slug="used", title="Used", statement_md="x", author=staff, is_public=False)
    old = Contest.objects.create(title="Old", start=timezone.now() + timezone.timedelta(days=1),
                                 end=timezone.now() + timezone.timedelta(days=2))
    ContestProblem.objects.create(contest=old, problem=used, label="A")
    r = client.post(reverse("moderation:contest_new"), _contest_data(used))
    assert r.status_code == 200 and "Bu masala boshqa musobaqada ishlatilgan" in r.content.decode()
    assert not Contest.objects.filter(title="Round").exists()


@pytest.mark.django_db
def test_unrated_contest_saves_reused_problem_with_warning(client):
    from apps.contests.models import Contest

    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    client.force_login(staff)
    public = Problem.objects.create(slug="pub", title="Pub", statement_md="x", author=staff, is_public=True)
    r = client.post(reverse("moderation:contest_new"), _contest_data(public, rated=False), follow=True)
    html = r.content.decode()
    assert Contest.objects.filter(title="Round").exists()
    assert 'class="ca-alert ca-alert-warn"' in html and "A: ochiq yoki boshqa musobaqada ishlatilgan" in html


@pytest.mark.django_db
def test_contest_edit_is_not_blocked_by_its_own_or_ended_problems(client):
    from django.utils import timezone

    from apps.contests.models import Contest, ContestProblem

    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    client.force_login(staff)
    now = timezone.now()
    running = Contest.objects.create(title="Live", is_rated=True, start=now - timezone.timedelta(hours=1),
                                     end=now + timezone.timedelta(hours=1))
    ContestProblem.objects.create(contest=running, label="A", problem=Problem.objects.create(
        slug="fresh", title="Fresh", statement_md="x", author=staff, is_public=False))
    ended = Contest.objects.create(title="Past", is_rated=True, start=now - timezone.timedelta(hours=3),
                                   end=now - timezone.timedelta(hours=2))
    ContestProblem.objects.create(contest=ended, label="A", problem=Problem.objects.create(
        slug="opened", title="Opened", statement_md="x", author=staff, is_public=True))
    for c in (running, ended):
        r = client.post(reverse("moderation:contest_edit", args=[c.pk]), _contest_edit_data(c))
        assert r.status_code == 302, r.content.decode()[:2000]


@pytest.mark.django_db
def test_problem_delete_refuses_when_others_depend_on_it(client):
    from django.utils import timezone

    from apps.contests.models import Contest, ContestProblem
    from apps.problems.models import Language
    from apps.submissions.models import Submission, UserProblemSolved

    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    ali = User.objects.create_user("ali", password="x")
    lang = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    in_contest = Problem.objects.create(slug="c", title="C", statement_md="x", author=staff)
    c = Contest.objects.create(title="R", start=timezone.now() + timezone.timedelta(days=1),
                               end=timezone.now() + timezone.timedelta(days=2))
    ContestProblem.objects.create(contest=c, problem=in_contest, label="A")
    tried = Problem.objects.create(slug="t", title="T", statement_md="x", author=staff)
    Submission.objects.create(user=ali, problem=tried, language=lang, source="x", verdict="WA")
    own = Problem.objects.create(slug="m", title="M", statement_md="x", author=staff)
    own_ac = Submission.objects.create(user=staff, problem=own, language=lang, source="x", verdict="AC")
    UserProblemSolved.objects.create(user=staff, problem=own, first_ac_submission=own_ac)

    client.force_login(staff)
    for p in (in_contest, tried):
        r = client.post(reverse("moderation:problem_delete", args=[p.pk]), follow=True)
        assert 'class="ca-alert ca-alert-bad"' in r.content.decode()
    assert Problem.objects.filter(pk__in=[in_contest.pk, tried.pk]).count() == 2
    client.post(reverse("moderation:problem_delete", args=[own.pk]))  # only the author's solve: no ProtectedError
    assert not Problem.objects.filter(pk=own.pk).exists()


@pytest.mark.django_db
def test_contest_delete_refuses_when_it_has_submissions(client):
    from django.utils import timezone

    from apps.contests.models import Contest
    from apps.problems.models import Language
    from apps.submissions.models import Submission

    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    p = Problem.objects.create(slug="p", title="P", statement_md="x", author=staff)
    lang = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    times = {"start": timezone.now() - timezone.timedelta(hours=3), "end": timezone.now() - timezone.timedelta(hours=2)}
    used = Contest.objects.create(title="Used", **times)
    Submission.objects.create(user=staff, problem=p, contest=used, language=lang, source="x", verdict="AC")
    empty = Contest.objects.create(title="Empty", **times)
    client.force_login(staff)
    client.post(reverse("moderation:contest_delete", args=[used.pk]))
    client.post(reverse("moderation:contest_delete", args=[empty.pk]))
    assert list(Contest.objects.values_list("title", flat=True)) == ["Used"]


@pytest.mark.django_db
def test_rejudge_requeues_finished_submissions_once(client, django_capture_on_commit_callbacks):
    from apps.problems.models import Language
    from apps.submissions.models import Submission, TestResult

    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    ali = User.objects.create_user("ali", password="x")
    p = Problem.objects.create(slug="p", title="P", statement_md="x", author=staff)
    tc = p.testcases.create(input="1\n", expected="1\n")
    lang = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    ac, wa, running = [Submission.objects.create(user=ali, problem=p, language=lang, source="x", verdict=v,
                                                 passed=1, total=1) for v in ("AC", "WA", "RUNNING")]
    TestResult.objects.create(submission=ac, testcase=tc, verdict="AC")
    client.force_login(staff)
    assert "2 ta urinish qayta tekshiriladi" in client.get(reverse("moderation:problems")).content.decode()

    with patch("apps.moderation.views.django_rq.get_queue") as get_queue:
        for _ in range(2):  # a double click: the second finds nothing left to reset
            with django_capture_on_commit_callbacks(execute=True):
                assert client.post(reverse("moderation:problem_rejudge", args=[p.pk])).status_code == 302
    get_queue.assert_called_with("rejudge")
    assert [c.args[1] for c in get_queue.return_value.enqueue.call_args_list] == [ac.pk, wa.pk]
    ac.refresh_from_db()
    running.refresh_from_db()
    assert (ac.verdict, ac.passed, ac.total) == ("PENDING", 0, 0) and not ac.results.exists()
    assert running.verdict == "RUNNING"  # in flight: left alone


@pytest.mark.django_db
def test_rejudge_warns_about_applied_rating_and_needs_staff(client):
    from django.utils import timezone

    from apps.contests.models import Contest, ContestProblem
    from apps.problems.models import Language
    from apps.submissions.models import Submission

    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    ali = User.objects.create_user("ali", password="x")
    p = Problem.objects.create(slug="p", title="P", statement_md="x", author=staff)
    c = Contest.objects.create(title="Final", is_rated=True, rating_applied=True,
                               start=timezone.now() - timezone.timedelta(hours=3),
                               end=timezone.now() - timezone.timedelta(hours=2))
    ContestProblem.objects.create(contest=c, problem=p, label="A")
    lang = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    s = Submission.objects.create(user=ali, problem=p, contest=c, language=lang, source="x", verdict="AC")

    client.force_login(ali)
    assert client.post(reverse("moderation:problem_rejudge", args=[p.pk])).status_code == 302
    s.refresh_from_db()
    assert s.verdict == "AC"  # not staff: nothing happened

    client.force_login(staff)
    with patch("apps.moderation.views.django_rq.get_queue"):
        r = client.post(reverse("moderation:problem_rejudge", args=[p.pk]), follow=True)
    assert "Final: reyting allaqachon hisoblangan" in r.content.decode()
