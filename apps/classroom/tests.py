from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Group, User
from apps.problems.models import Language, Problem
from apps.submissions.models import Submission

from .models import Assignment, AssignmentProblem


@pytest.fixture
def teacher(db):
    return User.objects.create_user("teacher", password="x", role="teacher")


@pytest.fixture
def klass(teacher):
    g = Group.objects.create(name="201-guruh", teacher=teacher)
    for name in ("ali", "vali", "sami"):
        g.members.add(User.objects.create_user(name, password="x"))
    return g


@pytest.fixture
def python(db):
    return Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")


def _problem(slug, author, **kw):
    return Problem.objects.create(slug=slug, title=slug.upper(), statement_md="x", author=author, **kw)


def _sub(user, problem, lang, verdict, at):
    s = Submission.objects.create(user=user, problem=problem, language=lang, source="x", verdict=verdict)
    Submission.objects.filter(pk=s.pk).update(created=at)


def _assignment(klass, teacher, problems, deadline):
    a = Assignment.objects.create(group=klass, title="1-uy vazifa", created_by=teacher,
                                  start=deadline - timezone.timedelta(days=7), deadline=deadline)
    for i, p in enumerate(problems):
        AssignmentProblem.objects.create(assignment=a, problem=p, order=i)
    return a


@pytest.mark.django_db
def test_teacher_creates_an_assignment_for_own_group_only(client, teacher, klass):
    _problem("p1", teacher), _problem("p2", teacher)
    hidden = _problem("secret", teacher, is_public=False)
    other = Group.objects.create(name="Boshqa", teacher=User.objects.create_user("t2", password="x"))
    client.force_login(teacher)
    data = {"group": klass.pk, "title": "1-uy vazifa", "description_md": "", "start": "2030-01-01T09:00",
            "deadline": "2030-01-08T23:59", "problems": "p2, p1"}
    assert client.post(reverse("classroom:new"), data | {"group": other.pk}).status_code == 200
    assert client.post(reverse("classroom:new"), data | {"problems": "p1, secret"}).status_code == 200
    assert client.post(reverse("classroom:new"), data | {"deadline": "2029-12-31T00:00"}).status_code == 200
    r = client.post(reverse("classroom:new"), data)
    a = Assignment.objects.get()
    assert r.status_code == 302 and a.group == klass
    assert [ap.problem.slug for ap in a.assignment_problems.all()] == ["p2", "p1"]
    assert hidden.pk not in a.assignment_problems.values_list("problem_id", flat=True)

    r = client.post(reverse("classroom:edit", args=[a.pk]), data | {"problems": "p1", "title": "Yangi"})
    a.refresh_from_db()
    assert a.title == "Yangi" and [ap.problem.slug for ap in a.assignment_problems.all()] == ["p1"]

    client.force_login(User.objects.get(username="ali"))  # a student can't manage
    assert client.get(reverse("classroom:new")).status_code == 403
    assert client.get(reverse("classroom:edit", args=[a.pk])).status_code == 403


@pytest.mark.django_db
def test_the_problem_picker_offers_exactly_what_the_form_accepts(client, teacher, klass):
    from apps.contests.models import Contest, ContestProblem

    _problem("open", teacher)
    _problem("secret", teacher, is_public=False)
    _problem("queued", teacher, status=Problem.Status.PENDING)
    soon = _problem("soon", teacher)
    c = Contest.objects.create(title="Soon", start=timezone.now() + timezone.timedelta(days=1),
                               end=timezone.now() + timezone.timedelta(days=1, hours=2))
    ContestProblem.objects.create(contest=c, problem=soon, label="A")
    client.force_login(teacher)
    r = client.get(reverse("classroom:new"))
    assert [p["slug"] for p in r.context["form"].picker_problems()] == ["open"]
    assert 'id="picker-data"' in r.content.decode()
    data = {"group": klass.pk, "title": "T", "description_md": "", "start": "2030-01-01T09:00",
            "deadline": "2030-01-08T23:59"}
    for slug in ("secret", "queued", "soon"):  # what the picker leaves out, the form refuses
        assert client.post(reverse("classroom:new"), data | {"problems": slug}).status_code == 200
    assert not Assignment.objects.exists()


@pytest.mark.django_db
def test_progress_grid_and_csv(client, teacher, klass, python):
    p1, p2 = _problem("p1", teacher), _problem("p2", teacher)
    deadline = timezone.now() - timezone.timedelta(hours=1)
    a = _assignment(klass, teacher, [p1, p2], deadline)
    ali, vali = User.objects.get(username="ali"), User.objects.get(username="vali")
    _sub(ali, p1, python, "WA", deadline - timezone.timedelta(hours=3))
    _sub(ali, p1, python, "AC", deadline - timezone.timedelta(hours=2))  # on time, 1 try before
    _sub(ali, p2, python, "AC", deadline + timezone.timedelta(minutes=30))  # late
    _sub(vali, p1, python, "WA", deadline - timezone.timedelta(hours=2))
    _sub(vali, p1, python, "CE", deadline - timezone.timedelta(hours=2))  # CE is not a try

    client.force_login(teacher)
    r = client.get(reverse("classroom:detail", args=[a.pk]))
    rows = {row["user"].username: row for row in r.context["grid"]}
    assert [c["status"] for c in rows["ali"]["cells"]] == ["ok", "late"]
    assert rows["ali"]["cells"][0]["tries"] == 1 and rows["ali"]["on_time"] == 1 and rows["ali"]["solved"] == 2
    assert [c["status"] for c in rows["vali"]["cells"]] == ["tried", "none"] and rows["vali"]["cells"][0]["tries"] == 1
    assert [c["status"] for c in rows["sami"]["cells"]] == ["none", "none"]
    assert list(rows) == ["ali", "vali", "sami"]  # most on-time solves first

    csv = client.get(reverse("classroom:detail", args=[a.pk]) + "?format=csv")
    assert csv["Content-Type"].startswith("text/csv")
    lines = csv.content.decode("utf-8-sig").splitlines()
    assert lines[0] == "Foydalanuvchi,Ism,P1,P2,O‘z vaqtida,Jami"
    assert lines[1].startswith("ali,,ok,kech,1,2")


@pytest.mark.django_db
def test_students_see_their_groups_assignments_only(client, teacher, klass, python):
    p1 = _problem("p1", teacher)
    a = _assignment(klass, teacher, [p1], timezone.now() + timezone.timedelta(days=2))
    stranger = User.objects.create_user("begona", password="x")
    ali = User.objects.get(username="ali")
    _sub(ali, p1, python, "AC", timezone.now())

    client.force_login(ali)
    r = client.get(reverse("classroom:list"))
    assert [x.pk for x in r.context["assignments"]] == [a.pk] and r.context["assignments"][0].my_solved == 1
    r = client.get(reverse("classroom:detail", args=[a.pk]))
    assert r.status_code == 200 and "grid" not in r.context and r.context["mine"][0]["status"] == "ok"

    client.force_login(stranger)
    assert list(client.get(reverse("classroom:list")).context["assignments"]) == []
    assert client.get(reverse("classroom:detail", args=[a.pk])).status_code == 404



def test_assignment_description_is_rendered_markdown_and_sanitized(client, teacher, klass):
    a = _assignment(klass, teacher, [_problem("p1", teacher)], timezone.now() + timezone.timedelta(days=2))
    Assignment.objects.filter(pk=a.pk).update(description_md="**Juma kuni** yeching <script>alert(1)</script>")
    client.force_login(User.objects.get(username="ali"))
    page = client.get(reverse("classroom:detail", args=[a.pk])).content.decode()
    assert "<strong>Juma kuni</strong>" in page and "**Juma" not in page
    assert "<script>alert(1)</script>" not in page

# ---- code review ---------------------------------------------------------------------------------

@pytest.fixture
def ali_sub(klass, python, teacher):
    ali = User.objects.get(username="ali")
    p = _problem("p1", teacher)
    return Submission.objects.create(user=ali, problem=p, language=python, verdict="WA",
                                     source="n = int(input())\nprint(n + 1)\nprint(n)\n")


@pytest.mark.django_db
def test_group_teacher_reviews_a_students_code(client, teacher, ali_sub):
    from .models import ReviewComment

    url = reverse("classroom:review", args=[ali_sub.pk])
    client.force_login(teacher)
    assert client.get(reverse("submissions:detail", args=[ali_sub.pk])).status_code == 200
    assert client.post(url, {"line": "9", "body": "yo‘q qator"}).status_code == 400
    assert client.post(url, {"line": "2", "body": "n + 1 emas, n * 2 kerak"}).status_code == 302
    assert client.post(url, {"line": "", "body": "Umumiy: yaxshi boshlanish"}).status_code == 302

    ali = ali_sub.user
    client.force_login(ali)
    assert client.get(reverse("problems:list")).context["unread_reviews"] == 2
    page = client.get(reverse("submissions:detail", args=[ali_sub.pk])).content.decode()
    assert "n + 1 emas, n * 2 kerak" in page and "2-qator" in page and "print(n + 1)" in page
    assert client.get(reverse("problems:list")).context["unread_reviews"] == 0  # opening marked them read
    assert client.post(url, {"body": "Tushundim, rahmat"}).status_code == 302  # the student can reply
    assert list(ReviewComment.objects.values_list("author__username", "line")) == [
        ("teacher", 2), ("teacher", None), ("ali", None)]
    client.force_login(teacher)
    assert client.get(reverse("problems:list")).context["unread_reviews"] == 0  # replies don't badge staff


@pytest.mark.django_db
def test_only_the_students_teachers_and_staff_can_review(client, ali_sub):
    other = User.objects.create_user("t2", password="x")
    Group.objects.create(name="Boshqa", teacher=other)  # teaches, but not ali
    client.force_login(other)
    assert client.get(reverse("submissions:detail", args=[ali_sub.pk])).status_code == 404
    assert client.post(reverse("classroom:review", args=[ali_sub.pk]), {"body": "x"}).status_code == 404
    client.force_login(User.objects.create_user("boss", password="x", is_staff=True))
    assert client.post(reverse("classroom:review", args=[ali_sub.pk]), {"body": "ok"}).status_code == 302


# ---- duels ------------------------------------------------------------------------------------------

def _q(key, level="easy", language="python", **kw):
    from .models import DuelQuestion

    fields = {"kind": "output", "code": f"print({key!r})", "answer": key, "options": []}
    fields.update(kw)
    return DuelQuestion.objects.create(key=key, language=language, level=level, **fields)


@pytest.fixture
def bank(db):
    """Six easy Python questions (two picked from options, the rest typed) and five medium ones."""
    qs = [_q(f"e{i}") for i in range(4)]
    qs.append(_q("pick", options=["a", "b", "c", "d"], answer="b"))
    qs.append(_q("list", answer="[1, 4]"))
    for i in range(5):
        _q(f"m{i}", level="medium")
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
    form = {"opponent": "p2", "language": "python", "difficulty": "easy"}
    assert client.post(url, {**form, "opponent": "p1"}).status_code == 200  # not yourself
    assert client.post(url, {**form, "opponent": "nobody"}).status_code == 200
    assert "Tilni tanlang" in client.post(url, {**form, "language": "cobol"}).content.decode()
    r = client.post(url, form)
    duel = Duel.objects.get()
    assert r.status_code == 302 and r.url == reverse("classroom:duel_play", args=[duel.pk])
    # nobody waits for anybody: the challenger's run starts at once, on five easy Python questions
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
    duel, _ = challenge(p1, "p2", "python", "easy")
    decline(duel, p1)
    duel.refresh_from_db()
    assert duel.status == "pending"
    decline(duel, p2)
    duel.refresh_from_db()
    assert duel.status == "declined"


@pytest.mark.django_db
def test_quick_match_joins_the_closest_rated_open_duel_in_that_language_and_level(bank):
    from .duels import BUSY, _open, find_opponent, joinable_counts

    low, high = User.objects.create_user("low", password="x"), User.objects.create_user("high", password="x", duel_rating=1500)
    ids = [q.pk for q in bank[:5]]
    d_low = _open(low, "python", "easy", ids)
    d_high = _open(high, "python", "easy", ids)
    _open(User.objects.create_user("cpp", password="x", duel_rating=1450), "cpp", "easy", ids)
    near = User.objects.create_user("near", password="x", duel_rating=1450)
    assert joinable_counts(near) == {"python:easy": 2, "cpp:easy": 1}

    duel, error = find_opponent(near, "python", "easy")
    assert error == "" and duel.pk == d_high.pk  # 50 points apart, where low is 250
    duel.refresh_from_db()
    assert duel.opponent == near and duel.status == "active" and duel.opponent_started_at is not None
    duel, _ = find_opponent(User.objects.create_user("mid", password="x"), "python", "easy")
    assert duel.pk == d_low.pk

    # nobody left to join: the next player opens a duel of their own, run started
    late = User.objects.create_user("late", password="x")
    duel, _ = find_opponent(late, "python", "medium")
    assert duel.challenger == late and duel.opponent is None and duel.status == "pending"
    assert duel.difficulty == "medium" and duel.started_at is not None
    assert find_opponent(late, "python", "easy") == (None, BUSY)
    assert find_opponent(late, "python", "hard")[1] == "Darajani tanlang."
    assert "yetarli emas" in find_opponent(User.objects.create_user("x", password="x"), "java", "easy")[1]


@pytest.mark.django_db
def test_new_questions_come_first_and_seen_ones_only_fill_up(bank):
    from .duels import _pick, find_opponent

    p1, _ = _players()
    duel, _ = find_opponent(p1, "python", "easy")
    _play(duel, p1, right=5)
    seen = set(duel.questions)
    picked = _pick([p1], "python", "easy")
    unseen = {q.pk for q in bank} - seen
    assert len(picked) == 5 and unseen <= set(picked)  # the one unseen question, then four seen ones


@pytest.mark.django_db
def test_each_question_has_its_own_20_seconds_and_a_reload_doesnt_reset_them(bank):
    from .duels import answer, current, find_opponent, is_right
    from .models import DuelAnswer

    p1, _ = _players()
    duel, _ = find_opponent(p1, "python", "easy")
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
def test_more_right_answers_win_then_less_time_and_none_right_is_a_draw(bank):
    from .duels import accept, challenge, settle
    from .models import Duel

    p1, p2 = _players()
    duel, _ = challenge(p1, "p2", "python", "easy")
    _play(duel, p1, right=3, secs=8)
    assert Duel.objects.get(pk=duel.pk).status == "pending"  # waiting for p2
    accept(duel, p2)
    _play(duel, p2, right=3, secs=4)  # as many right, and faster
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
    duel, _ = challenge(p3, "p4", "python", "medium")
    _play(duel, p3, right=0)
    accept(duel, p4)
    _play(duel, p4, right=0, secs=1)
    duel.refresh_from_db()
    assert duel.status == "finished" and duel.winner is None  # nobody right: speed doesn't matter

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
    duel, _ = challenge(p1, "p2", "python", "easy")
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

    lonely, _ = find_opponent(User.objects.create_user("lonely", password="x"), "python", "easy")
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
    duel, _ = find_opponent(p1, "python", "easy")
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
    Duel.objects.create(challenger=a, opponent=b, difficulty="easy", status="finished", winner=a, mode="code")
    Duel.objects.create(challenger=b, opponent=c, difficulty="easy", status="finished", winner=None, mode="code")
    Duel.objects.create(challenger=a, opponent=c, difficulty="easy", status="expired", mode="code")
    replay(Duel.objects.all(), User.objects.all())
    ratings = dict(User.objects.values_list("username", "duel_rating"))
    # a beat b at 1200 each: ±20; then b (1180) drew with c (1200): the lower one gains a point
    assert (ratings["a"], ratings["b"], ratings["c"], ratings["lonely"]) == (1220, 1181, 1199, 1200)
    deltas = list(Duel.objects.order_by("pk").values_list("challenger_delta", "opponent_delta"))
    assert deltas[:2] == [(20, -20), (1, -1)] and deltas[2] == (None, None)


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
def test_duel_finder_offers_classmates_and_rivals_then_searches_every_handle(client, klass):
    from .models import Duel

    url = reverse("classroom:duel_people")
    assert client.get(url).status_code == 302  # signed-in users only
    ali = User.objects.get(username="ali")
    client.force_login(ali)

    def found(q=""):
        return [(p["username"], p["mate"]) for p in client.get(url, {"q": q}).json()["results"]]

    assert found() == [("sami", True), ("vali", True)]  # the group, minus yourself; the teacher isn't a member
    Duel.objects.create(challenger=User.objects.create_user("bob", password="x"), opponent=ali, difficulty="easy")
    assert found() == [("bob", False), ("sami", True), ("vali", True)]  # and whoever you have duelled
    User.objects.create_user("valijon", password="x")
    User.objects.create_user("avali", password="x")
    User.objects.create_user("vali2", password="x", is_active=False)
    # the exact handle, then those starting with it, then the rest; never a blocked user or yourself
    assert [name for name, _ in found("VALI")] == ["vali", "valijon", "avali"]
    assert "ali" not in [name for name, _ in found("ali")]


@pytest.mark.django_db
def test_duel_badges_count_wins_runs_the_best_rating_and_perfect_quiz_runs(bank):
    from .duel_badges import duel_badges
    from .duels import accept, challenge
    from .models import Duel

    p1, p2 = _players()
    names = lambda: [b["name"] for b in duel_badges(p1)["earned"]]  # noqa: E731
    assert names() == []
    nxt = {b["name"]: b for b in duel_badges(p1)["next"]}
    assert (nxt["Birinchi g‘alaba"]["done"], nxt["Birinchi g‘alaba"]["total"]) == (0, 1)
    assert (nxt["Tajribali"]["done"], nxt["Tajribali"]["shown"]) == (0, "1200 / 1300")
    assert duel_badges(p1)["total"] == 11

    duel, _ = challenge(p1, "p2", "python", "easy")
    _play(duel, p1, right=5, secs=2)  # all five in 10 s
    accept(duel, p2)
    _play(duel, p2, right=1)
    assert names() == ["Birinchi g‘alaba", "Mukammal", "Chaqmoq"]
    assert {b["name"]: b["done"] for b in duel_badges(p1)["next"]}["Poliglot"] == 1
    assert [b["name"] for b in duel_badges(p2)["earned"]] == []

    # three wins in a row and a rating past 1300, from older duels: the badges stay once earned
    for _ in range(2):
        Duel.objects.create(challenger=p1, opponent=p2, difficulty="easy", status="finished", winner=p1,
                            mode="code", challenger_delta=45, opponent_delta=-45)
    Duel.objects.create(challenger=p1, opponent=p2, difficulty="easy", status="finished", winner=p2,
                        mode="code", challenger_delta=-40, opponent_delta=40)
    assert {"Zanjir", "Tajribali"} <= set(names())
