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
def test_student_submission_is_pending_and_hidden(client):
    user = User.objects.create_user("ali", password="x")
    client.force_login(user)
    data = {"title": "Sum of two", "statement_md": "a+b ni top", "difficulty": "easy",
            "tl_ms": "1000", "ml_mb": "256", "points": "100"}
    data.update(_formset_data())
    data["testcases-0-input"] = "1 2\n"
    data["testcases-0-expected"] = "3\n"

    r = client.post(reverse("moderation:submit"), data)
    problem = Problem.objects.get(title="Sum of two")
    assert r.status_code == 302
    assert problem.status == Problem.Status.PENDING
    assert problem.is_public is False
    assert problem.author == user
    assert problem.testcases.count() == 1

    from django.test import Client
    assert Client().get(reverse("problems:detail", args=[problem.slug])).status_code == 404


@pytest.mark.django_db
def test_staff_submission_is_approved_and_public(client):
    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    client.force_login(staff)
    data = {"title": "Staff Problem", "statement_md": "x", "difficulty": "easy",
            "tl_ms": "1000", "ml_mb": "256", "points": "100"}
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
    user = User.objects.create_user("ali", password="x")
    client.force_login(user)
    data = {"title": "No Cases", "statement_md": "x", "difficulty": "easy",
            "tl_ms": "1000", "ml_mb": "256", "points": "100"}
    data.update(_formset_data())

    r = client.post(reverse("moderation:submit"), data)
    assert r.status_code == 200
    assert not Problem.objects.filter(title="No Cases").exists()
    assert b"Kamida bitta test case kerak" in r.content


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
