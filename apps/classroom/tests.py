from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Follow, User


# ---- duels ------------------------------------------------------------------------------------------

def _q(key, level="easy", language="python", **kw):
    from .models import DuelQuestion

    fields = {"kind": "output", "code": f"print({key!r})", "answer": key, "options": []}
    fields.update(kw)
    return DuelQuestion.objects.create(key=key, language=language, level=level, **fields)


@pytest.fixture
def bank(db):
    """Six Python questions: two answered from options, the rest typed."""
    qs = [_q(f"e{i}") for i in range(4)]
    qs.append(_q("pick", options=["a", "b", "c", "d"], answer="b"))
    qs.append(_q("list", answer="[1, 4]"))
    return qs


def _players():
    return User.objects.create_user("p1", password="x"), User.objects.create_user("p2", password="x")


def _age(duel, *, challenger=None, opponent=None, created=None):
    """Move a duel's clocks into the past, as if that much time had gone by."""
    from .models import Duel

    duel = Duel.objects.get(pk=duel.pk)
    fields = {}
    if challenger:
        fields.update(started_at=duel.started_at - challenger, ends_at=duel.ends_at - challenger)
    if opponent:
        fields.update(opponent_started_at=duel.opponent_started_at - opponent,
                      opponent_ends_at=duel.opponent_ends_at - opponent)
    if created:
        fields.update(created=duel.created - created)
    Duel.objects.filter(pk=duel.pk).update(**fields)
    return Duel.objects.get(pk=duel.pk)


def _play(duel, user, right: int, secs: float = 3):
    """Answer the whole run: the first `right` questions right, the rest wrong, each `secs` after it showed."""
    from .duels import answer, current
    from .models import Duel

    duel = Duel.objects.get(pk=duel.pk)  # as a request would load it
    for i in range(5):
        a = current(duel, user)
        q = a.question
        answer(duel, user, a.index, q.answer if i < right else "nope", now=a.shown_at + timezone.timedelta(seconds=secs))


@pytest.mark.django_db
def test_a_challenge_starts_the_challengers_run_and_accepting_starts_the_opponents(client, bank):
    from .models import Duel

    p1, p2 = _players()
    client.force_login(p1)
    url = reverse("classroom:duels")
    form = {"opponent": "p2", "language": "python"}
    assert client.post(url, {**form, "opponent": "p1"}).status_code == 200  # not yourself
    assert client.post(url, {**form, "opponent": "nobody"}).status_code == 200
    assert "Tilni tanlang" in client.post(url, {**form, "language": "cobol"}).content.decode()
    r = client.post(url, form)
    duel = Duel.objects.get()
    assert r.status_code == 302 and r.url == reverse("classroom:duel_play", args=[duel.pk])
    # nobody waits for anybody: the challenger's run starts at once, on five Python questions
    assert duel.status == "pending" and duel.mode == "quiz" and duel.language == "python"
    assert len(duel.questions) == 5 and len(set(duel.questions)) == 5 and duel.opponent_started_at is None
    assert client.post(url, form).status_code == 200  # one run at a time
    assert Duel.objects.count() == 1

    assert client.post(reverse("classroom:duel_answer", args=[duel.pk]), {"accept": "1"}).status_code == 404
    client.post(reverse("classroom:duel_answer", args=[duel.pk]))  # the challenger can't take it back
    assert Duel.objects.get().status == "pending"
    client.force_login(p2)
    page = client.get(reverse("classroom:duel", args=[duel.pk])).content.decode()
    assert "Qabul qilish" in page and "Savollar" not in page  # no peeking before playing
    r = client.post(reverse("classroom:duel_answer", args=[duel.pk]), {"accept": "1"})
    assert r.url == reverse("classroom:duel_play", args=[duel.pk])
    duel.refresh_from_db()
    assert duel.status == "active" and duel.opponent_started_at is not None

    page = client.get(reverse("classroom:duel", args=[duel.pk])).content.decode()
    assert 'hx-trigger="every 5s"' in page and "Boshlash" in page
    state = client.get(reverse("classroom:duel", args=[duel.pk])).context["state"]
    partial = client.get(reverse("classroom:duel", args=[duel.pk]), {"seen": state}, HTTP_HX_REQUEST="true")
    assert "<html" not in partial.content.decode()
    stale = client.get(reverse("classroom:duel", args=[duel.pk]), {"seen": "pending.0.False"}, HTTP_HX_REQUEST="true")
    assert stale.headers["HX-Refresh"] == "true"  # the page was drawn before p2 joined
    client.force_login(User.objects.create_user("spy", password="x"))
    assert client.get(reverse("classroom:duel", args=[duel.pk])).status_code == 404
    assert client.get(reverse("classroom:duel_play", args=[duel.pk])).status_code == 404


@pytest.mark.django_db
def test_a_friend_who_declines_gets_no_duel(bank):
    from .duels import challenge, decline

    p1, p2 = _players()
    duel, _ = challenge(p1, "p2", "python")
    decline(duel, p1)
    duel.refresh_from_db()
    assert duel.status == "pending"
    decline(duel, p2)
    duel.refresh_from_db()
    assert duel.status == "declined"


@pytest.mark.django_db
def test_quick_match_joins_the_closest_rated_open_duel_in_that_language(bank):
    from .duels import BUSY, _open, find_opponent, joinable_counts

    low, high = User.objects.create_user("low", password="x"), User.objects.create_user("high", password="x", duel_rating=1500)
    ids = [q.pk for q in bank[:5]]
    d_low = _open(low, "python", ids)
    d_high = _open(high, "python", ids)
    _open(User.objects.create_user("cpp", password="x", duel_rating=1450), "cpp", ids)
    near = User.objects.create_user("near", password="x", duel_rating=1450)
    assert joinable_counts(near) == {"python": 2, "cpp": 1}

    duel, error = find_opponent(near, "python")
    assert error == "" and duel.pk == d_high.pk  # 50 points apart, where low is 250
    duel.refresh_from_db()
    assert duel.opponent == near and duel.status == "active" and duel.opponent_started_at is not None
    duel, _ = find_opponent(User.objects.create_user("mid", password="x"), "python")
    assert duel.pk == d_low.pk

    # nobody left to join: the next player opens a duel of their own, run started
    late = User.objects.create_user("late", password="x")
    duel, _ = find_opponent(late, "python")
    assert duel.challenger == late and duel.opponent is None and duel.status == "pending"
    assert duel.started_at is not None
    assert find_opponent(late, "python") == (None, BUSY)
    assert find_opponent(late, "cobol")[1] == "Tilni tanlang."
    assert "yetarli emas" in find_opponent(User.objects.create_user("x", password="x"), "java")[1]


@pytest.mark.django_db
def test_new_questions_come_first_and_seen_ones_only_fill_up(bank):
    from .duels import _pick, find_opponent

    p1, _ = _players()
    duel, _ = find_opponent(p1, "python")
    _play(duel, p1, right=5)
    seen = set(duel.questions)
    picked = _pick([p1], "python")
    unseen = {q.pk for q in bank} - seen
    assert len(picked) == 5 and unseen <= set(picked)  # the one unseen question, then four seen ones


@pytest.mark.django_db
def test_each_question_has_its_own_20_seconds_and_a_reload_doesnt_reset_them(bank):
    from .duels import answer, current, find_opponent, is_right
    from .models import DuelAnswer

    p1, _ = _players()
    duel, _ = find_opponent(p1, "python")
    first = current(duel, p1)
    assert current(duel, p1).pk == first.pk  # shown again, same clock
    late = answer(duel, p1, 0, first.question.answer, now=first.shown_at + timezone.timedelta(seconds=23))
    assert late.correct is False  # right, but after 20 s and the 2 s grace
    assert answer(duel, p1, 0, "again").answer == first.question.answer  # the first answer stays
    second = current(duel, p1)
    assert second.index == 1
    # a question left open past its time is closed: the next one comes up
    DuelAnswer.objects.filter(pk=second.pk).update(shown_at=second.shown_at - timezone.timedelta(seconds=30))
    assert current(duel, p1).index == 2

    typed, pick = bank[5], bank[4]
    assert is_right(typed, " [1,4] ") and is_right(typed, "[1, 4]") and not is_right(typed, "") and not is_right(typed, "[1, 5]")
    assert is_right(pick, "b") and not is_right(pick, " b")


@pytest.mark.django_db
def test_more_right_answers_win_and_equal_is_a_draw_whatever_the_time(bank):
    from .duels import accept, challenge, settle
    from .models import Duel

    p1, p2 = _players()
    duel, _ = challenge(p1, "p2", "python")
    _play(duel, p1, right=3, secs=8)
    assert Duel.objects.get(pk=duel.pk).status == "pending"  # waiting for p2
    accept(duel, p2)
    _play(duel, p2, right=4, secs=4)  # one more right
    duel.refresh_from_db()
    p1.refresh_from_db()
    p2.refresh_from_db()
    assert duel.status == "finished" and duel.winner == p2
    assert (duel.challenger_delta, duel.opponent_delta) == (-20, 20)  # K 40 for both newcomers
    assert (p1.duel_rating, p2.duel_rating) == (1180, 1220)
    settle(Duel.objects.get(pk=duel.pk))  # settling again changes nothing
    p1.refresh_from_db()
    assert p1.duel_rating == 1180

    p3, p4 = User.objects.create_user("p3", password="x"), User.objects.create_user("p4", password="x")
    duel, _ = challenge(p3, "p4", "python")
    _play(duel, p3, right=3, secs=8)
    accept(duel, p4)
    _play(duel, p4, right=3, secs=1)  # as many right, and far faster: still a draw
    duel.refresh_from_db()
    assert duel.status == "finished" and duel.winner is None and duel.challenger_delta == duel.opponent_delta == 0

    from django.test import Client
    page = Client()
    page.force_login(p1)
    r = page.get(reverse("classroom:duels"))
    board = [u.username for u in r.context["board"]]
    assert board[0] == "p2" and board[-1] == "p1" and r.context["duel_rank"] == 4
    assert r.context["record"] == {"wins": 0, "losses": 1, "draws": 0}


@pytest.mark.django_db
def test_a_run_left_half_way_ends_after_five_minutes_and_an_open_duel_nobody_joins_expires(bank):
    from .duels import accept, challenge, find_opponent, settle
    from .models import Duel

    p1, p2 = _players()
    duel, _ = challenge(p1, "p2", "python")
    _play(duel, p1, right=2)
    accept(duel, p2)
    from .duels import answer, current
    duel = Duel.objects.get(pk=duel.pk)
    a = current(duel, p2)
    answer(duel, p2, 0, a.question.answer, now=a.shown_at + timezone.timedelta(seconds=2))  # then left the page
    settle(duel)
    assert Duel.objects.get(pk=duel.pk).status == "active"
    duel = _age(duel, opponent=timezone.timedelta(minutes=6))
    settle(duel)
    duel.refresh_from_db()
    assert duel.status == "finished" and duel.winner == p1  # 2 right beats 1; the four unseen count wrong

    lonely, _ = find_opponent(User.objects.create_user("lonely", password="x"), "python")
    lonely = _age(lonely, challenger=timezone.timedelta(days=4), created=timezone.timedelta(days=4))
    settle(lonely)
    assert Duel.objects.get(pk=lonely.pk).status == "expired"


def test_k_is_high_for_newcomers_and_low_at_the_top():
    from .duels import elo, k_factor

    assert k_factor(1200, 0) == k_factor(2300, 29) == 40
    assert k_factor(1999, 30) == 20 and k_factor(2000, 30) == 10
    assert elo(1200, 1200, 1.0, 40, 40) == (20, -20)
    assert elo(1200, 1200, 1.0, 40, 10) == (20, -5)  # each pays by their own K
    assert elo(1000, 1400, 0.5, 20, 20) == (8, -8)  # a draw lifts the lower one


@pytest.mark.django_db
def test_the_play_page_shows_one_question_never_its_answer_and_then_how_it_went(client, bank):
    from .duels import find_opponent

    p1, p2 = _players()
    duel, _ = find_opponent(p1, "python")
    client.force_login(p1)
    url = reverse("classroom:duel_play", args=[duel.pk])
    r = client.get(url)
    q = r.context["q"]
    page = r.content.decode()
    assert "data-nocopy" in page and "1-savol" in page and 'name="index" value="0"' in page
    if not q.options:
        assert f"<code>{q.answer}</code>" not in page
    r = client.post(url, {"index": "0", "answer": q.answer})
    assert r.url == url + "?after=0"
    page = client.get(r.url).content.decode()
    assert "To‘g‘ri!" in page and "Keyingi savol" in page
    assert client.get(url).context["n"] == 2  # the next question
    assert client.post(url, {"index": "x"}).status_code == 400

    for i in range(1, 5):
        a = client.get(url).context["a"]
        client.post(url, {"index": str(a.index), "answer": ""})
    assert client.get(url).url == reverse("classroom:duel", args=[duel.pk])  # run over: to the results
    page = client.get(reverse("classroom:duel", args=[duel.pk])).content.decode()
    assert "1/5" in page and "Savollar" in page and "hali o‘ynamadi" in page


@pytest.mark.django_db
def test_replay_works_the_ratings_out_again_keeping_every_result(db):
    from .duels import replay
    from .models import Duel

    a, b, c = (User.objects.create_user(n, password="x", duel_rating=999) for n in "abc")
    lonely = User.objects.create_user("lonely", password="x", duel_rating=1234)
    Duel.objects.create(challenger=a, opponent=b, status="finished", winner=a, mode="code")
    Duel.objects.create(challenger=b, opponent=c, status="finished", winner=None, mode="code")
    Duel.objects.create(challenger=a, opponent=c, status="expired", mode="code")
    replay(Duel.objects.all(), User.objects.all())
    ratings = dict(User.objects.values_list("username", "duel_rating"))
    # a beat b at 1200 each: ±20; then b (1180) drew with c (1200): the lower one gains a point
    assert (ratings["a"], ratings["b"], ratings["c"], ratings["lonely"]) == (1220, 1181, 1199, 1200)
    deltas = list(Duel.objects.order_by("pk").values_list("challenger_delta", "opponent_delta"))
    assert deltas[:2] == [(20, -20), (1, -1)] and deltas[2] == (None, None)


@pytest.mark.django_db
def test_recalc_duel_rating_command_rebuilds_deltas_and_ratings(bank):
    from io import StringIO

    from django.core.management import call_command

    from .duels import accept, challenge
    from .models import Duel

    p1, p2 = _players()
    duel, _ = challenge(p1, "p2", "python")
    _play(duel, p1, right=5, secs=2)  # p1 all five right
    accept(duel, p2)
    _play(duel, p2, right=1)
    # a corrupted history: a wrong delta and a hand-edited rating
    Duel.objects.filter(pk=duel.pk).update(challenger_delta=999, opponent_delta=-999)
    User.objects.filter(pk=p1.pk).update(duel_rating=7)

    out = StringIO()
    call_command("recalc_duel_rating", stdout=out)

    duel.refresh_from_db()
    p1.refresh_from_db()
    p2.refresh_from_db()
    assert (duel.challenger_delta, duel.opponent_delta) == (20, -20)  # both newcomers: K 40
    assert (p1.duel_rating, p2.duel_rating) == (1220, 1180)
    assert "Replayed 1 finished duels" in out.getvalue()


@pytest.mark.django_db
def test_recalc_duel_rating_command_rebuilds_a_past_season_podium():
    from io import StringIO

    from django.core.management import call_command

    from .duels import duel_season
    from .models import Duel, DuelSeasonResult

    p1, p2 = _players()
    ids = [Duel.objects.create(challenger=p1, opponent=p2, mode="quiz", language="python",
                               status="finished", winner=p1).pk for _ in range(3)]
    past = timezone.now() - timezone.timedelta(days=40)  # a finished month
    Duel.objects.filter(pk__in=ids).update(created=past, ends_at=past, opponent_ends_at=past)
    DuelSeasonResult.objects.all().delete()

    call_command("recalc_duel_rating", stdout=StringIO())

    season = duel_season(Duel.objects.first())
    rows = list(DuelSeasonResult.objects.filter(season=season).order_by("rank")
                .values_list("rank", "user_id", "duels"))
    assert rows == [(1, p1.pk, 3), (2, p2.pk, 3)]  # p1 won all three, so the higher rating


@pytest.mark.django_db
def test_a_finished_duel_records_when_it_ended(bank):
    from .duels import accept, challenge

    p1, p2 = _players()
    duel, _ = challenge(p1, "p2", "python")
    assert duel.finished_at is None and duel.ended_at == duel.created  # pending: it keeps its creation date
    _play(duel, p1, right=1)
    accept(duel, p2)
    _play(duel, p2, right=1)
    duel.refresh_from_db()
    assert duel.status == "finished" and duel.finished_at is not None
    assert duel.finished_at >= duel.created
    assert duel.ended_at == duel.finished_at  # a finished duel is shown under when it ended


@pytest.mark.django_db
def test_load_duel_questions_adds_updates_and_retires(db):
    from django.core.management import call_command

    from .models import DuelQuestion
    from .quiz_bank import entries

    _q("gone")
    call_command("load_duel_questions")
    n = sum(1 for _ in entries())
    assert DuelQuestion.objects.filter(is_active=True).count() == n
    assert DuelQuestion.objects.get(key="gone").is_active is False
    call_command("load_duel_questions")  # again: nothing changes
    assert DuelQuestion.objects.count() == n + 1


def test_every_bank_question_is_well_formed():
    from collections import Counter

    from .quiz_bank import BANK, entries
    from .quiz_check import BLANK

    keys = Counter(e["key"] for e in entries())
    assert max(keys.values()) == 1
    for e in entries():
        assert e["answer"] and (not e["options"] or e["answer"] in e["options"]), e["key"]
        assert len(set(e["options"])) == len(e["options"]), e["key"]
        assert (e["code"].count(BLANK) == 1) == (e["kind"] == "fill"), e["key"]
        assert e["kind"] == "output" or e["expect"], e["key"]
    assert all(len(qs) >= 10 for qs in BANK.values())


@pytest.mark.django_db
def test_seed_python_duels_command():
    from django.core.management import call_command
    from .models import DuelQuestion

    call_command("seed_python_duels")
    count = DuelQuestion.objects.filter(language="python", level__in=("beginner", "easy"), is_active=True).count()
    assert count >= 50



@pytest.mark.django_db
def test_duel_finder_offers_followed_and_rivals_then_searches_every_handle(client):
    from .models import Duel

    url = reverse("classroom:duel_people")
    assert client.get(url).status_code == 302  # signed-in users only
    ali, vali, sami = (User.objects.create_user(n, password="x") for n in ("ali", "vali", "sami"))
    Follow.objects.create(user=ali, target=vali)
    Follow.objects.create(user=ali, target=sami)
    client.force_login(ali)

    def found(q=""):
        return [(p["username"], p["followed"]) for p in client.get(url, {"q": q}).json()["results"]]

    assert found() == [("sami", True), ("vali", True)]  # the people you follow, never yourself
    Duel.objects.create(challenger=User.objects.create_user("bob", password="x"), opponent=ali)
    assert found() == [("bob", False), ("sami", True), ("vali", True)]  # and whoever you have duelled
    User.objects.create_user("valijon", password="x")
    User.objects.create_user("avali", password="x")
    User.objects.create_user("vali2", password="x", is_active=False)
    # the exact handle, then those starting with it, then the rest; never a blocked user or yourself
    assert [name for name, _ in found("VALI")] == ["vali", "valijon", "avali"]
    assert "ali" not in [name for name, _ in found("ali")]


@pytest.mark.django_db
def test_duel_stats_count_wins_runs_the_best_rating_and_perfect_quiz_runs(bank):
    from .duel_badges import duel_stats
    from .duels import accept, challenge
    from .models import Duel

    p1, p2 = _players()
    assert duel_stats(p1) == {"wins": 0, "win_run": 0, "duel_peak": 1200, "perfect": 0, "lightning": 0, "languages": 0}
    duel, _ = challenge(p1, "p2", "python")
    _play(duel, p1, right=5, secs=2)  # all five in 10 s
    accept(duel, p2)
    _play(duel, p2, right=1)
    assert duel_stats(p1) == {"wins": 1, "win_run": 1, "duel_peak": 1220, "perfect": 1, "lightning": 1, "languages": 1}
    for winner, delta in ((p1, 45), (p1, 45), (p2, -40)):
        Duel.objects.create(challenger=p1, opponent=p2, status="finished", winner=winner,
                            mode="code", challenger_delta=delta, opponent_delta=-delta)
    stats = duel_stats(p1)
    assert (stats["wins"], stats["win_run"], stats["duel_peak"]) == (3, 3, 1310)


@pytest.mark.django_db
def test_an_answer_gets_only_its_verdict_then_the_next_question(client, bank):
    from .duels import find_opponent

    p1, _ = _players()
    duel, _ = find_opponent(p1, "python")
    client.force_login(p1)
    url = reverse("classroom:duel_play", args=[duel.pk])
    q = client.get(url).context["q"]
    r = client.post(url, {"index": "0", "answer": q.answer}, HTTP_X_DUEL_ANSWER="1")
    assert r.json() == {"verdict": "ok", "next": url}  # never the right answer
    q = client.get(url).context["q"]
    assert client.post(url, {"index": "1", "answer": "nope"}, HTTP_X_DUEL_ANSWER="1").json()["verdict"] == "bad"
    client.get(url)
    assert client.post(url, {"index": "2", "answer": ""}, HTTP_X_DUEL_ANSWER="1").json()["verdict"] == "late"
    page = client.get(url + "?after=1").content.decode()  # the page without script: the verdict alone, then on
    card = page[page.index('<section class="ca-quiz-card'):page.index("</section>", page.index('<section class="ca-quiz-card'))]
    assert "Noto‘g‘ri" in card and 'http-equiv="refresh"' in page and f"<code>{q.answer}</code>" not in card
    assert "To‘g‘ri javob" not in card
    for i in (3, 4):
        client.get(url)
        last = client.post(url, {"index": str(i), "answer": "x"}, HTTP_X_DUEL_ANSWER="1").json()
    assert last["next"] == reverse("classroom:duel", args=[duel.pk])  # the run is over: to the results


@pytest.mark.django_db
def test_staff_see_every_duels_result_and_both_players_answers(client, bank):
    from .duels import accept, challenge

    p1, p2 = _players()
    duel, _ = challenge(p1, "p2", "python")
    _play(duel, p1, right=4)
    accept(duel, p2)
    _play(duel, p2, right=2)
    admin = User.objects.create_user("boss", password="x", is_staff=True)
    client.force_login(p1)
    assert client.get(reverse("moderation:duels")).status_code in (302, 403)
    client.force_login(admin)
    r = client.get(reverse("moderation:duels"))
    page = r.content.decode()
    d = r.context["page"][0]
    assert [(s["user"].username, s["right"], s["won"]) for s in d.sides] == [("p1", 4, True), ("p2", 2, False)]
    assert "4/5 to‘g‘ri" in page and "+20" in page and r.context["counts"]["finished"] == 1
    assert client.get(reverse("moderation:duels"), {"user": "nobody"}).context["page"].object_list == []
    review = client.get(reverse("classroom:duel", args=[duel.pk])).context["review"]
    assert len(review) == 5 and [s["label"] for s in review[0]["answers"]] == ["p1", "p2"]


@pytest.mark.django_db(transaction=True)
def test_telegram_tells_of_a_challenge_a_duel_result_and_a_badge(bank, settings, django_capture_on_commit_callbacks):
    from apps.accounts.models import TelegramLink, TelegramOutbox

    from .duels import accept, challenge

    settings.TELEGRAM_BOT_TOKEN = "x"
    settings.TELEGRAM_BOT_USERNAME = "codearena_bot"  # the bot counts as set up only with both
    p1, p2 = _players()
    for u in (p1, p2):
        TelegramLink.objects.create(user=u, chat_id=f"c{u.pk}")
    with patch("apps.accounts.telegram.dispatch_outbox"):
        with django_capture_on_commit_callbacks(execute=True):  # the notice goes out once the duel is committed
            duel, _ = challenge(p1, "p2", "python")
        invite = TelegramOutbox.objects.get(link__user=p2, event_key=f"duel:{duel.pk}:challenge")
        assert "p1" in invite.text and "Python" in invite.text
        _play(duel, p1, right=5, secs=2)
        accept(duel, p2)
        _play(duel, p2, right=1)
        results = {o.link.user.username: o.text for o in TelegramOutbox.objects.filter(event_key=f"duel:{duel.pk}:result")}
        assert "G‘alaba" in results["p1"] and "5 : 1" in results["p1"] and "Mag‘lubiyat" in results["p2"]
        badge = TelegramOutbox.objects.filter(link__user=p1, preference="notify_badges").first()
        assert badge is not None and "Mukammal I" in badge.text  # 5/5 in a duel
        link = TelegramLink.objects.get(user=p2)
        link.notify_duels = False
        link.save()
        with django_capture_on_commit_callbacks(execute=True):
            d2, _ = challenge(p1, "p2", "python")
        assert not TelegramOutbox.objects.filter(event_key=f"duel:{d2.pk}:challenge").exists()  # turned off


@pytest.mark.django_db
def test_duel_history_lists_the_latest_finish_first(client):
    from .models import Duel

    me, b = (User.objects.create_user(n, password="x") for n in ("me", "bob"))
    now = timezone.now()
    first = Duel.objects.create(challenger=me, opponent=b, status="finished", winner=me, mode="quiz",
                                finished_at=now - timezone.timedelta(hours=1))
    late_start = Duel.objects.create(challenger=me, opponent=b, status="finished", winner=b, mode="quiz",
                                     finished_at=now - timezone.timedelta(days=2))  # made last, ended first
    client.force_login(me)
    history = client.get(reverse("classroom:duels")).context["history"]
    assert [d.pk for d in history] == [first.pk, late_start.pk]


# ---- duel rules: levels, pairs, hidden answers, variants ---------------------------------------------

@pytest.mark.django_db
def test_a_duel_mixes_levels_by_rating_and_takes_the_least_asked_first():
    from collections import Counter

    from .duels import _pick
    from .models import DuelAnswer, DuelQuestion

    for level in ("beginner", "easy", "medium"):
        for i in range(6):
            _q(f"{level}{i}", level=level)
    p1, p2 = _players()  # both 1200: mostly easy ones, no medium

    def levels(ids):
        return Counter(DuelQuestion.objects.get(pk=i).level for i in ids)

    assert levels(_pick([p1, p2], "python")) == {"beginner": 2, "easy": 3}
    User.objects.filter(pk=p1.pk).update(duel_rating=900)
    User.objects.filter(pk=p2.pk).update(duel_rating=1000)
    assert levels(_pick([p1, p2], "python")) == {"beginner": 3, "easy": 2}
    User.objects.filter(pk__in=[p1.pk, p2.pk]).update(duel_rating=1700)  # only the strong get a medium
    assert levels(_pick([p1, p2], "python")) == {"beginner": 1, "easy": 3, "medium": 1}
    # a question asked many times to others waits behind the ones nobody was asked
    busy = DuelQuestion.objects.get(key="easy0")
    third = User.objects.create_user("p3", password="x")
    from .models import Duel
    d = Duel.objects.create(challenger=third, language="python", questions=[busy.pk], started_at=timezone.now())
    for i in range(3):
        DuelAnswer.objects.create(duel=d, user=third, index=i, question=busy, shown_at=timezone.now())
    for _ in range(20):
        assert busy.pk not in _pick([p1, p2], "python")


@pytest.mark.django_db
def test_a_pair_moves_full_elo_for_ten_duels_a_day_then_half_and_stops_at_twenty(bank):
    from .duels import pair_weight
    from .models import Duel

    p1, p2 = _players()
    made = [Duel.objects.create(challenger=p1, opponent=p2, mode="quiz", language="python", status="finished", winner=p1)
            for _ in range(12)]
    assert [pair_weight(d) for d in made] == [1] * 10 + [0.5] * 2
    other = User.objects.create_user("p3", password="x")
    fresh = Duel.objects.create(challenger=p1, opponent=other, mode="quiz", language="python", status="finished", winner=p1)
    assert pair_weight(fresh) == 1  # another opponent: full
    Duel.objects.filter(pk__in=[d.pk for d in made]).update(created=timezone.now() - timezone.timedelta(days=2))
    again = Duel.objects.create(challenger=p2, opponent=p1, mode="quiz", language="python", status="finished", winner=p2)
    assert pair_weight(again) == 1  # the day has passed


@pytest.mark.django_db
def test_questions_and_right_answers_open_only_when_both_runs_are_over(client, bank):
    from .duels import accept, challenge

    p1, p2 = _players()
    duel, _ = challenge(p1, "p2", "python")
    _play(duel, p1, right=4)
    client.force_login(p1)
    page = client.get(reverse("classroom:duel", args=[duel.pk]))
    assert page.context["review"] == [] and page.context["review_waits"]  # p2 hasn't played: nothing to pass on
    assert "raqibingiz ham tugatgach" in page.content.decode()
    accept(duel, p2)
    _play(duel, p2, right=2)
    page = client.get(reverse("classroom:duel", args=[duel.pk]))
    assert len(page.context["review"]) == 5 and not page.context["review_waits"]


def test_variants_nudge_numbers_outside_strings_and_work_the_answer_out():
    import random

    from .quiz_variants import mutate, options_for, variants_of

    rng = random.Random(3)
    code = 'print("7 // 2")\nprint(7 // 2)'
    new = mutate(code, rng)
    assert new.splitlines()[0] == 'print("7 // 2")' and new != code  # the string stays as it was
    assert mutate("print('x')", rng) == "print('x')"  # nothing to nudge

    def run(language, source):  # a stand-in for the sandbox: evaluate the one expression
        try:
            return True, str(eval(source.strip().removeprefix("print(").removesuffix(")"))) + "\n"
        except Exception:
            return False, ""

    entry = {"kind": "output", "language": "python", "level": "easy", "code": "print(7 // 2)", "answer": "3",
             "options": ["3", "4", "2", "5"], "full": False, "key": "python-abc", "accept": [], "explain": "", "expect": ""}
    made = list(variants_of(entry, run, 5, rng))
    assert made and all(v["origin"] == "python-abc" and v["code"] != entry["code"] and v["answer"] != "3" for v in made)
    assert all(v["answer"] == str(eval(v["code"][6:-1])) for v in made)
    for v in made:
        assert len(set(v["options"])) == 4 and v["answer"] in v["options"]
    assert options_for("hello", ["a", "b"], rng) == []  # a word answer is typed
    assert options_for("True", ["True", "False", "None"], rng) == ["True", "False", "None"]
    assert list(variants_of({**entry, "answer": "Xato"}, run, 5, rng)) == []  # an error answer is not varied
    word = {**entry, "code": 'print("ab" + "c" * 2)', "answer": "abcc", "options": ["abcc", "abc", "ab", "cc"]}
    assert list(variants_of(word, lambda lang, src: (True, "abcd\n"), 5, rng)) == []  # a pick never becomes a typed question


@pytest.mark.django_db
def test_a_full_day_of_duels_with_one_person_blocks_sending_accepting_and_matching(bank):
    from .duels import PAIR_FULL, PAIR_LIMIT, _open, accept, challenge, find_opponent, full_pairs, joinable_counts
    from .models import Duel

    p1, p2 = _players()
    for _ in range(PAIR_LIMIT):
        Duel.objects.create(challenger=p1, opponent=p2, mode="quiz", language="python", status="finished", winner=p1)
    assert full_pairs(p1.pk) == {p2.pk} and full_pairs(p2.pk) == {p1.pk}
    assert challenge(p1, "p2", "python") == (None, PAIR_FULL)  # can't be sent
    # an invitation made before the day filled up can't be accepted either
    p3 = User.objects.create_user("p3", password="x")
    old = Duel.objects.create(challenger=p3, opponent=p1, mode="quiz", language="python", questions=[1, 2, 3, 4, 5],
                              started_at=timezone.now(), ends_at=timezone.now() + timezone.timedelta(minutes=5))
    for _ in range(PAIR_LIMIT):
        Duel.objects.create(challenger=p1, opponent=p3, mode="quiz", language="python", status="finished", winner=p1)
    Duel.objects.filter(pk=old.pk).update(created=timezone.now() - timezone.timedelta(minutes=1))
    assert accept(old, p1) == PAIR_FULL
    # automatic matching leaves out an owner whose pair with you is full
    fresh = User.objects.create_user("p4", password="x")
    _open(p2, "python", [e.pk for e in bank[:5]])
    assert joinable_counts(p1) == {}  # p2's open duel isn't offered to p1 ...
    duel, _ = find_opponent(p1, "python")
    assert duel is not None and duel.opponent_id is None and duel.challenger_id == p1.pk  # ... p1 opens their own
    assert joinable_counts(fresh) == {"python": 2}  # while anyone else still sees both


def test_duels_ask_only_about_io_if_loops_lists_and_strings():
    from .quiz_bank import entries, friendly

    assert friendly("python", "print(7 // 2)", "3", [])
    assert friendly("python", "a = [3, 1, 2]\na.sort()\nprint(a[0])", "1", [])
    assert friendly("python", 'for c in "abc":\n    print(c)', "a b c", [])
    assert not friendly("python", "def f(x):\n    return x\nprint(f(1))", "1", [])  # functions
    assert not friendly("python", "print(type(5))", "<class 'int'>", ["<class 'int'>", "x"])  # type checks
    assert not friendly("python", 'd = {"a": 1}\nprint(d["a"])', "1", [])  # dicts
    assert not friendly("python", "print([n * 2 for n in range(3)])", "[0, 2, 4]", ["[0, 2, 4]", "x"])  # comprehensions
    assert not friendly("python", "a = [1, 2]\nprint(a)", "[1, 2]", [])  # a typed list: everyone writes it differently
    assert friendly("python", "a = [1, 2]\nprint(a)", "[1, 2]", ["[1, 2]", "[2, 1]"])  # but a pick is fine
    assert not friendly("js", "console.log([1, 2].map(x => x * 2))", "[2, 4]", ["[2, 4]"])
    assert not friendly("java", "static int f() { return 1; }", "1", [])
    for e in entries():  # nothing in the bank breaks the rule
        assert friendly(e["language"], e["code"], e["answer"], e["options"]), e["key"]


def test_a_variant_with_a_long_decimal_or_a_new_zero_is_not_worth_asking():
    from .quiz_variants import acceptable

    assert acceptable("print(9 // 2)", "4", "print(7 // 2)")
    assert not acceptable("print(12 / 7)", "1.7142857142857142", "print(7 / 2)")
    assert acceptable("print(7 / 4)", "1.75", "print(7 / 2)")
    assert not acceptable("print(10 - 0 * 3)", "10", "print(10 - 2 * 3)")  # a 0 that was not there
    assert acceptable("print(0 + 5)", "5", "print(0 + 3)")  # one the original had
