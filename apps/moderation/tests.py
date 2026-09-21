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
            "rating": "1500", "practice_points": "0", "school": "", "location": "", "is_active": "on"}
    assert client.post(reverse("moderation:user_edit", args=[student.pk]), {**base, "is_staff": "on"}).status_code == 302
    student.refresh_from_db()
    assert student.is_staff is True and student.rating == 1500

    r = client.post(reverse("moderation:user_edit", args=[staff.pk]), {**base, "username": "teacher"})
    assert r.status_code == 200
    staff.refresh_from_db()
    assert staff.is_staff is True


@pytest.mark.django_db
def test_contest_publish_opens_problems_and_grants_points(client):
    from django.utils import timezone

    from apps.contests.models import Contest, ContestProblem
    from apps.problems.models import Language
    from apps.submissions.models import Submission

    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    ali = User.objects.create_user("ali", password="x")
    p = Problem.objects.create(slug="p", title="P", statement_md="x", author=staff, is_public=False, points=70)
    c = Contest.objects.create(title="C", start=timezone.now() - timezone.timedelta(hours=3),
                               end=timezone.now() - timezone.timedelta(hours=1))
    ContestProblem.objects.create(contest=c, problem=p, label="A")
    lang = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    for v in ("WA", "AC", "AC"):
        Submission.objects.create(user=ali, problem=p, contest=c, language=lang, source="x", verdict=v)

    client.force_login(staff)
    assert client.post(reverse("moderation:contest_publish", args=[c.pk])).status_code == 302
    p.refresh_from_db(); ali.refresh_from_db()
    assert p.is_public is True
    assert ali.practice_points == 70  # once, not per AC
    client.post(reverse("moderation:contest_publish", args=[c.pk]))
    ali.refresh_from_db()
    assert ali.practice_points == 70


@pytest.mark.django_db
def test_contest_form_rejects_already_ended_on_create(client):
    client.force_login(User.objects.create_user("teacher", password="x", is_staff=True))
    data = {"title": "Old", "start": "2020-01-01T10:00", "end": "2020-01-01T12:00",
            "cp-TOTAL_FORMS": "0", "cp-INITIAL_FORMS": "0", "cp-MIN_NUM_FORMS": "0", "cp-MAX_NUM_FORMS": "1000"}
    r = client.post(reverse("moderation:contest_new"), data)
    assert r.status_code == 200 and "tib ketgan" in r.content.decode()
