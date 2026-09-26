from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.contests.models import Contest, ContestProblem, Participation
from apps.problems.models import Language, Problem, TestCase

from .models import Submission, TestResult, UserProblemSolved


@pytest.fixture
def python(db):
    return Language.objects.create(code="python", name="Python 3", docker_image="codearena-judge-python",
                                   run_cmd="python3 main.py", tl_multiplier=3.0)


@pytest.fixture
def problem(db):
    author = User.objects.create_user("teacher", password="x")
    p = Problem.objects.create(slug="a-plus-b", title="A + B", statement_md="x", author=author, tl_ms=1000,
                               points=10)
    TestCase.objects.create(problem=p, input="1 2\n", expected="3\n", is_sample=True, order=0)
    TestCase.objects.create(problem=p, input="5 7\n", expected="12\n", order=1)
    return p


@pytest.fixture
def user(db):
    return User.objects.create_user("ali", password="x")


def test_submit_requires_login(client, problem, python):
    r = client.post(reverse("submissions:submit", args=[problem.slug]), {"language": "python", "source": "x"})
    assert r.status_code == 302 and r.url.startswith(reverse("login"))


@patch("apps.submissions.views.django_rq.enqueue")
def test_submit_creates_pending_and_enqueues(enqueue, client, problem, python, user):
    client.force_login(user)
    r = client.post(reverse("submissions:submit", args=[problem.slug]),
                    {"language": "python", "source": "print(1)"})
    s = Submission.objects.get()
    assert r.status_code == 302 and r.url == reverse("problems:detail", args=[s.problem.slug])
    assert s.verdict == "PENDING" and s.user == user and s.total == 0
    enqueue.assert_called_once()
    assert enqueue.call_args.args[1] == s.pk


@patch("apps.submissions.views.django_rq.enqueue")
def test_submit_during_running_contest_tags_submission_and_skips_points(enqueue, client, problem, python, user):
    problem.is_public = False
    problem.save()
    contest = Contest.objects.create(
        title="Sprint", start=timezone.now() - timezone.timedelta(minutes=5),
        end=timezone.now() + timezone.timedelta(minutes=55))
    ContestProblem.objects.create(contest=contest, problem=problem, label="A", points=100)
    Participation.objects.create(user=user, contest=contest)
    client.force_login(user)
    client.post(reverse("submissions:submit", args=[problem.slug]), {"language": "python", "source": "x"})
    s = Submission.objects.get()
    assert s.contest == contest


@patch("apps.submissions.views.django_rq.enqueue")
def test_submit_rejected_when_ip_prefix_no_longer_matches(enqueue, client, problem, python, user):
    problem.is_public = False
    problem.save()
    contest = Contest.objects.create(
        title="Sprint", start=timezone.now() - timezone.timedelta(minutes=5),
        end=timezone.now() + timezone.timedelta(minutes=55), allowed_ip_prefix="10.0.")
    ContestProblem.objects.create(contest=contest, problem=problem, label="A", points=100)
    Participation.objects.create(user=user, contest=contest)
    client.force_login(user)
    r = client.post(reverse("submissions:submit", args=[problem.slug]),
                    {"language": "python", "source": "x"}, REMOTE_ADDR="192.168.1.1")
    assert r.status_code == 400
    assert Submission.objects.count() == 0


def test_submit_rejects_empty_source(client, problem, python, user):
    client.force_login(user)
    r = client.post(reverse("submissions:submit", args=[problem.slug]), {"language": "python", "source": "  "})
    assert r.status_code == 400 and Submission.objects.count() == 0


def test_detail_only_owner(client, problem, python, user):
    s = Submission.objects.create(user=user, problem=problem, language=python, source="x")
    other = User.objects.create_user("vali", password="x")
    client.force_login(other)
    assert client.get(reverse("submissions:detail", args=[s.pk])).status_code == 404
    client.force_login(user)
    assert client.get(reverse("submissions:detail", args=[s.pk])).status_code == 200


def test_status_partial_polls_until_terminal(client, problem, python, user):
    s = Submission.objects.create(user=user, problem=problem, language=python, source="x")
    client.force_login(user)
    r = client.get(reverse("submissions:status", args=[s.pk]))
    assert b'hx-trigger="every 1s"' in r.content
    s.verdict, s.mem_kb = "AC", 9216
    s.save()
    r = client.get(reverse("submissions:status", args=[s.pk]))
    assert b"hx-trigger" not in r.content and b"ca-verdict-ac" in r.content
    assert b"9 MB" in r.content


def test_status_compact_poll_stays_compact(client, problem, python, user):
    """Problem-page sidebar polls with ?compact=1: once terminal it must not grow the test grid."""
    s = Submission.objects.create(user=user, problem=problem, language=python, source="x", verdict="RUNNING")
    client.force_login(user)
    r = client.get(reverse("submissions:status", args=[s.pk]) + "?compact=1")
    assert b"?compact=1" in r.content  # next poll keeps the flag
    tc = problem.testcases.first()
    TestResult.objects.create(submission=s, testcase=tc, verdict="WA")
    s.verdict, s.passed, s.total = "WA", 0, 2
    s.save()
    compact = client.get(reverse("submissions:status", args=[s.pk]) + "?compact=1").content
    full = client.get(reverse("submissions:status", args=[s.pk])).content
    assert b"ca-test-WA" not in compact and b"ca-verdict-bad" in compact
    assert b"ca-test-WA" in full


@patch("apps.submissions.views.django_rq.get_queue")
def test_trial_runs_samples_without_a_submission(get_queue, client, problem, python, user):
    get_queue.return_value.enqueue.return_value.id = "job1"
    client.force_login(user)
    r = client.post(reverse("submissions:trial", args=[problem.slug]), {"language": "python", "source": "x"})
    assert r.json() == {"id": "job1"}
    get_queue.assert_called_with("run")
    args, kwargs = get_queue.return_value.enqueue.call_args
    assert args[1:4] == ("python", "x", ["1 2\n"]) and args[4] == ["3\n"]  # samples only
    assert kwargs["meta"] == {"user_id": user.pk}
    assert not Submission.objects.exists()


@patch("apps.submissions.views.django_rq.get_queue")
def test_trial_custom_stdin_has_no_expected(get_queue, client, problem, python, user):
    get_queue.return_value.enqueue.return_value.id = "job1"
    client.force_login(user)
    client.post(reverse("submissions:trial", args=[problem.slug]), {"language": "python", "source": "x", "stdin": "9 9"})
    args = get_queue.return_value.enqueue.call_args.args
    assert args[3] == ["9 9"] and args[4] is None


@patch("apps.submissions.views.django_rq.get_queue")
def test_trial_status_is_private(get_queue, client, problem, user):
    job = get_queue.return_value.fetch_job.return_value
    job.meta = {"user_id": user.pk + 1}
    client.force_login(user)
    assert client.get(reverse("submissions:trial_status", args=["job1"])).status_code == 404
    job.meta = {"user_id": user.pk}
    job.get_status.return_value = "finished"
    job.return_value.return_value = {"verdict": "AC", "log": "", "cases": [], "total": 1}
    assert client.get(reverse("submissions:trial_status", args=["job1"])).json()["verdict"] == "AC"


@patch("judge.runner.sandbox.run_tests", return_value=[("3\n", "OK", 5, 1024), ("7\n", "OK", 6, 1024)])
@patch("judge.runner.sandbox.compile", return_value=(True, ""))
def test_run_trial_marks_each_sample(compile_, run_tests, python):
    from judge.runner import run_trial
    r = run_trial("python", "x", ["1 2\n", "3 3\n"], ["3\n", "6\n"], 1000, 256)
    assert r["verdict"] == "WA" and r["total"] == 2
    assert [c["verdict"] for c in r["cases"]] == ["AC", "WA"]
    run_tests.return_value = [("3\n", "OK", 5, 1024)]
    custom = run_trial("python", "x", ["1 2\n"], None, 1000, 256)
    assert custom["verdict"] == "OK" and custom["cases"][0]["expected"] is None


@patch("judge.runner.sandbox.run_tests")
@patch("judge.runner.sandbox.compile", return_value=(True, ""))
def test_runner_ac(compile_, run_tests, problem, python, user):
    from judge.runner import run_submission
    run_tests.return_value = [("3\n", "OK", 10, 2048), ("12\n", "OK", 12, 1024)]
    s = Submission.objects.create(user=user, problem=problem, language=python, source="x")
    run_submission(s.pk)
    s.refresh_from_db()
    assert s.verdict == "AC" and s.passed == 2 and s.total == 2 and s.exec_ms == 12 and s.mem_kb == 2048
    assert s.results.count() == 2


@patch("judge.runner.sandbox.run_tests")
@patch("judge.runner.sandbox.compile", return_value=(True, ""))
def test_runner_wa_stops_early(compile_, run_tests, problem, python, user):
    from judge.runner import run_submission
    run_tests.return_value = [("4\n", "OK", 10, 1024), ("12\n", "OK", 12, 1024)]
    s = Submission.objects.create(user=user, problem=problem, language=python, source="x")
    run_submission(s.pk)
    s.refresh_from_db()
    assert s.verdict == "WA" and s.passed == 0 and s.total == 2
    assert s.results.get().verdict == "WA"


@patch("judge.runner.sandbox.run_tests")
@patch("judge.runner.sandbox.compile", return_value=(False, "SyntaxError"))
def test_runner_ce(compile_, run_tests, problem, python, user):
    from judge.runner import run_submission
    s = Submission.objects.create(user=user, problem=problem, language=python, source="x")
    run_submission(s.pk)
    s.refresh_from_db()
    assert s.verdict == "CE" and s.compile_log == "SyntaxError"
    run_tests.assert_not_called()


@patch("judge.runner.sandbox.run_tests", return_value=[("", "TLE", 3100, 1024)])
@patch("judge.runner.sandbox.compile", return_value=(True, ""))
def test_runner_tle(compile_, run_tests, problem, python, user):
    from judge.runner import run_submission
    s = Submission.objects.create(user=user, problem=problem, language=python, source="x")
    run_submission(s.pk)
    s.refresh_from_db()
    assert s.verdict == "TLE"


@patch("judge.runner.sandbox.run_tests", return_value=[])
@patch("judge.runner.sandbox.compile", return_value=(True, ""))
def test_runner_runs_tests_in_their_order(compile_, run_tests, problem, python, user):
    from judge.runner import run_submission
    TestCase.objects.create(problem=problem, input="first\n", expected="x\n", order=-1)
    s = Submission.objects.create(user=user, problem=problem, language=python, source="x")
    run_submission(s.pk)
    assert run_tests.call_args.args[2] == ["first\n", "1 2\n", "5 7\n"]


# --- practice points: spec §2 step 5 says first AC per (user, problem) awards
# problem.points once, via a UserProblemSolved row. Not in the original task
# brief text; added here since judge.runner is exactly where AC is decided.

@patch("judge.runner.sandbox.run_tests")
@patch("judge.runner.sandbox.compile", return_value=(True, ""))
def test_runner_first_ac_awards_practice_points(compile_, run_tests, problem, python, user):
    from judge.runner import run_submission
    run_tests.return_value = [("3\n", "OK", 10, 1024), ("12\n", "OK", 12, 1024)]
    s = Submission.objects.create(user=user, problem=problem, language=python, source="x")
    run_submission(s.pk)
    user.refresh_from_db()
    assert user.practice_points == problem.points
    assert UserProblemSolved.objects.filter(user=user, problem=problem, first_ac_submission=s).exists()


@patch("judge.runner.sandbox.run_tests")
@patch("judge.runner.sandbox.compile", return_value=(True, ""))
def test_runner_second_ac_does_not_award_points_again(compile_, run_tests, problem, python, user):
    from judge.runner import run_submission
    run_tests.side_effect = [[("3\n", "OK", 10, 1024), ("12\n", "OK", 12, 1024)], [("3\n", "OK", 10, 1024), ("12\n", "OK", 12, 1024)]]
    s1 = Submission.objects.create(user=user, problem=problem, language=python, source="x")
    run_submission(s1.pk)
    s2 = Submission.objects.create(user=user, problem=problem, language=python, source="x")
    run_submission(s2.pk)
    user.refresh_from_db()
    assert user.practice_points == problem.points
    assert UserProblemSolved.objects.filter(user=user, problem=problem).count() == 1


@patch("judge.runner.sandbox.run_tests")
@patch("judge.runner.sandbox.compile", return_value=(True, ""))
def test_runner_wa_awards_no_points(compile_, run_tests, problem, python, user):
    from judge.runner import run_submission
    run_tests.return_value = [("4\n", "OK", 10, 1024)]
    s = Submission.objects.create(user=user, problem=problem, language=python, source="x")
    run_submission(s.pk)
    user.refresh_from_db()
    assert user.practice_points == 0


@patch("judge.runner.sandbox.run_tests")
@patch("judge.runner.sandbox.compile", return_value=(True, ""))
def test_runner_contest_ac_awards_no_practice_points(compile_, run_tests, problem, python, user):
    """spec §2 step 5: practice points are awarded on AC 'outside contest' only."""
    from judge.runner import run_submission
    contest = Contest.objects.create(title="Sprint", start=timezone.now(), end=timezone.now() + timezone.timedelta(hours=1))
    run_tests.return_value = [("3\n", "OK", 10, 1024), ("12\n", "OK", 12, 1024)]
    s = Submission.objects.create(user=user, problem=problem, contest=contest, language=python, source="x")
    run_submission(s.pk)
    s.refresh_from_db()
    user.refresh_from_db()
    assert s.verdict == "AC"
    assert user.practice_points == 0
    assert not UserProblemSolved.objects.filter(user=user, problem=problem).exists()


@patch("judge.runner.sandbox.run_tests")
@patch("judge.runner.sandbox.compile", return_value=(True, ""))
def test_runner_retry_while_running_does_not_duplicate_results(compile_, run_tests, problem, python, user):
    """RQ retry of a RUNNING submission must clear prior TestResults and finish once."""
    from apps.submissions.models import TestResult
    from judge.runner import run_submission

    s = Submission.objects.create(
        user=user, problem=problem, language=python, source="x", verdict="RUNNING")
    # Simulate a crashed prior attempt that left a partial result row.
    TestResult.objects.create(
        submission=s, testcase=problem.testcases.first(), verdict="AC", exec_ms=5)
    run_tests.return_value = [("3\n", "OK", 10, 1024), ("12\n", "OK", 12, 1024)]

    run_submission(s.pk)
    s.refresh_from_db()
    assert s.verdict == "AC"
    assert s.results.count() == 2

    # Terminal retry is a no-op (no duplicate rows).
    run_submission(s.pk)
    s.refresh_from_db()
    assert s.verdict == "AC"
    assert s.results.count() == 2


@pytest.fixture
def sql_lang(db):
    return Language.objects.create(code="sql", name="SQL (SQLite)", docker_image="-", run_cmd="-")


@pytest.fixture
def sql_problem(db):
    from apps.problems.models import SQLDataset

    author = User.objects.create_user("teacher2", password="x")
    p = Problem.objects.create(slug="older-than-21", title="21+", statement_md="x", author=author,
                               kind=Problem.Kind.SQL, tl_ms=1000, points=10)
    SQLDataset.objects.create(
        problem=p,
        schema_sql="CREATE TABLE users(id INTEGER, name TEXT, age INTEGER);",
        seed_sql="INSERT INTO users VALUES (1,'ali',20),(2,'vali',25),(3,'guli',22);",
        expected_result="guli\nvali",
    )
    return p


def test_runner_sql_ac(sql_problem, sql_lang, user):
    from judge.runner import run_submission
    s = Submission.objects.create(user=user, problem=sql_problem, language=sql_lang,
                                  source="SELECT name FROM users WHERE age > 21")
    run_submission(s.pk)
    s.refresh_from_db()
    assert s.verdict == "AC" and s.passed == 1 and s.total == 1
    assert s.results.count() == 0
    user.refresh_from_db()
    assert user.practice_points == 10


def test_runner_sql_wa(sql_problem, sql_lang, user):
    from judge.runner import run_submission
    s = Submission.objects.create(user=user, problem=sql_problem, language=sql_lang,
                                  source="SELECT name FROM users")
    run_submission(s.pk)
    s.refresh_from_db()
    assert s.verdict == "WA"


def test_runner_sql_denies_write_query(sql_problem, sql_lang, user):
    from judge.runner import run_submission
    s = Submission.objects.create(user=user, problem=sql_problem, language=sql_lang,
                                  source="DELETE FROM users")
    run_submission(s.pk)
    s.refresh_from_db()
    assert s.verdict == "RE"


def test_submit_and_detail_render_for_sql_problem(client, sql_problem, sql_lang, user):
    with patch("apps.submissions.views.django_rq.enqueue"):
        client.force_login(user)
        r = client.post(reverse("submissions:submit", args=[sql_problem.slug]),
                        {"language": "sql", "source": "SELECT name FROM users"})
        assert r.status_code == 302
    s = Submission.objects.get(problem=sql_problem)
    assert client.get(reverse("submissions:detail", args=[s.pk])).status_code == 200


def test_problem_detail_shows_schema_not_testcase_samples(client, sql_problem, sql_lang):
    r = client.get(reverse("problems:detail", args=[sql_problem.slug]))
    assert r.status_code == 200
    assert b"CREATE TABLE users" in r.content
    assert b"Jadval tuzilishi" in r.content


def test_mine_paginates_at_50(client, problem, python, user):
    Submission.objects.bulk_create([
        Submission(user=user, problem=problem, language=python, source="x") for _ in range(55)
    ])
    client.force_login(user)
    r = client.get(reverse("submissions:mine"))
    assert r.status_code == 200
    assert len(r.context["subs"]) == 50
    assert r.context["subs"].paginator.num_pages == 2


@patch("apps.submissions.views.django_rq.enqueue")
def test_submit_rate_limited_after_max_per_window(enqueue, client, problem, python, user):
    from django.core.cache import cache
    from apps.submissions.views import RATE_LIMIT_MAX

    cache.clear()
    client.force_login(user)
    for _ in range(RATE_LIMIT_MAX):
        r = client.post(reverse("submissions:submit", args=[problem.slug]), {"language": "python", "source": "x"})
        assert r.status_code == 302
    r = client.post(reverse("submissions:submit", args=[problem.slug]), {"language": "python", "source": "x"})
    assert r.status_code == 429
    cache.clear()
