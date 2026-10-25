from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.accounts.models import User
from apps.contests.models import Contest, ContestProblem, Participation
from apps.problems.models import Language, Problem
from apps.submissions.models import Submission


@pytest.fixture
def python(db):
    return Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")


@pytest.fixture
def teacher(db):
    return User.objects.create_user("teacher", password="x", email="teacher@example.com")


@pytest.fixture
def problems(teacher):
    return [Problem.objects.create(slug=s, title=s.upper(), statement_md="x", author=teacher, is_public=False)
            for s in ("a", "b")]


def _contest(problems, start_hours, length_hours=2, **fields):
    now = timezone.now()
    c = Contest.objects.create(start=now + timedelta(hours=start_hours), end=now + timedelta(hours=start_hours + length_hours),
                               **fields)
    for i, p in enumerate(problems):
        ContestProblem.objects.create(contest=c, problem=p, label="AB"[i], order=i, points=100)
    return c


@pytest.fixture
def past(problems, python, teacher):
    c = _contest(problems, -5, kind="round", number=1, type="icpc", is_rated=True)
    c.authors.add(teacher)
    for rank, (name, solved) in enumerate([("ali", 2), ("vali", 1), ("sami", 0)], start=1):
        user = User.objects.create_user(name, password="x", email=f"{name}@example.com", first_name=name.title(),
                                        country="UZ")
        User.objects.filter(pk=user.pk).update(rating=100 - 30 * rank)
        Participation.objects.create(user=user, contest=c, rank=rank, rating_before=0, rating_after=100 - 30 * rank)
        for i, p in enumerate(problems[:solved]):
            s = Submission.objects.create(user=user, problem=p, contest=c, language=python, source="SECRET CODE",
                                          verdict="AC", passed=1)
            s.created = c.start + timedelta(minutes=10 * (i + 1))
            s.save(update_fields=["created"])
    return c


def test_every_response_is_json_open_to_any_origin_and_cacheable(client, past):
    r = client.get("/api/v1/contests/")
    assert r.status_code == 200 and r["Access-Control-Allow-Origin"] == "*"
    assert r["Content-Type"].startswith("application/json") and "max-age" in r["Cache-Control"]


def test_only_get_is_allowed(client, past):
    assert client.post("/api/v1/contests/").status_code == 405


def test_contest_list_pages_like_samcoding_and_ends_empty_past_the_last_page(client, past, problems):
    _contest(problems, 24, kind="round", number=2)
    first = client.get("/api/v1/contests/?page_size=1").json()
    assert (first["page"], first["pagesCount"], first["count"]) == (1, 2, 2)
    item = first["data"][0]
    assert {"id", "title", "url", "start_time", "end_time", "duration_minutes", "status"} <= set(item)
    assert item["start_time"].endswith("Z") and item["duration_minutes"] == 120
    beyond = client.get("/api/v1/contests/?page_size=1&page=9").json()
    assert beyond["page"] == 9 and beyond["data"] == []


def test_contest_list_filters_by_status(client, past, problems):
    _contest(problems, 24, kind="round", number=2)
    assert [c["status"] for c in client.get("/api/v1/contests/?status=upcoming").json()["data"]] == ["upcoming"]
    assert [c["status"] for c in client.get("/api/v1/contests/?status=past").json()["data"]] == ["past"]


def test_drafts_do_not_exist_for_the_api(client, problems):
    draft = _contest(problems, 24, kind="round", number=3, is_draft=True)
    assert client.get("/api/v1/contests/").json()["count"] == 0
    r = client.get(f"/api/v1/contests/{draft.pk}/")
    assert r.status_code == 404 and r.json()["status"] == "error"


def test_an_upcoming_round_keeps_its_problems_secret(client, problems):
    up = _contest(problems, 24, kind="round", number=2)
    body = client.get(f"/api/v1/contests/{up.pk}/").json()["contest"]
    assert body["problems_hidden"] and body["problems"] == [] and body["n_problems"] == 2
    board = client.get(f"/api/v1/contests/{up.pk}/clist-standings/").json()
    assert board["problems"] == [] and board["standings"] == []


def test_a_finished_round_lists_its_problems(client, past):
    body = client.get(f"/api/v1/contests/{past.pk}/").json()["contest"]
    assert [p["label"] for p in body["problems"]] == ["A", "B"]


def test_standings_rows_carry_place_score_penalty_and_cells(client, past):
    rows = client.get(f"/api/v1/contests/{past.pk}/standings/").json()["data"]
    assert [(r["member"], r["place"], r["solved"]) for r in rows] == [("ali", 1, 2), ("vali", 2, 1), ("sami", 3, 0)]
    assert rows[0]["rating_change"] == 70 and rows[0]["problems"]["A"]["time"] == "00:10"
    assert rows[2]["problems"] == {}


def test_clist_standings_follow_the_parser_contract(client, past):
    body = client.get(f"/api/v1/contests/{past.pk}/clist-standings/").json()
    assert body["status"] == "ok" and body["rules"] == "icpc"
    assert [p["short"] for p in body["problems"]] == ["A", "B"]
    top = body["standings"][0]
    assert (top["member"], top["place"], top["solving"], top["penalty"]) == ("ali", 1, 2, 30)
    assert top["problems"]["A"] == {"result": "+", "time": "00:10", "first_ac": True}


def test_authors_and_the_disqualified_have_no_place(client, past, teacher, python):
    Participation.objects.create(user=teacher, contest=past)
    Participation.objects.filter(user__username="sami").update(disqualified=True)
    cache.clear()
    places = {r["member"]: r["place"] for r in client.get(f"/api/v1/contests/{past.pk}/standings/").json()["data"]}
    assert places["teacher"] is None and places["sami"] is None and places["ali"] == 1


def test_a_running_personal_clock_round_shuts_problems_and_board(client, problems):
    marathon = _contest(problems, -1, length_hours=30, kind="marathon", number=1, personal_minutes=120)
    body = client.get(f"/api/v1/contests/{marathon.pk}/").json()["contest"]
    assert body["problems_hidden"] and body["problems"] == []
    board = client.get(f"/api/v1/contests/{marathon.pk}/standings/").json()
    assert board["hidden"] and board["data"] == []


def test_nothing_private_leaks(client, past):
    text = "".join(client.get(url).content.decode() for url in (
        "/api/v1/users/", "/api/v1/users/ali/", f"/api/v1/contests/{past.pk}/standings/",
        f"/api/v1/contests/{past.pk}/clist-standings/"))
    assert "example.com" not in text and "SECRET CODE" not in text


def test_users_are_the_rating_board_with_ranks(client, past):
    users = client.get("/api/v1/users/").json()["data"]
    assert [(u["username"], u["rank"]) for u in users] == [("ali", 1), ("vali", 2), ("sami", 3)]
    one = client.get("/api/v1/users/vali/").json()["user"]
    assert one["rank"] == 2 and one["max_rating"] == 40 and one["country"] == "UZ"


def test_a_user_off_the_board_has_a_profile_but_no_rank(client, past):
    Participation.objects.filter(user__username="ali").update(
        rating_after=None, rating_before=None)
    body = client.get("/api/v1/users/ali/").json()["user"]
    assert body["on_board"] is False and body["rank"] is None


def test_rating_history_lists_rated_contests(client, past):
    data = client.get("/api/v1/users/ali/ratings/").json()["data"]
    assert [(d["contest_id"], d["place"], d["rating_after"], d["rating_change"]) for d in data] == [(past.pk, 1, 70, 70)]


def test_unknown_user_is_a_json_404(client, db):
    r = client.get("/api/v1/users/nobody/")
    assert r.status_code == 404 and r.json() == {"status": "error", "error": "not found"}


def test_problems_hide_private_ones_and_those_of_unstarted_rounds(client, teacher, problems):
    open_one = Problem.objects.create(slug="open", title="Open", statement_md="Hi", author=teacher, is_public=True)
    held = Problem.objects.create(slug="held", title="Held", statement_md="Secret", author=teacher, is_public=True)
    _contest([held], 24, kind="round", number=4)
    assert [p["slug"] for p in client.get("/api/v1/problems/").json()["data"]] == ["open"]
    assert client.get("/api/v1/problems/held/").status_code == 404
    assert client.get("/api/v1/problems/a/").status_code == 404  # not public
    assert client.get("/api/v1/problems/open/").json()["problem"]["statement_md"] == "Hi"
    assert open_one.slug == "open"


def test_the_api_is_rate_limited_per_address(client, db):
    for _ in range(120):
        assert client.get("/api/v1/").status_code == 200
    r = client.get("/api/v1/")
    assert r.status_code == 429 and r["Retry-After"] == "60"


def test_meta_lists_tiers_and_divisions(client, db):
    body = client.get("/api/v1/meta/").json()
    assert body["tiers"][0]["name"] == "Newbie" and body["divisions"][0]["number"] == 1
