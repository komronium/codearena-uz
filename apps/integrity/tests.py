import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.contests.models import Contest, Participation

from .models import FocusEvent


@pytest.fixture
def contest(db):
    return Contest.objects.create(title="Sprint", start=timezone.now() - timezone.timedelta(minutes=5),
                                  end=timezone.now() + timezone.timedelta(minutes=55))


@pytest.fixture
def user(db):
    return User.objects.create_user("ali", password="x")


def test_event_requires_login(client, contest):
    r = client.post(reverse("integrity:event"), {"contest_id": contest.pk, "kind": "blur"})
    assert r.status_code == 302


def test_event_rejects_non_participant(client, contest, user):
    client.force_login(user)
    r = client.post(reverse("integrity:event"), {"contest_id": contest.pk, "kind": "blur"})
    assert r.status_code == 400
    assert FocusEvent.objects.count() == 0


def test_event_records_for_participant(client, contest, user):
    Participation.objects.create(user=user, contest=contest)
    client.force_login(user)
    r = client.post(reverse("integrity:event"), {"contest_id": contest.pk, "kind": "paste"})
    assert r.status_code == 200
    assert FocusEvent.objects.filter(user=user, contest=contest, kind="paste").exists()


def test_event_rejects_bad_kind(client, contest, user):
    Participation.objects.create(user=user, contest=contest)
    client.force_login(user)
    r = client.post(reverse("integrity:event"), {"contest_id": contest.pk, "kind": "not-a-kind"})
    assert r.status_code == 400


def test_contest_report_requires_staff(client, contest, user):
    client.force_login(user)
    r = client.get(reverse("integrity:contest_report", args=[contest.pk]))
    assert r.status_code in (302, 403)


def test_contest_report_renders_for_staff(client, contest, user):
    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    Participation.objects.create(user=user, contest=contest)
    FocusEvent.objects.create(user=user, contest=contest, kind="blur")
    client.force_login(staff)
    r = client.get(reverse("integrity:contest_report", args=[contest.pk]))
    assert r.status_code == 200
    assert b"ali" in r.content
