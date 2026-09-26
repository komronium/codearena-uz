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


@pytest.mark.django_db
def test_challenge_accept_picks_a_problem_neither_player_tried(client, duel_pool, python):
    from .models import Duel

    p1, p2 = _players()
    Submission.objects.create(user=p1, problem=duel_pool["e1"], language=python, source="x", verdict="WA")
    Submission.objects.create(user=p2, problem=duel_pool["e2"], language=python, source="x", verdict="AC")
    client.force_login(p1)
    url = reverse("classroom:duels")
    assert client.post(url, {"opponent": "p1", "difficulty": "easy"}).status_code == 200  # not yourself
    assert client.post(url, {"opponent": "nobody", "difficulty": "easy"}).status_code == 200
    assert client.post(url, {"opponent": "p2", "difficulty": "easy"}).status_code == 302
    assert client.post(url, {"opponent": "p2", "difficulty": "easy"}).status_code == 200  # one open duel per pair
    duel = Duel.objects.get()
    assert duel.status == "pending" and duel.problem is None  # nobody sees the problem before the start

    assert client.post(reverse("classroom:duel_answer", args=[duel.pk]), {"accept": "1"}).status_code == 404
    client.force_login(p2)
    assert client.post(reverse("classroom:duel_answer", args=[duel.pk]), {"accept": "1"}).status_code == 302
    duel.refresh_from_db()
    assert duel.status == "active" and duel.problem.slug == "e3"
    assert duel.ends_at - duel.started_at == timezone.timedelta(minutes=30)

    page = client.get(reverse("classroom:duels")).content.decode()
    assert "Ochiq duellar" in page and "p1" in page
    page = client.get(reverse("classroom:duel", args=[duel.pk])).content.decode()
    assert "E3" in page and 'hx-trigger="every 5s"' in page
    partial = client.get(reverse("classroom:duel", args=[duel.pk]), HTTP_HX_REQUEST="true").content.decode()
    assert "<html" not in partial and "E3" in partial
    client.force_login(User.objects.create_user("spy", password="x"))
    assert client.get(reverse("classroom:duel", args=[duel.pk])).status_code == 404


@pytest.mark.django_db
def test_first_ac_wins_and_moves_duel_elo_once(duel_pool, python):
    from judge.runner import run_submission

    from .duels import accept, challenge
    from .models import Duel

    for slug in ("e1", "e2", "e3"):
        duel_pool[slug].testcases.create(input="1\n", expected="1\n")
    p1, p2 = _players()
    duel, _ = challenge(p1, "p2", "easy")
    accept(duel, p2)
    duel.refresh_from_db()
    before = Submission.objects.create(user=p2, problem=duel.problem, language=python, source="x", verdict="AC")
    Submission.objects.filter(pk=before.pk).update(created=duel.started_at - timezone.timedelta(seconds=1))
    s = Submission.objects.create(user=p1, problem=duel.problem, language=python, source="print(1)")
    with (patch("judge.runner.sandbox.compile", return_value=(True, "")),
          patch("judge.runner.sandbox.run_tests", return_value=[("1\n", "OK", 10, 1024)])):
        run_submission(s.pk)
    duel.refresh_from_db()
    p1.refresh_from_db()
    p2.refresh_from_db()
    assert duel.status == "finished" and duel.winner == p1
    assert (p1.duel_rating, p2.duel_rating) == (1216, 1184)
    from .duels import settle

    settle(Duel.objects.get(pk=duel.pk))  # settling again changes nothing
    p1.refresh_from_db()
    assert p1.duel_rating == 1216


@pytest.mark.django_db
def test_no_ac_in_time_is_a_draw_and_unanswered_challenges_expire(duel_pool):
    from .duels import accept, challenge, settle
    from .models import Duel

    p1, p2 = _players()
    User.objects.filter(pk=p2.pk).update(duel_rating=1400)
    duel, _ = challenge(p1, "p2", "easy")
    accept(duel, User.objects.get(pk=p2.pk))
    Duel.objects.filter(pk=duel.pk).update(ends_at=timezone.now() - timezone.timedelta(seconds=1))
    settle(Duel.objects.get(pk=duel.pk))
    duel.refresh_from_db()
    p1.refresh_from_db()
    assert duel.status == "finished" and duel.winner is None and p1.duel_rating > 1200  # a draw lifts the lower one

    late, _ = challenge(p1, "p2", "easy")
    Duel.objects.filter(pk=late.pk).update(created=timezone.now() - timezone.timedelta(hours=2))
    settle(Duel.objects.get(pk=late.pk))
    assert Duel.objects.get(pk=late.pk).status == "expired"


@pytest.mark.django_db
def test_hints_are_locked_for_the_players_of_an_active_duel(client, duel_pool):
    from apps.problems.models import ProblemHint

    from .duels import accept, challenge

    p1, p2 = _players()
    duel, _ = challenge(p1, "p2", "easy")
    accept(duel, p2)
    duel.refresh_from_db()
    hint = ProblemHint.objects.create(problem=duel.problem, body_md="sir", cost_pct=10)
    client.force_login(p1)
    assert client.post(reverse("problems:hint", args=[duel.problem.slug, hint.pk])).status_code == 400
    page = client.get(reverse("problems:detail", args=[duel.problem.slug])).content.decode()
    assert "Duel" in page
