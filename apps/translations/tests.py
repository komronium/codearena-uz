import json
from types import SimpleNamespace

import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.problems.models import Problem, ProblemHint
from apps.translations import service
from apps.translations.models import ContentTranslation


@pytest.fixture
def problem(db):
    author = User.objects.create_user("author", password="x", is_staff=True)
    p = Problem.objects.create(slug="sum", title="Yig‘indi", statement_md="Ikki sonning yig‘indisini toping.", is_public=True,
                               status=Problem.Status.APPROVED, author=author)
    ProblemHint.objects.create(problem=p, order=1, body_md="Ikkalasini qo‘shing.", cost_pct=10)
    return p


def _en(client):
    client.cookies["ca_lang"] = "en"
    return client


def test_the_language_switch_remembers_the_choice_in_a_cookie_and_on_the_account(client, db):
    assert 'lang="uz"' in client.get(reverse("login")).content.decode()
    r = client.post(reverse("set_language"), {"language": "en", "next": "/accounts/login/"})
    assert r.status_code == 302 and r.url == "/accounts/login/" and r.cookies["ca_lang"].value == "en"
    page = client.get(reverse("login")).content.decode()
    assert 'lang="en"' in page and "Welcome" in page and "Xush kelibsiz" not in page
    # an outside address is not followed
    assert client.post(reverse("set_language"), {"language": "uz", "next": "https://evil.example/"}).url == "/"
    u = User.objects.create_user("lang", password="x")
    client.force_login(u)
    client.post(reverse("set_language"), {"language": "en"})
    u.refresh_from_db()
    assert u.language == "en"
    client.cookies.pop("ca_lang")  # a new browser: the account's choice still holds
    assert 'lang="en"' in client.get(reverse("home")).content.decode()


def test_english_text_is_shown_only_once_an_admin_confirms_it(client, problem):
    service.save_draft(problem, "title", "en", "Sum", by_ai=True)
    service.save_draft(problem, "statement_md", "en", "Find the sum of two numbers.", by_ai=True)
    en = _en(client)
    page = en.get(reverse("problems:detail", args=["sum"])).content.decode()
    assert "Find the sum" not in page and "Yig‘indi" in page and "hasn&#x27;t been translated" in page.replace("’", "&#x27;") or "translated yet" in page
    assert "Sum" not in en.get(reverse("problems:list")).content.decode().split("Yig‘indi")[0][-200:]
    admin = User.objects.create_user("boss", password="x", is_staff=True)
    assert service.confirm_all(problem, admin) == 2
    page = en.get(reverse("problems:detail", args=["sum"])).content.decode()
    assert "Find the sum of two numbers." in page and "translated yet" not in page
    assert "<title>Sum" in page.replace("\n", "") or "Sum" in page
    assert "Sum" in en.get(reverse("problems:list")).content.decode()
    # the Uzbek page is untouched, and the stored text is never replaced
    en.cookies["ca_lang"] = "uz"
    assert "Ikki sonning" in en.get(reverse("problems:detail", args=["sum"])).content.decode()
    problem.refresh_from_db()
    assert problem.title == "Yig‘indi"


def test_a_problem_written_in_english_is_translated_into_uzbek(client, problem):
    Problem.objects.filter(pk=problem.pk).update(source_lang="en", title="Sum", statement_md="Find the sum.")
    problem.refresh_from_db()
    assert service.other(problem.source_lang) == "uz"
    service.save_draft(problem, "statement_md", "uz", "Yig‘indini toping.", confirm=True)
    assert "Yig‘indini toping." in client.get(reverse("problems:detail", args=["sum"])).content.decode()  # the default page language is Uzbek
    assert "Find the sum." in _en(client).get(reverse("problems:detail", args=["sum"])).content.decode()


def test_editing_the_original_sends_the_translation_back_to_the_admins(client, problem):
    admin = User.objects.create_user("boss", password="x", is_staff=True)
    service.save_draft(problem, "statement_md", "en", "Find the sum.", confirm=True, user=admin)
    assert service.status(problem) == "draft"  # the title and the hint are still missing, so not "confirmed"
    service.stale(problem)
    assert not ContentTranslation.objects.filter(confirmed=True).exists()


class _FakeClient:
    """Stands in for anthropic.Anthropic: replies to a translation request with the same keys, text turned into 'EN: ...'."""

    def __init__(self):
        self.messages = self

    def stream(self, **kw):
        asked = json.loads(kw["messages"][0]["content"].split("\n\n", 1)[1])
        reply = json.dumps({k: "EN: " + v for k, v in asked.items()})
        message = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=reply)])

        class _Ctx:
            def __enter__(self_inner):
                return SimpleNamespace(get_final_message=lambda: message)

            def __exit__(self_inner, *a):
                return False
        return _Ctx()


def test_the_ai_writes_drafts_that_stay_closed_until_confirmed(problem):
    n = service.ai_translate(problem, client=_FakeClient())
    assert n == 3  # the title, the statement and the hint
    rows = ContentTranslation.objects.all()
    assert rows.count() == 3 and all(r.by_ai and not r.confirmed and r.lang == "en" for r in rows)
    assert service.status(problem) == "draft"
    assert rows.get(field="title").text == "EN: Yig‘indi"


def test_the_admin_pages_list_edit_and_confirm(client, problem):
    plain = User.objects.create_user("plain", password="x")
    client.force_login(plain)
    assert client.get(reverse("moderation:translations")).status_code == 403
    admin = User.objects.create_user("boss", password="x", is_staff=True)
    client.force_login(admin)
    r = client.get(reverse("moderation:translations") + "?kind=problems")
    assert r.status_code == 200 and "Yig‘indi" in r.content.decode()
    page = client.get(reverse("moderation:translation_edit", args=["problems", problem.pk]))
    assert page.status_code == 200 and "Ikki sonning" in page.content.decode()
    data = {"t0": "Sum", "t1": "Find the sum of two numbers.", "t2": "Add them.", "confirm": "1"}
    assert client.post(reverse("moderation:translation_edit", args=["problems", problem.pk]), data).status_code == 302
    assert service.status(problem) == "confirmed"
    assert ContentTranslation.objects.filter(confirmed=True, reviewed_by=admin).count() == 3
    # nothing to confirm in bulk now, and a bad kind is a 404
    assert client.post(reverse("moderation:translation_confirm_all", args=["problems"])).status_code == 302
    assert client.get(reverse("moderation:translations") + "?kind=nope").status_code == 404


def test_the_problem_form_asks_which_language_the_author_writes_in(client, db):
    setter = User.objects.create_user("setter", password="x", is_setter=True)
    client.force_login(setter)
    page = client.get(reverse("moderation:submit")).content.decode()
    assert 'name="source_lang"' in page
