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
from .similarity import matched_lines, similarity

LONG_SOURCE = """n = int(input())
arr = list(map(int, input().split()))
arr.sort()
total = 0
for x in arr:
    total += x
print(total, arr[n // 2])
"""


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
    source = LONG_SOURCE
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
    source = LONG_SOURCE
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


def test_similarity_survives_rename_extra_import_and_comments():
    renamed = "import sys\n# my own solution\n" + LONG_SOURCE.replace("arr", "xs").replace("total", "acc")
    assert similarity(LONG_SOURCE, renamed) >= 0.9
    hit_a, hit_b = matched_lines(LONG_SOURCE, renamed)
    assert hit_a == set(range(7)) and hit_b == set(range(2, 9))


def _ac(user, problem, contest, lang, source):
    return Submission.objects.create(user=user, problem=problem, contest=contest, language=lang,
                                     source=source, verdict="AC")


def test_flag_similarity_ignores_short_code(flag_contest, flag_problem, flag_python):
    short = "a, b = map(int, input().split())\nprint(a + b)"
    for name in ("s1", "s2"):
        _ac(User.objects.create_user(name, password="x"), flag_problem, flag_contest, flag_python, short)
    call_command("flag_similarity", flag_contest.pk, stdout=StringIO())
    assert SimilarityFlag.objects.count() == 0


def test_flag_similarity_one_flag_per_user_pair_and_prunes_stale(flag_contest, flag_problem, flag_python):
    ali = User.objects.create_user("p1", password="x")
    bob = User.objects.create_user("p2", password="x")
    _ac(ali, flag_problem, flag_contest, flag_python, LONG_SOURCE)
    _ac(ali, flag_problem, flag_contest, flag_python, LONG_SOURCE + "\n")
    _ac(bob, flag_problem, flag_contest, flag_python, LONG_SOURCE)
    # a loose-rule leftover between the same pair: replaced, not duplicated
    x = _ac(ali, flag_problem, flag_contest, flag_python, "x")
    y = _ac(bob, flag_problem, flag_contest, flag_python, "y")
    SimilarityFlag.objects.create(submission_a=x, submission_b=y, score=0.86)
    call_command("flag_similarity", flag_contest.pk, stdout=StringIO())
    assert SimilarityFlag.objects.count() == 1
    assert SimilarityFlag.objects.get().score == 1.0


def test_flag_similarity_keeps_reviewed_flags(flag_contest, flag_problem, flag_python):
    ali = User.objects.create_user("r1", password="x")
    bob = User.objects.create_user("r2", password="x")
    x = _ac(ali, flag_problem, flag_contest, flag_python, "x")
    y = _ac(bob, flag_problem, flag_contest, flag_python, "y")
    SimilarityFlag.objects.create(submission_a=x, submission_b=y, score=0.86, reviewed=True, note="checked")
    call_command("flag_similarity", flag_contest.pk, stdout=StringIO())
    assert SimilarityFlag.objects.get().note == "checked"


def test_report_shows_flag_side_by_side_with_shared_lines(client, flag_contest, flag_problem, flag_python):
    staff = User.objects.create_user("t9", password="x", is_staff=True)
    ali = User.objects.create_user("c1", password="x")
    bob = User.objects.create_user("c2", password="x")
    _ac(ali, flag_problem, flag_contest, flag_python, LONG_SOURCE)
    _ac(bob, flag_problem, flag_contest, flag_python, LONG_SOURCE.replace("arr", "xs"))
    call_command("flag_similarity", flag_contest.pk, stdout=StringIO())
    client.force_login(staff)
    html = client.get(reverse("integrity:contest_report", args=[flag_contest.pk])).content.decode()
    assert html.count("ca-cmp-line is-hit") == 14  # 7 shared lines on each side
    assert "xs.sort()" in html and "arr.sort()" in html


def test_event_records_problem_and_away_time(client, flag_contest, flag_problem):
    ali = User.objects.create_user("ev1", password="x")
    Participation.objects.create(user=ali, contest=flag_contest)
    client.force_login(ali)
    url = reverse("integrity:event")
    r = client.post(url, {"contest_id": flag_contest.pk, "problem_id": flag_problem.pk, "kind": "focus", "away_ms": "65000"})
    assert r.status_code == 200
    fe = FocusEvent.objects.get()
    assert fe.problem == flag_problem and fe.away_ms == 65000
    other = Problem.objects.create(slug="zz", title="Z", statement_md="x", author=ali)
    r = client.post(url, {"contest_id": flag_contest.pk, "problem_id": other.pk, "kind": "blur"})
    assert r.status_code == 400


def test_snapshot_saves_only_changes(client, flag_contest, flag_problem, flag_python):
    from .models import CodeSnapshot
    ali = User.objects.create_user("sn1", password="x")
    Participation.objects.create(user=ali, contest=flag_contest)
    client.force_login(ali)
    url = reverse("integrity:snapshot")
    data = {"contest_id": flag_contest.pk, "problem_id": flag_problem.pk, "language": "python", "source": "a = 1"}
    for _ in range(2):
        assert client.post(url, data).status_code == 200
    client.post(url, data | {"source": "a = 1\nprint(a)"})
    assert list(CodeSnapshot.objects.values_list("source", flat=True)) == ["a = 1", "a = 1\nprint(a)"]
    assert CodeSnapshot.objects.first().language == flag_python
    stranger = User.objects.create_user("sn2", password="x")
    client.force_login(stranger)
    assert client.post(url, data).status_code == 400


def test_report_lists_too_fast_and_back_and_solve(client, flag_contest, flag_problem, flag_python):
    flag_problem.difficulty = Problem.Difficulty.MEDIUM
    flag_problem.save()
    staff = User.objects.create_user("st1", password="x", is_staff=True)
    fast = User.objects.create_user("quick", password="x")
    back = User.objects.create_user("returner", password="x")
    for u in (fast, back):
        Participation.objects.create(user=u, contest=flag_contest)
    FocusEvent.objects.create(user=fast, contest=flag_contest, kind="view", problem=flag_problem)
    _ac(fast, flag_problem, flag_contest, flag_python, LONG_SOURCE)
    FocusEvent.objects.create(user=back, contest=flag_contest, kind="focus", away_ms=95_000)
    _ac(back, flag_problem, flag_contest, flag_python, LONG_SOURCE)
    client.force_login(staff)
    html = client.get(reverse("integrity:contest_report", args=[flag_contest.pk])).content.decode()
    section = html[html.index("Shubhali yechimlar"):html.index("O‘xshash kodlar")]
    assert "quick" in section and "ochilgandan" in section
    assert "returner" in section and "95 s tashqarida" in section


def test_replay_shows_frames_and_jumps_for_staff_only(client, flag_contest, flag_problem, flag_python):
    from .models import CodeSnapshot
    ali = User.objects.create_user("rp1", password="x")
    CodeSnapshot.objects.create(user=ali, contest=flag_contest, problem=flag_problem, source="n = 1")
    CodeSnapshot.objects.create(user=ali, contest=flag_contest, problem=flag_problem, source=LONG_SOURCE * 3)
    url = reverse("integrity:replay", args=[flag_contest.pk, ali.pk, flag_problem.pk])
    client.force_login(ali)
    assert client.get(url).status_code in (302, 403)
    client.force_login(User.objects.create_user("rp2", password="x", is_staff=True))
    r = client.get(url)
    assert r.status_code == 200
    assert len(r.context["frames"]) == 2 and len(r.context["jumps"]) == 1
    assert "keskin sakrash" in r.content.decode()


def test_contest_page_tracks_registered_participant_during_contest(client, flag_contest):
    ali = User.objects.create_user("tr1", password="x")
    client.force_login(ali)
    url = reverse("contests:detail", args=[flag_contest.pk])
    assert "ca-away" not in client.get(url).content.decode()
    Participation.objects.create(user=ali, contest=flag_contest)
    assert 'id="ca-away"' in client.get(url).content.decode()


def test_flag_run_checks_only_chosen_problems(client, flag_contest, flag_problem, flag_python):
    other = Problem.objects.create(slug="b", title="B", statement_md="x", author=flag_problem.author)
    ContestProblem.objects.create(contest=flag_contest, problem=other, label="B")
    ali = User.objects.create_user("ch1", password="x")
    bob = User.objects.create_user("ch2", password="x")
    for p in (flag_problem, other):
        for u in (ali, bob):
            _ac(u, p, flag_contest, flag_python, LONG_SOURCE)
    client.force_login(User.objects.create_user("ch3", password="x", is_staff=True))
    url = reverse("integrity:flag_run", args=[flag_contest.pk])
    client.post(url)  # nothing picked: nothing checked
    assert SimilarityFlag.objects.count() == 0
    client.post(url, {"problems": ["B"]})
    assert list(SimilarityFlag.objects.values_list("submission_a__problem__slug", flat=True)) == ["b"]
