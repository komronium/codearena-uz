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

@pytest.fixture
def duel_pool(teacher):
    """Three easy problems and one medium; ali already tried e1."""
    return {slug: _problem(slug, teacher, difficulty=diff)
            for slug, diff in (("e1", "easy"), ("e2", "easy"), ("e3", "easy"), ("m1", "medium"))}


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


@pytest.mark.django_db
def test_a_challenge_starts_the_challengers_clock_and_accepting_starts_the_opponents(client, duel_pool, python):
    from .models import Duel

    p1, p2 = _players()
    Submission.objects.create(user=p1, problem=duel_pool["e1"], language=python, source="x", verdict="WA")
    Submission.objects.create(user=p2, problem=duel_pool["e2"], language=python, source="x", verdict="AC")
    client.force_login(p1)
    url = reverse("classroom:duels")
    assert client.post(url, {"opponent": "p1", "difficulty": "easy"}).status_code == 200  # not yourself
    assert client.post(url, {"opponent": "nobody", "difficulty": "easy"}).status_code == 200
    assert client.post(url, {"opponent": "p2", "difficulty": "easy"}).status_code == 302
    duel = Duel.objects.get()
    # nobody waits for anybody: the challenger's 30 minutes run from the challenge, on a
    # problem neither player ever tried
    assert duel.status == "pending" and duel.problem.slug == "e3" and duel.opponent_started_at is None
    assert duel.ends_at - duel.started_at == timezone.timedelta(minutes=30)
    assert client.post(url, {"opponent": "p2", "difficulty": "easy"}).status_code == 200  # one clock at a time
    assert Duel.objects.count() == 1

    assert client.post(reverse("classroom:duel_answer", args=[duel.pk]), {"accept": "1"}).status_code == 404
    client.post(reverse("classroom:duel_answer", args=[duel.pk]))  # the challenger can't take it back
    assert Duel.objects.get().status == "pending"
    client.force_login(p2)
    assert client.post(reverse("classroom:duel_answer", args=[duel.pk]), {"accept": "1"}).status_code == 302
    duel.refresh_from_db()
    assert duel.status == "active" and duel.problem.slug == "e3"
    assert duel.opponent_ends_at - duel.opponent_started_at == timezone.timedelta(minutes=30)

    page = client.get(url).content.decode()
    assert "Ochiq duellar" in page and "p1" in page
    page = client.get(reverse("classroom:duel", args=[duel.pk])).content.decode()
    assert "E3" in page and 'hx-trigger="every 5s"' in page and "?seen=active." in page
    partial = client.get(reverse("classroom:duel", args=[duel.pk]), {"seen": f"active.{p2.pk}"},
                         HTTP_HX_REQUEST="true")
    assert "<html" not in partial.content.decode() and "E3" in partial.content.decode()
    stale = client.get(reverse("classroom:duel", args=[duel.pk]), {"seen": "pending.0"}, HTTP_HX_REQUEST="true")
    assert stale.headers["HX-Refresh"] == "true"  # the page was drawn before p2 joined
    client.force_login(User.objects.create_user("spy", password="x"))
    assert client.get(reverse("classroom:duel", args=[duel.pk])).status_code == 404


@pytest.mark.django_db
def test_a_friend_who_declines_or_already_tried_the_problem_gets_no_duel(duel_pool, python):
    from .duels import accept, challenge, decline

    p1, p2 = _players()
    duel, _ = challenge(p1, "p2", "easy")
    decline(duel, p1)
    duel.refresh_from_db()
    assert duel.status == "pending"
    decline(duel, p2)
    duel.refresh_from_db()
    assert duel.status == "declined"

    p3 = User.objects.create_user("p3", password="x")
    _age(duel, challenger=timezone.timedelta(minutes=31))  # p1's clock ran out: free to challenge again
    duel, _ = challenge(p1, "p3", "easy")
    Submission.objects.create(user=p3, problem=duel.problem, language=python, source="x", verdict="WA")
    assert "urinib ko‘rgansiz" in accept(duel, p3)
    duel.refresh_from_db()
    assert duel.status == "expired"


@pytest.mark.django_db
def test_quick_match_joins_the_closest_rated_open_duel_on_a_problem_you_never_tried(duel_pool, python):
    from .duels import BUSY, _open, find_opponent, joinable_counts

    low, high = User.objects.create_user("low", password="x"), User.objects.create_user("high", password="x")
    User.objects.filter(pk=high.pk).update(duel_rating=1500)
    d_low = _open(low, "easy", duel_pool["e1"].pk)
    d_high = _open(User.objects.get(pk=high.pk), "easy", duel_pool["e2"].pk)
    near_high = User.objects.create_user("near", password="x", duel_rating=1450)
    fresh = User.objects.create_user("fresh", password="x", duel_rating=1450)
    assert joinable_counts(near_high) == {"easy": 2}

    # the closer duel is on a problem near_high already tried: it's never handed to them
    Submission.objects.create(user=near_high, problem=duel_pool["e2"], language=python, source="x", verdict="WA")
    duel, error = find_opponent(near_high, "easy")
    assert error == "" and duel.pk == d_low.pk
    duel.refresh_from_db()
    assert duel.opponent == near_high and duel.status == "active" and duel.opponent_started_at is not None

    duel, _ = find_opponent(fresh, "easy")
    assert duel.pk == d_high.pk  # 50 points apart, where low is 250

    # nobody left to join: the next player opens a duel of their own, clock running
    late = User.objects.create_user("late", password="x")
    duel, _ = find_opponent(late, "easy")
    assert duel.challenger == late and duel.opponent is None and duel.status == "pending"
    assert duel.started_at is not None and duel.problem.difficulty == "easy"
    assert find_opponent(late, "easy") == (None, BUSY)
    assert find_opponent(late, "nope")[1] == "Qiyinlikni tanlang."


@pytest.mark.django_db
def test_the_faster_solve_wins_once_the_other_clock_cant_beat_it(duel_pool, python):
    from judge.runner import run_submission

    from .duels import accept, challenge, settle
    from .models import Duel

    for slug in ("e1", "e2", "e3"):
        duel_pool[slug].testcases.create(input="1\n", expected="1\n")
    p1, p2 = _players()
    duel, _ = challenge(p1, "p2", "easy")
    s = Submission.objects.create(user=p1, problem=duel.problem, language=python, source="print(1)")
    Submission.objects.filter(pk=s.pk).update(created=duel.started_at + timezone.timedelta(minutes=2))
    with (patch("judge.runner.sandbox.compile", return_value=(True, "")),
          patch("judge.runner.sandbox.run_tests", return_value=[("1\n", "OK", 10, 1024)])):
        run_submission(s.pk)
    assert Duel.objects.get(pk=duel.pk).status == "pending"  # solved in 2:00, waiting for p2

    accept(duel, p2)
    settle(duel)
    assert Duel.objects.get(pk=duel.pk).status == "active"  # p2 has 2:00 to beat it
    # 3 minutes on p2's clock, but their 1:30 submission is still being judged: it may be an AC
    duel = _age(duel, opponent=timezone.timedelta(minutes=3))
    pending = Submission.objects.create(user=p2, problem=duel.problem, language=python, source="x")
    Submission.objects.filter(pk=pending.pk).update(created=duel.opponent_started_at + timezone.timedelta(seconds=90))
    settle(duel)
    assert Duel.objects.get(pk=duel.pk).status == "active"
    Submission.objects.filter(pk=pending.pk).update(verdict="WA")
    settle(duel)
    duel.refresh_from_db()
    p1.refresh_from_db()
    p2.refresh_from_db()
    assert duel.status == "finished" and duel.winner == p1
    assert (p1.duel_rating, p2.duel_rating) == (1216, 1184)
    settle(Duel.objects.get(pk=duel.pk))  # settling again changes nothing
    p1.refresh_from_db()
    assert p1.duel_rating == 1216

    from django.test import Client
    page = Client()
    page.force_login(p2)
    r = page.get(reverse("classroom:duels"))
    assert [(u.username, u.duels) for u in r.context["board"]] == [(p1.username, 1), (p2.username, 1)]
    assert r.context["duel_rank"] == 2 and r.context["record"] == {"wins": 0, "losses": 1, "draws": 0}


@pytest.mark.django_db
def test_no_ac_from_either_is_a_draw_and_an_open_duel_nobody_joins_expires(duel_pool):
    from .duels import accept, challenge, find_opponent, settle
    from .models import Duel

    p1, p2 = _players()
    User.objects.filter(pk=p2.pk).update(duel_rating=1400)
    duel, _ = challenge(p1, "p2", "easy")
    accept(duel, User.objects.get(pk=p2.pk))
    duel = _age(duel, challenger=timezone.timedelta(minutes=40), opponent=timezone.timedelta(minutes=29))
    settle(duel)
    assert Duel.objects.get(pk=duel.pk).status == "active"  # p2 still has a minute
    duel = _age(duel, opponent=timezone.timedelta(minutes=2))
    settle(duel)
    duel.refresh_from_db()
    p1.refresh_from_db()
    assert duel.status == "finished" and duel.winner is None and p1.duel_rating > 1200  # a draw lifts the lower one

    lonely, _ = find_opponent(User.objects.create_user("lonely", password="x"), "easy")
    lonely = _age(lonely, challenger=timezone.timedelta(days=4), created=timezone.timedelta(days=4))
    settle(lonely)
    assert Duel.objects.get(pk=lonely.pk).status == "expired"


@pytest.mark.django_db
def test_hints_are_locked_while_your_duel_clock_runs(client, duel_pool):
    from apps.problems.models import ProblemHint

    from .duels import challenge

    p1, p2 = _players()
    duel, _ = challenge(p1, "p2", "easy")
    hint = ProblemHint.objects.create(problem=duel.problem, body_md="sir", cost_pct=10)
    client.force_login(p1)
    assert client.post(reverse("problems:hint", args=[duel.problem.slug, hint.pk])).status_code == 400
    page = client.get(reverse("problems:detail", args=[duel.problem.slug])).content.decode()
    assert "Duel" in page
    client.force_login(p2)  # hasn't accepted: no clock of theirs runs
    assert client.post(reverse("problems:hint", args=[duel.problem.slug, hint.pk])).status_code != 400


@pytest.mark.django_db
def test_duel_page_shows_each_run_from_its_own_start(client, duel_pool, python):
    from .duels import accept, challenge

    p1, p2 = _players()
    duel, _ = challenge(p1, "p2", "easy")
    for verdict, minutes in (("WA", 3), ("AC", 7)):
        _sub(p1, duel.problem, python, verdict, duel.started_at + timezone.timedelta(minutes=minutes))
    accept(duel, p2)
    duel.refresh_from_db()
    _sub(p2, duel.problem, python, "WA", duel.opponent_started_at + timezone.timedelta(seconds=5))
    client.force_login(p2)
    r = client.get(reverse("classroom:duel", args=[duel.pk]))
    players = {p["user"].username: p for p in r.context["players"]}
    assert (players["p1"]["attempts"], players["p1"]["solved_in"]) == (2, "07:00")
    assert (players["p2"]["attempts"], players["p2"]["solved_in"], players["p2"]["running"]) == (1, None, True)
    assert r.context["best"] == {"at": "23.33", "time": "07:00"}  # the time to beat, on both lanes
    assert r.context["beat_by"] == duel.opponent_started_at + timezone.timedelta(minutes=7)
    assert "07:00" in r.content.decode()


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
