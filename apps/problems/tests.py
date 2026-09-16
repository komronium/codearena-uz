import pytest
from django.urls import reverse

from apps.accounts.models import User
from .models import Problem, TestCase


@pytest.fixture
def problem(db):
    author = User.objects.create_user("teacher", password="x", role="teacher")
    p = Problem.objects.create(slug="a-plus-b", title="A + B", statement_md="Ikki son **yig'indisi**.",
                               author=author)
    TestCase.objects.create(problem=p, input="1 2\n", expected="3\n", is_sample=True, order=0)
    TestCase.objects.create(problem=p, input="5 7\n", expected="12\n", is_sample=False, order=1)
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


def test_detail_renders_markdown_and_samples_only(client, problem):
    r = client.get(reverse("problems:detail", kwargs={"slug": "a-plus-b"}))
    assert r.status_code == 200
    assert b"<strong>yig&#x27;indisi</strong>" in r.content or b"<strong>yig'indisi</strong>" in r.content
    assert b"1 2" in r.content
    assert b"5 7" not in r.content


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
