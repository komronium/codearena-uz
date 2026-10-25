"""The production setup: English is the main language (the plain address, what a person who chose nothing sees) and
Uzbek lives under /uz/. The rest of the suite runs as an Uzbek-first site (config/settings/test.py); these tests turn
the real settings on."""
import gettext
from pathlib import Path

import pytest
from django.conf import settings as django_settings
from django.test import Client
from django.utils import translation

BASE = Path(django_settings.BASE_DIR)
HTML = {"HTTP_ACCEPT": "text/html"}


@pytest.fixture
def english_main(settings):
    settings.LANGUAGE_CODE = "en"
    settings.LANGUAGES = [("en", "English"), ("uz", "O‘zbekcha")]
    settings.LOCALE_PATHS = [BASE / "locale", BASE / "locale_uz"]


def test_nothing_chosen_is_english_and_uzbek_lives_under_uz(english_main):
    page = Client().get("/accounts/login/", **HTML)
    assert page.status_code == 200 and page["Content-Language"] == "en"
    assert '<html lang="en"' in page.content.decode()
    client = Client()
    uz = client.get("/uz/accounts/login/")
    assert uz.status_code == 200 and uz["Content-Language"] == "uz" and '<html lang="uz"' in uz.content.decode()
    assert client.cookies["ca_lang"].value == "uz"  # following the Uzbek link is a choice: plain links stay Uzbek
    assert client.get("/accounts/login/", **HTML)["Location"] == "/uz/accounts/login/"


def test_an_old_en_address_moves_to_the_plain_one(english_main, client):
    response = client.get("/en/problems/?page=2")
    assert response.status_code == 301 and response["Location"] == "/problems/?page=2"
    assert client.get("/en").status_code == 301 and client.get("/en")["Location"] == "/"


def test_the_switch_goes_to_the_same_page_in_the_other_language(english_main, client):
    for lang, nxt, where in (("uz", "/problems/?tag=math", "/uz/problems/?tag=math"), ("en", "/uz/problems/?tag=math", "/problems/?tag=math")):
        response = client.post("/i18n/language/", {"language": lang, "next": nxt})
        assert response.status_code == 302 and response["Location"] == where


def test_hreflang_names_english_as_the_default(english_main, client, db):
    html = client.get("/problems/").content.decode()
    for lang, href in (("en", "http://testserver/problems/"), ("uz", "http://testserver/uz/problems/"), ("x-default", "http://testserver/problems/")):
        assert f'<link rel="alternate" hreflang="{lang}" href="{href}">' in html


def test_robots_keeps_the_uzbek_copies_of_private_pages_out_too(english_main, client):
    robots = client.get("/robots.txt").content.decode()
    assert "Disallow: /moderation/" in robots and "Disallow: /uz/moderation/" in robots and "Disallow: /en/" not in robots


def test_every_english_line_has_an_uzbek_one(english_main):
    """A missing Uzbek line falls back to the English catalogue (the main language), so the Uzbek one lists every msgid."""
    en = gettext.GNUTranslations(open(BASE / "locale/en/LC_MESSAGES/django.mo", "rb"))
    uz = gettext.GNUTranslations(open(BASE / "locale_uz/uz/LC_MESSAGES/django.mo", "rb"))
    missing = [m for m in en._catalog if m and not isinstance(m, tuple) and m not in uz._catalog]
    assert not missing, missing[:10]


def test_the_uzbek_page_does_not_fall_back_to_english(english_main):
    with translation.override("uz"):
        assert translation.gettext("Yuborish") == "Yuborish"
    with translation.override("en"):
        assert translation.gettext("Yuborish") == "Send"


def test_places_and_the_error_option_read_in_the_page_language(english_main):
    from apps.accounts.templatetags.places import city_label, school_label
    from apps.classroom.templatetags.quiz import quiz_label, quiz_text
    with translation.override("en"):
        assert city_label("Toshkent") == "Tashkent" and city_label("Buxoro viloyati") == "Bukhara region"
        assert school_label("Samarqand davlat universiteti") == "Samarkand State University"
        assert city_label("Mening mahallam") == "Mening mahallam"  # a person's own text stays
        assert quiz_label("Xato") == "Error" and quiz_label("3") == "3"
        assert quiz_text("// butun bo‘lish: kasr qismi tashlanadi.") == "// is integer division: the fractional part is dropped."
    with translation.override("uz"):
        assert city_label("Toshkent") == "Toshkent" and quiz_label("Xato") == "Xato"


def test_a_typed_error_answer_is_right_in_either_language(db):
    from apps.classroom import duels
    from apps.classroom.models import DuelQuestion
    q = DuelQuestion(key="k", language="python", level="beginner", kind="output", code="print(1/0)", answer="Xato", options=[])
    assert duels.is_right(q, "Xato") and duels.is_right(q, "error") and duels.is_right(q, "Error") and not duels.is_right(q, "0")
