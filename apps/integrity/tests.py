from io import StringIO

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.contests.models import Contest, ContestProblem, Participation
from apps.problems.models import Language, Problem
from apps.submissions.models import Submission

from .models import FocusEvent, SimilarityFlag
from .similarity import similarity


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


def test_similarity_identical_source_is_1():
    assert similarity("a=1\nprint(a)", "a=1\nprint(a)") == 1.0


def test_similarity_ignores_whitespace_reformatting():
    assert similarity("a = 1\nprint( a )", "a=1\nprint(a)") == 1.0


def test_similarity_unrelated_code_is_low():
    assert similarity("a,b=map(int,input().split());print(a+b)", "print('hello world')") < 0.5


@pytest.fixture
def flag_python(db):
    return Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")


@pytest.fixture
def flag_problem(db):
    author = User.objects.create_user("teacher2", password="x")
    return Problem.objects.create(slug="a", title="A", statement_md="x", author=author, is_public=False)


@pytest.fixture
def flag_contest(db, flag_problem):
    c = Contest.objects.create(title="Sprint", start=timezone.now() - timezone.timedelta(hours=1),
                               end=timezone.now() + timezone.timedelta(hours=1))
    ContestProblem.objects.create(contest=c, problem=flag_problem, label="A")
    return c


def test_flag_similarity_flags_near_identical_ac_submissions(flag_contest, flag_problem, flag_python):
    ali = User.objects.create_user("ali2", password="x")
    bob = User.objects.create_user("bob2", password="x")
    source = "a,b=map(int,input().split())\nprint(a+b)"
    Submission.objects.create(user=ali, problem=flag_problem, contest=flag_contest, language=flag_python,
                              source=source, verdict="AC")
    Submission.objects.create(user=bob, problem=flag_problem, contest=flag_contest, language=flag_python,
                              source=source, verdict="AC")

    call_command("flag_similarity", flag_contest.pk, stdout=StringIO())

    assert SimilarityFlag.objects.count() == 1
    flag = SimilarityFlag.objects.get()
    assert flag.score == 1.0

    # idempotent: running again does not duplicate the flag
    call_command("flag_similarity", flag_contest.pk, stdout=StringIO())
    assert SimilarityFlag.objects.count() == 1


def test_flag_similarity_without_id_processes_all_ended_contests(flag_problem, flag_python):
    """Cron-friendly mode: no contest_id -> every ended contest."""
    ended = Contest.objects.create(title="Ended", start=timezone.now() - timezone.timedelta(hours=2),
                                   end=timezone.now() - timezone.timedelta(hours=1))
    ContestProblem.objects.create(contest=ended, problem=flag_problem, label="A")
    ali = User.objects.create_user("ali4", password="x")
    bob = User.objects.create_user("bob4", password="x")
    source = "a,b=map(int,input().split())\nprint(a+b)"
    Submission.objects.create(user=ali, problem=flag_problem, contest=ended, language=flag_python,
                              source=source, verdict="AC")
    Submission.objects.create(user=bob, problem=flag_problem, contest=ended, language=flag_python,
                              source=source, verdict="AC")

    call_command("flag_similarity", stdout=StringIO())

    assert SimilarityFlag.objects.filter(submission_a__contest=ended).count() == 1


def test_flag_similarity_skips_same_user_and_dissimilar(flag_contest, flag_problem, flag_python):
    ali = User.objects.create_user("ali3", password="x")
    Submission.objects.create(user=ali, problem=flag_problem, contest=flag_contest, language=flag_python,
                              source="a=1", verdict="AC")
    Submission.objects.create(user=ali, problem=flag_problem, contest=flag_contest, language=flag_python,
                              source="a=1", verdict="AC")

    call_command("flag_similarity", flag_contest.pk, stdout=StringIO())

    assert SimilarityFlag.objects.count() == 0


def test_report_ranks_by_risk_and_flag_review_toggles(client, contest, user):
    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    other = User.objects.create_user("vali", password="x")
    for u in (user, other):
        Participation.objects.create(user=u, contest=contest)
    FocusEvent.objects.create(user=user, contest=contest, kind="blur")
    for _ in range(2):
        FocusEvent.objects.create(user=other, contest=contest, kind="paste")
    problem = Problem.objects.create(slug="p", title="P", statement_md="x", author=staff)
    lang = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    a = Submission.objects.create(user=user, problem=problem, contest=contest, language=lang, source="x", verdict="AC")
    b = Submission.objects.create(user=other, problem=problem, contest=contest, language=lang, source="x", verdict="AC")
    flag = SimilarityFlag.objects.create(submission_a=a, submission_b=b, score=0.9)

    client.force_login(staff)
    html = client.get(reverse("integrity:contest_report", args=[contest.pk])).content.decode()
    assert html.index("vali") < html.index(">ali<")  # 2 pastes (risk 10) outranks 1 blur (risk 1)

    r = client.post(reverse("integrity:flag_review", args=[flag.pk]), {"note": "bir xil"})
    assert r.status_code == 302
    flag.refresh_from_db()
    assert flag.reviewed is True and flag.note == "bir xil"


def test_flag_review_requires_staff(client, contest, user):
    client.force_login(user)
    assert client.post(reverse("integrity:flag_run", args=[contest.pk])).status_code in (302, 403)
