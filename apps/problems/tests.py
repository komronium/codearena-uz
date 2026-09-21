import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.contests.models import Contest, ContestProblem, Participation
from .models import Language, Problem, Tag, TestCase


@pytest.fixture
def problem(db):
    author = User.objects.create_user("teacher", password="x", role="teacher")
    p = Problem.objects.create(slug="a-plus-b", title="A + B", statement_md="Ikki son **yig'indisi**.",
                               author=author)
    TestCase.objects.create(problem=p, input="1 2\n", expected="3\n", is_sample=True, order=0)
    TestCase.objects.create(problem=p, input="99 1\n", expected="100\n", is_sample=False, order=1)
    return p


def test_list_shows_public_problem(client, problem):
    r = client.get(reverse("problems:list"))
    assert r.status_code == 200
    assert b"A + B" in r.content


def test_list_hides_private_problem(client, problem):
    problem.is_public = False
    problem.save()
    r = client.get(reverse("problems:list"))
    assert b"A + B" not in r.content


def test_list_marks_solved_problem_for_logged_in_user(client, problem):
    from apps.problems.models import Language
    from apps.submissions.models import Submission, UserProblemSolved

    user = User.objects.create_user("ali", password="x")
    python = Language.objects.create(code="python", name="Python 3", docker_image="codearena-judge-python",
                                      run_cmd="python3 main.py")
    sub = Submission.objects.create(user=user, problem=problem, language=python, source="x", verdict="AC")
    UserProblemSolved.objects.create(user=user, problem=problem, first_ac_submission=sub)

    client.force_login(user)
    r = client.get(reverse("problems:list"))
    assert b'title="Yechilgan"' in r.content


def test_list_does_not_mark_unsolved_problem(client, problem):
    user = User.objects.create_user("ali", password="x")
    client.force_login(user)
    r = client.get(reverse("problems:list"))
    assert b'title="Yechilgan"' not in r.content


def test_detail_renders_markdown_and_samples_only(client, problem):
    r = client.get(reverse("problems:detail", kwargs={"slug": "a-plus-b"}))
    assert r.status_code == 200
    assert b"<strong>yig&#x27;indisi</strong>" in r.content or b"<strong>yig'indisi</strong>" in r.content
    assert b"1 2" in r.content
    assert b"99 1" not in r.content


def test_private_detail_404(client, problem):
    problem.is_public = False
    problem.save()
    assert client.get(reverse("problems:detail", kwargs={"slug": "a-plus-b"})).status_code == 404


def test_detail_strips_script_tags_from_statement(client, problem):
    problem.statement_md = "hi <script>alert(1)</script> there"
    problem.save()
    r = client.get(reverse("problems:detail", kwargs={"slug": "a-plus-b"}))
    assert b"<script>alert(1)</script>" not in r.content
    assert b"&lt;script&gt;alert(1)&lt;/script&gt;" in r.content


@pytest.fixture
def running_contest(db, problem):
    contest = Contest.objects.create(
        title="Sprint", start=timezone.now() - timezone.timedelta(minutes=5),
        end=timezone.now() + timezone.timedelta(minutes=55))
    ContestProblem.objects.create(contest=contest, problem=problem, label="A", points=100)
    return contest


def test_private_contest_problem_visible_to_registered_participant(client, problem, running_contest):
    problem.is_public = False
    problem.save()
    user = User.objects.create_user("ali", password="x")
    Participation.objects.create(user=user, contest=running_contest)
    client.force_login(user)
    r = client.get(reverse("problems:detail", kwargs={"slug": "a-plus-b"}))
    assert r.status_code == 200
    assert b"Musobaqa rejimi" in r.content


def test_private_contest_problem_404_for_non_participant(client, problem, running_contest):
    problem.is_public = False
    problem.save()
    user = User.objects.create_user("bob", password="x")
    client.force_login(user)
    assert client.get(reverse("problems:detail", kwargs={"slug": "a-plus-b"})).status_code == 404


def test_upcoming_contest_problem_secret_even_if_public(client, problem):
    """Problems of a not-yet-started contest are hidden from list, detail, contest page
    and submit — is_public is irrelevant until the contest starts."""
    contest = Contest.objects.create(
        title="Soon", start=timezone.now() + timezone.timedelta(hours=1),
        end=timezone.now() + timezone.timedelta(hours=3))
    ContestProblem.objects.create(contest=contest, problem=problem, label="A", points=100)
    user = User.objects.create_user("ali", password="x")
    Participation.objects.create(user=user, contest=contest)
    client.force_login(user)

    assert problem not in client.get(reverse("problems:list")).context["problems"].object_list
    assert client.get(reverse("problems:detail", kwargs={"slug": "a-plus-b"})).status_code == 404
    assert b"a-plus-b" not in client.get(reverse("contests:detail", kwargs={"pk": contest.pk})).content
    lang = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    r = client.post(reverse("submissions:submit", kwargs={"slug": "a-plus-b"}),
                    {"language": lang.code, "source": "print(1)"})
    assert r.status_code == 404

    contest.start = timezone.now() - timezone.timedelta(minutes=1)
    contest.save()
    assert client.get(reverse("problems:detail", kwargs={"slug": "a-plus-b"})).status_code == 200


def test_list_sorts_by_column_and_direction(client, problem):
    author = problem.author
    hard = Problem.objects.create(slug="z", title="Zzz", statement_md="x", author=author, difficulty="hard")
    easy = Problem.objects.create(slug="b", title="Bbb", statement_md="x", author=author, difficulty="beginner")

    def ids(**params):
        return [p.id for p in client.get(reverse("problems:list"), params).context["problems"].object_list]

    assert ids(sort="title") == [problem.id, easy.id, hard.id]  # "A + B" < "Bbb" < "Zzz"
    assert ids(sort="title", dir="desc") == [hard.id, easy.id, problem.id]
    assert ids(sort="difficulty")[0] == easy.id and ids(sort="difficulty", dir="desc")[0] == hard.id
    assert ids(sort="bogus") == ids()  # unknown column falls back to id


def test_list_pagination_keeps_filters_and_shows_page_numbers(client, problem):
    author = problem.author
    for i in range(65):
        Problem.objects.create(slug=f"p{i}", title=f"P{i}", statement_md="x", author=author)
    r = client.get(reverse("problems:list"), {"q": "P", "sort": "title", "page": 2})
    html = r.content.decode()
    assert 'aria-current="page">2<' in html
    assert "?q=P&amp;sort=title&amp;page=3" in html
    assert "31–60 / 65" in html


def test_list_paginates_at_30(client, problem):
    author = problem.author
    for i in range(35):
        Problem.objects.create(slug=f"p{i}", title=f"P{i}", statement_md="x", author=author)
    r = client.get(reverse("problems:list"))
    assert r.status_code == 200
    assert len(r.context["problems"]) == 30
    assert r.context["problems"].paginator.num_pages == 2


def test_list_search_by_title(client, problem):
    Problem.objects.create(slug="other", title="Binary Search", statement_md="x", author=problem.author)
    r = client.get(reverse("problems:list"), {"q": "Binary"})
    assert b"Binary Search" in r.content
    assert b"A + B" not in r.content


def test_list_filter_by_tag(client, problem):
    dp = Tag.objects.create(name="dp")
    tagged = Problem.objects.create(slug="tagged", title="DP Problem", statement_md="x", author=problem.author)
    tagged.tags.add(dp)
    r = client.get(reverse("problems:list"), {"tag": "dp"})
    assert b"DP Problem" in r.content
    assert b"A + B" not in r.content


@pytest.mark.django_db
def test_problem_page_offers_to_join_running_contest(client):
    from django.utils import timezone

    from apps.contests.models import Contest, ContestProblem, Participation

    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    ali = User.objects.create_user("ali", password="x")
    p = Problem.objects.create(slug="p", title="P", statement_md="x", author=staff)
    c = Contest.objects.create(title="Live", start=timezone.now() - timezone.timedelta(minutes=5),
                               end=timezone.now() + timezone.timedelta(hours=1))
    ContestProblem.objects.create(contest=c, problem=p, label="A")
    client.force_login(ali)
    assert "Musobaqaga qo‘shilish" in client.get(reverse("problems:detail", args=["p"])).content.decode()
    Participation.objects.create(user=ali, contest=c)
    assert "Musobaqaga qo‘shilish" not in client.get(reverse("problems:detail", args=["p"])).content.decode()
