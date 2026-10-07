from datetime import timedelta
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.core.management import call_command, CommandError
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.problems.models import Language, Problem
from apps.submissions.models import Submission

from .models import Clarification, Contest, ContestProblem, Participation
from .standings import compute_standings


@pytest.fixture
def python(db):
    return Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")


@pytest.fixture
def author(db):
    return User.objects.create_user("teacher", password="x")


@pytest.fixture
def problem_a(author):
    return Problem.objects.create(slug="a", title="A", statement_md="x", author=author, is_public=False)


@pytest.fixture
def problem_b(author):
    return Problem.objects.create(slug="b", title="B", statement_md="x", author=author, is_public=False)


@pytest.fixture
def contest(db, problem_a, problem_b):
    c = Contest.objects.create(title="Sprint", start=timezone.now() - timezone.timedelta(hours=1),
                               end=timezone.now() + timezone.timedelta(hours=1))
    ContestProblem.objects.create(contest=c, problem=problem_a, label="A", order=0, points=100)
    ContestProblem.objects.create(contest=c, problem=problem_b, label="B", order=1, points=100)
    return c


def _sub(user, problem, contest, python, verdict, minutes_after_start, passed=0):
    s = Submission.objects.create(user=user, problem=problem, contest=contest, language=python,
                                  source="x", verdict=verdict, passed=passed)
    s.created = contest.start + timezone.timedelta(minutes=minutes_after_start)
    s.save(update_fields=["created"])
    return s


def test_ranks_by_score_then_penalty(contest, problem_a, problem_b, python):
    ali = User.objects.create_user("ali", password="x")
    bob = User.objects.create_user("bob", password="x")
    Participation.objects.create(user=ali, contest=contest)
    Participation.objects.create(user=bob, contest=contest)

    # ali: solves A at minute 10 (no wrong attempts) -> penalty 10, solved 1
    _sub(ali, problem_a, contest, python, "AC", 10)
    # bob: WA on A at minute 5, AC at minute 20 -> penalty 20 + 20 = 40, solved 1
    _sub(bob, problem_a, contest, python, "WA", 5)
    _sub(bob, problem_a, contest, python, "AC", 20)

    rows = compute_standings(contest)
    assert [r["user"] for r in rows] == [ali, bob]
    assert rows[0]["penalty"] == 10 and rows[0]["solved"] == 1
    assert rows[1]["penalty"] == 40 and rows[1]["solved"] == 1


def _rules_contest(rules, minutes, problem_a, problem_b, users):
    """An ended contest of `minutes` under `rules`, problems A (500) and B (1000), `users` in it."""
    now = timezone.now()
    c = Contest.objects.create(title=rules, type=rules, start=now - timezone.timedelta(minutes=minutes), end=now)
    ContestProblem.objects.create(contest=c, problem=problem_a, label="A", order=0, points=500)
    ContestProblem.objects.create(contest=c, problem=problem_b, label="B", order=1, points=1000)
    people = [User.objects.create_user(name, password="x") for name in users]
    for u in people:
        Participation.objects.create(user=u, contest=c)
    return c, people


def test_codeforces_points_fall_with_time_and_wrong_tries(problem_a, problem_b, python):
    """max(0.3x, x - floor(120xt / 250d) - 50w): a 500 solved at 00:04 of a 2.5-hour round is the
    494 a Codeforces board shows; each counted wrong try costs 50; nothing drops below 30%."""
    c, (ali, bob, cem) = _rules_contest(Contest.Type.CF, 150, problem_a, problem_b, ["ali", "bob", "cem"])
    _sub(ali, problem_a, c, python, "AC", 4)
    _sub(bob, problem_a, c, python, "WA", 1, passed=3)
    _sub(bob, problem_a, c, python, "AC", 10)
    for minute in range(7):
        _sub(cem, problem_a, c, python, "WA", minute, passed=1)
    _sub(cem, problem_a, c, python, "AC", 140)
    rows = {r["user"]: r for r in compute_standings(c)}
    assert rows[ali]["cells"][0]["points"] == 494
    assert rows[bob]["cells"][0]["points"] == 500 - 16 - 50
    assert rows[cem]["cells"][0]["points"] == 150
    assert rows[ali]["score"] == 494 and rows[ali]["penalty"] == rows[bob]["penalty"] == 0


def test_codeforces_forgives_test_1_and_compile_errors_and_ties_share_a_place(problem_a, problem_b, python):
    c, (ali, bob) = _rules_contest(Contest.Type.CF, 120, problem_a, problem_b, ["ali", "bob"])
    _sub(ali, problem_a, c, python, "WA", 1)  # failed test 1, the statement's example
    _sub(ali, problem_a, c, python, "CE", 2)
    _sub(ali, problem_a, c, python, "AC", 5)
    _sub(bob, problem_a, c, python, "AC", 5)
    rows = compute_standings(c)
    assert [r["cells"][0]["wrong"] for r in rows] == [0, 0]
    assert [(r["score"], r["rank"]) for r in rows] == [(490, 1), (490, 1)]


def test_icpc_ranks_by_solved_then_penalty_of_10_minutes_a_try(problem_a, problem_b, python):
    c, (ali, bob, cem) = _rules_contest(Contest.Type.ICPC, 120, problem_a, problem_b, ["ali", "bob", "cem"])
    _sub(ali, problem_a, c, python, "AC", 50)
    _sub(ali, problem_b, c, python, "AC", 60)
    _sub(bob, problem_a, c, python, "AC", 15)
    _sub(cem, problem_b, c, python, "WA", 1, passed=2)
    _sub(cem, problem_b, c, python, "AC", 3)  # 3 + 10 = 13 < bob's 15; at 20 a try bob would lead
    rows = compute_standings(c)
    assert [(r["user"], r["score"], r["penalty"]) for r in rows] == [(ali, 2, 110), (cem, 1, 13), (bob, 1, 15)]
    assert rows[1]["cells"][1]["mark"] == "+1" and rows[0]["cells"][0]["mark"] == "+"


def test_board_shows_each_rules_columns(client, problem_a, problem_b, python):
    cf, (ali,) = _rules_contest(Contest.Type.CF, 150, problem_a, problem_b, ["ali"])
    _sub(ali, problem_a, cf, python, "AC", 4)
    cache.clear()
    html = client.get(reverse("contests:standings", args=[cf.pk])).content.decode()
    assert 'class="ca-cf-ac">494</span>' in html and ">Jarima</th>" not in html

    icpc, (bob,) = _rules_contest(Contest.Type.ICPC, 120, problem_a, problem_b, ["bob"])
    _sub(bob, problem_a, icpc, python, "WA", 1, passed=1)
    _sub(bob, problem_a, icpc, python, "AC", 7)
    html = client.get(reverse("contests:standings", args=[icpc.pk])).content.decode()
    assert 'class="ca-cf-ac">+1</span>' in html and ">Jarima</th>" in html


def test_more_points_rank_above_lower_penalty(contest, problem_a, problem_b, python):
    ali = User.objects.create_user("ali", password="x")
    bob = User.objects.create_user("bob", password="x")
    Participation.objects.create(user=ali, contest=contest)
    Participation.objects.create(user=bob, contest=contest)

    _sub(ali, problem_a, contest, python, "AC", 5)
    _sub(ali, problem_b, contest, python, "AC", 100)  # ali solves both, high penalty
    _sub(bob, problem_a, contest, python, "AC", 1)  # bob solves only one, low penalty

    rows = compute_standings(contest)
    assert rows[0]["user"] == ali and rows[0]["solved"] == 2
    assert rows[1]["user"] == bob and rows[1]["solved"] == 1


def test_score_ties_break_by_penalty(contest, problem_a, problem_b, python):
    ali = User.objects.create_user("ali", password="x")
    bob = User.objects.create_user("bob", password="x")
    Participation.objects.create(user=ali, contest=contest)
    Participation.objects.create(user=bob, contest=contest)

    _sub(ali, problem_a, contest, python, "AC", 50)
    _sub(bob, problem_a, contest, python, "AC", 10)

    rows = compute_standings(contest)
    assert rows[0]["user"] == bob  # same score, lower penalty (10 < 50) wins
    assert rows[0]["score"] == rows[1]["score"] == 100


def test_only_judged_wrong_answers_cost_penalty(contest, problem_a, problem_b, python):
    ali = User.objects.create_user("ali", password="x")
    bob = User.objects.create_user("bob", password="x")
    Participation.objects.create(user=ali, contest=contest)
    Participation.objects.create(user=bob, contest=contest)

    # ali: a compile error and a still-pending run before the AC cost nothing
    _sub(ali, problem_a, contest, python, "CE", 1)
    _sub(ali, problem_a, contest, python, "PENDING", 2)
    _sub(ali, problem_a, contest, python, "AC", 10)
    # unsolved B: CE and RUNNING are not shown as wrong tries either
    _sub(ali, problem_b, contest, python, "CE", 3)
    _sub(ali, problem_b, contest, python, "RUNNING", 4)
    # bob: an output-limit failure is a real wrong try
    _sub(bob, problem_a, contest, python, "OLE", 1)
    _sub(bob, problem_a, contest, python, "AC", 10)

    rows = {r["user"]: r for r in compute_standings(contest)}
    assert rows[ali]["penalty"] == 10 and rows[ali]["cells"][0]["wrong"] == 0
    assert rows[ali]["cells"][1]["wrong"] == 0
    assert rows[bob]["penalty"] == 30 and rows[bob]["cells"][0]["wrong"] == 1


@pytest.mark.django_db
def test_register_creates_participation(client):
    c = Contest.objects.create(title="Sprint", start=timezone.now() - timezone.timedelta(hours=1),
                               end=timezone.now() + timezone.timedelta(hours=1))
    user = User.objects.create_user("ali", password="x")
    client.force_login(user)
    r = client.post(reverse("contests:register", args=[c.pk]))
    assert r.status_code == 302
    assert Participation.objects.filter(user=user, contest=c).exists()


@pytest.mark.django_db
def test_register_rejected_when_ip_prefix_does_not_match(client):
    c = Contest.objects.create(title="Sprint", start=timezone.now() - timezone.timedelta(hours=1),
                               end=timezone.now() + timezone.timedelta(hours=1),
                               allowed_ip_prefix="10.0.")
    user = User.objects.create_user("ali", password="x")
    client.force_login(user)
    r = client.post(reverse("contests:register", args=[c.pk]), REMOTE_ADDR="192.168.1.1")
    assert r.status_code == 400
    assert not Participation.objects.filter(user=user, contest=c).exists()


@pytest.mark.django_db
def test_register_allowed_when_ip_prefix_matches(client):
    c = Contest.objects.create(title="Sprint", start=timezone.now() - timezone.timedelta(hours=1),
                               end=timezone.now() + timezone.timedelta(hours=1),
                               allowed_ip_prefix="10.0.")
    user = User.objects.create_user("ali", password="x")
    client.force_login(user)
    r = client.post(reverse("contests:register", args=[c.pk]), REMOTE_ADDR="10.0.0.5")
    assert r.status_code == 302
    assert Participation.objects.filter(user=user, contest=c).exists()


@pytest.mark.django_db
def test_register_rejected_when_not_in_require_group(client):
    from apps.accounts.models import Group

    teacher = User.objects.create_user("t", password="x")
    group = Group.objects.create(name="2-kurs", teacher=teacher)
    c = Contest.objects.create(title="Sprint", start=timezone.now() - timezone.timedelta(hours=1),
                               end=timezone.now() + timezone.timedelta(hours=1), require_group=group)
    user = User.objects.create_user("ali", password="x")
    client.force_login(user)
    r = client.post(reverse("contests:register", args=[c.pk]))
    assert r.status_code == 400
    assert not Participation.objects.filter(user=user, contest=c).exists()


@pytest.mark.django_db
def test_register_after_end_rejected(client):
    c = Contest.objects.create(title="Sprint", start=timezone.now() - timezone.timedelta(hours=2),
                               end=timezone.now() - timezone.timedelta(hours=1))
    user = User.objects.create_user("ali", password="x")
    client.force_login(user)
    r = client.post(reverse("contests:register", args=[c.pk]))
    assert r.status_code == 400
    assert not Participation.objects.filter(user=user, contest=c).exists()


@pytest.mark.django_db
def test_list_and_detail_render(client):
    c = Contest.objects.create(title="Sprint", start=timezone.now(), end=timezone.now() + timezone.timedelta(hours=1))
    assert client.get(reverse("contests:list")).status_code == 200
    assert client.get(reverse("contests:detail", args=[c.pk])).status_code == 200


@pytest.mark.django_db
def test_list_groups_ended_contests_by_month_and_shows_your_rating_change(client):
    ali = User.objects.create_user("ali", password="x")
    now = timezone.now()
    live = Contest.objects.create(title="Live", start=now - timezone.timedelta(minutes=30),
                                  end=now + timezone.timedelta(minutes=90))
    old = Contest.objects.create(title="Old", is_rated=True, start=now - timezone.timedelta(days=40),
                                 end=now - timezone.timedelta(days=40) + timezone.timedelta(hours=2))
    Contest.objects.create(title="Skipped", start=now - timezone.timedelta(days=2),
                           end=now - timezone.timedelta(days=2) + timezone.timedelta(hours=2))
    Participation.objects.create(user=ali, contest=live)
    Participation.objects.create(user=ali, contest=old, rating_before=1200, rating_after=1180)
    client.force_login(ali)
    r = client.get(reverse("contests:list"))
    page = r.content.decode()
    assert r.context["running"][0].elapsed_pct == 25
    assert r.context["running"][0].me is not None and "Davom etish" in page
    ended = {c.title: c for c in r.context["ended"]}
    assert ended["Old"].my_delta == -20 and ended["Skipped"].me is None
    assert ended["Old"].start_month in page and "-20" in page


@pytest.mark.django_db
def test_standings_view_renders(client, contest):
    r = client.get(reverse("contests:standings", args=[contest.pk]))
    assert r.status_code == 200


@pytest.fixture
def veteran(db):
    """Makes users past the newcomer ramp (six rated contests behind them), whose shown rating
    is the one the maths uses."""
    from .rating import RAMP

    start = timezone.now() - timezone.timedelta(days=60)
    history = [Contest.objects.create(title=f"History {i}", is_rated=True, rating_applied=True,
                                      start=start + timezone.timedelta(days=i),
                                      end=start + timezone.timedelta(days=i, hours=2)) for i in range(len(RAMP))]

    def make(username, rating):
        user = User.objects.create_user(username, password="x", rating=rating)
        Participation.objects.bulk_create(Participation(user=user, contest=c, rating_before=rating, rating_after=rating)
                                          for c in history)
        return user
    return make


@pytest.fixture
def ended_rated_contest(db, problem_a, problem_b):
    c = Contest.objects.create(title="Rated", is_rated=True,
                               start=timezone.now() - timezone.timedelta(hours=2),
                               end=timezone.now() - timezone.timedelta(hours=1))
    ContestProblem.objects.create(contest=c, problem=problem_a, label="A", order=0, points=100)
    ContestProblem.objects.create(contest=c, problem=problem_b, label="B", order=1, points=100)
    return c


def test_recalc_rating_applies_deltas_and_is_idempotent(ended_rated_contest, problem_a, python, veteran):
    winner, loser = veteran("winner", 1500), veteran("loser", 1500)
    Participation.objects.create(user=winner, contest=ended_rated_contest)
    Participation.objects.create(user=loser, contest=ended_rated_contest)
    _sub(winner, problem_a, ended_rated_contest, python, "AC", 5)
    _sub(loser, problem_a, ended_rated_contest, python, "WA", 7)

    call_command("recalc_rating", ended_rated_contest.pk, stdout=StringIO())

    winner.refresh_from_db()
    loser.refresh_from_db()
    ended_rated_contest.refresh_from_db()
    assert ended_rated_contest.rating_applied is True
    assert winner.rating > 1500
    assert loser.rating < 1500
    p_winner = Participation.objects.get(user=winner, contest=ended_rated_contest)
    assert p_winner.rank == 1 and p_winner.rating_before == 1500 and p_winner.rating_after == winner.rating

    # second run is a no-op
    rating_after_first_run = winner.rating
    call_command("recalc_rating", ended_rated_contest.pk, stdout=StringIO())
    winner.refresh_from_db()
    assert winner.rating == rating_after_first_run


def test_recalc_rating_without_id_processes_all_eligible_ended_contests(ended_rated_contest, problem_a, python):
    """Cron-friendly mode: no contest_id -> every ended, rated, not-yet-applied contest."""
    winner = User.objects.create_user("winner", password="x", rating=1500)
    Participation.objects.create(user=winner, contest=ended_rated_contest)
    _sub(winner, problem_a, ended_rated_contest, python, "AC", 5)

    still_running = Contest.objects.create(
        title="Live", is_rated=True, start=timezone.now(), end=timezone.now() + timezone.timedelta(hours=1))

    call_command("recalc_rating", stdout=StringIO())

    ended_rated_contest.refresh_from_db()
    still_running.refresh_from_db()
    assert ended_rated_contest.rating_applied is True
    assert still_running.rating_applied is False


def test_recalc_rating_rejects_unrated_contest(contest):
    with pytest.raises(CommandError):
        call_command("recalc_rating", contest.pk, stdout=StringIO())


def test_recalc_rating_rejects_contest_not_ended(python):
    c = Contest.objects.create(title="Live", is_rated=True, start=timezone.now(),
                               end=timezone.now() + timezone.timedelta(hours=1))
    with pytest.raises(CommandError):
        call_command("recalc_rating", c.pk, stdout=StringIO())


def test_recalc_rating_favorite_win_has_small_delta(ended_rated_contest, problem_a, python, veteran):
    """Unequal ratings: 1800 favorite finishing 1st vs 1200 underdog 2nd — the win was
    expected, so it is worth less than the same win in an equal field."""
    from apps.contests.rating import deltas

    favorite, underdog = veteran("fav", 1800), veteran("dog", 1200)
    Participation.objects.create(user=favorite, contest=ended_rated_contest)
    Participation.objects.create(user=underdog, contest=ended_rated_contest)
    _sub(favorite, problem_a, ended_rated_contest, python, "AC", 5)
    _sub(underdog, problem_a, ended_rated_contest, python, "WA", 7)

    call_command("recalc_rating", ended_rated_contest.pk, stdout=StringIO())

    favorite.refresh_from_db()
    underdog.refresh_from_db()
    assert 0 < favorite.rating - 1800 < deltas([1500, 1500], [1, 2])[0]
    assert underdog.rating < 1200


def test_recalc_rating_skips_registered_without_submissions(ended_rated_contest, problem_a, python):
    """Registered but never submitted = didn't take part: rating untouched, not ranked."""
    winner = User.objects.create_user("winner", password="x", rating=1500)
    ghost = User.objects.create_user("ghost", password="x", rating=1500)
    Participation.objects.create(user=winner, contest=ended_rated_contest)
    Participation.objects.create(user=ghost, contest=ended_rated_contest)
    _sub(winner, problem_a, ended_rated_contest, python, "AC", 5)

    call_command("recalc_rating", ended_rated_contest.pk, stdout=StringIO())

    ghost.refresh_from_db()
    assert ghost.rating == 1500
    assert Participation.objects.get(user=ghost, contest=ended_rated_contest).rating_after is None


def test_tied_results_share_rank_and_rating_delta(ended_rated_contest, problem_a, python, veteran):
    """Same solved+penalty -> same rank ("1, 1, 3") and identical rating change; the
    arbitrary sort order between equals must not decide who gains and who loses."""
    users = [veteran(f"u{i}", 1500) for i in range(3)]
    for u in users:
        Participation.objects.create(user=u, contest=ended_rated_contest)
    _sub(users[0], problem_a, ended_rated_contest, python, "AC", 5)
    _sub(users[1], problem_a, ended_rated_contest, python, "AC", 5)
    _sub(users[2], problem_a, ended_rated_contest, python, "WA", 5)

    rows = compute_standings(ended_rated_contest)
    assert [r["rank"] for r in rows] == [1, 1, 3]

    call_command("recalc_rating", ended_rated_contest.pk, stdout=StringIO())
    for u in users:
        u.refresh_from_db()
    assert users[0].rating == users[1].rating > 1500 > users[2].rating


def test_codeforces_deltas_and_anti_inflation():
    """Mirzayanov's algorithm: a 2-person equal field by hand is +107 / -87 before the
    anti-inflation fee of 11 each. The changes never sum above zero, and an equal field
    rewards places in order."""
    from apps.contests.rating import deltas

    assert deltas([1500, 1500], [1, 2]) == [96, -98]
    field = deltas([1000] * 15, list(range(1, 16)))
    assert field == sorted(field, reverse=True) and field[0] > 0 > field[-1]
    assert -15 <= sum(field) <= 0
    assert deltas([1000] * 3, [2, 2, 3])[:2] == [27, 27]  # a tie group all take its last place


def test_contest_detail_shows_my_rank_and_solved_marks(client, contest, problem_a, problem_b, python):
    ali = User.objects.create_user("ali", password="x")
    bob = User.objects.create_user("bob", password="x")
    Participation.objects.create(user=ali, contest=contest)
    Participation.objects.create(user=bob, contest=contest)
    _sub(bob, problem_a, contest, python, "AC", 5)
    _sub(ali, problem_a, contest, python, "WA", 8)
    _sub(ali, problem_a, contest, python, "AC", 10)
    cache.clear()  # standings are cached per contest pk; pks repeat across tests
    client.force_login(ali)
    r = client.get(reverse("contests:detail", args=[contest.pk]))
    html = r.content.decode()
    assert "Sizning natijangiz" in html and "<dd>2<small>/ 2</small></dd>" in html  # bob solved A earlier -> lower penalty
    assert 'title="Yechilgan: 00:10, 1 ta xatodan keyin"' in html  # hh:mm from the start, as Codeforces prints it
    assert r.context["problems"][0].solved_count == 2 and r.context["problems"][1].solved_count == 0


def test_active_contest_for_prefers_user_participation(problem_a):
    """Problem in two overlapping contests: only the one the user joined wins."""
    from apps.contests.services import active_contest_for

    now = timezone.now()
    contest_a = Contest.objects.create(
        title="A", start=now - timezone.timedelta(hours=1), end=now + timezone.timedelta(hours=1))
    contest_b = Contest.objects.create(
        title="B", start=now - timezone.timedelta(hours=1), end=now + timezone.timedelta(hours=1))
    ContestProblem.objects.create(contest=contest_a, problem=problem_a, label="A", order=0)
    ContestProblem.objects.create(contest=contest_b, problem=problem_a, label="A", order=0)
    # Ensure A has the lower pk so a naive .first() without participation filter
    # would pick A — the bug this test guards against.
    assert contest_a.pk < contest_b.pk

    user = User.objects.create_user("ali", password="x")
    Participation.objects.create(user=user, contest=contest_b)

    assert active_contest_for(user, problem_a) == contest_b



def test_close_ended_contests_makes_problems_public(problem_a, problem_b, python):
    ended = Contest.objects.create(title="Past", start=timezone.now() - timezone.timedelta(hours=2),
                                   end=timezone.now() - timezone.timedelta(hours=1))
    ContestProblem.objects.create(contest=ended, problem=problem_a, label="A")
    running = Contest.objects.create(title="Live", start=timezone.now(),
                                     end=timezone.now() + timezone.timedelta(hours=1))
    ContestProblem.objects.create(contest=running, problem=problem_b, label="B")

    call_command("close_ended_contests", stdout=StringIO())

    problem_a.refresh_from_db()
    problem_b.refresh_from_db()
    assert problem_a.is_public is True
    assert problem_b.is_public is False


@pytest.mark.django_db
def test_ask_clarification_as_participant(client, contest):
    user = User.objects.create_user("ali", password="x")
    Participation.objects.create(user=user, contest=contest)
    client.force_login(user)
    r = client.post(reverse("contests:ask_clarification", args=[contest.pk]), {"question": "Time limit?"})
    assert r.status_code == 302
    assert Clarification.objects.filter(contest=contest, user=user, question="Time limit?").exists()


@pytest.mark.django_db
def test_ask_clarification_rejects_non_participant(client, contest):
    user = User.objects.create_user("ali", password="x")
    client.force_login(user)
    r = client.post(reverse("contests:ask_clarification", args=[contest.pk]), {"question": "Time limit?"})
    assert r.status_code == 400
    assert not Clarification.objects.exists()


@pytest.mark.django_db
def test_ask_clarification_takes_only_a_problem_of_this_contest(client, contest, problem_a):
    other = Contest.objects.create(title="Other", start=contest.start, end=contest.end)
    foreign = ContestProblem.objects.create(contest=other, problem=problem_a, label="A")
    user = User.objects.create_user("ali", password="x")
    Participation.objects.create(user=user, contest=contest)
    client.force_login(user)
    url = reverse("contests:ask_clarification", args=[contest.pk])
    for bad in (str(foreign.pk), "abc"):
        assert client.post(url, {"question": "?", "problem_id": bad}).status_code == 400
    assert not Clarification.objects.exists()
    own = contest.contest_problems.get(label="B")
    assert client.post(url, {"question": "?", "problem_id": str(own.pk)}).status_code == 302
    assert Clarification.objects.get().problem == own


@pytest.mark.django_db
def test_ask_clarification_rejects_after_contest_end(client, problem_a):
    ended = Contest.objects.create(title="Past", start=timezone.now() - timezone.timedelta(hours=2),
                                   end=timezone.now() - timezone.timedelta(hours=1))
    user = User.objects.create_user("ali", password="x")
    Participation.objects.create(user=user, contest=ended)
    client.force_login(user)
    r = client.post(reverse("contests:ask_clarification", args=[ended.pk]), {"question": "?"})
    assert r.status_code == 400


@pytest.mark.django_db
def test_unanswered_clarification_hidden_from_other_participants(client, contest):
    asker = User.objects.create_user("asker", password="x")
    other = User.objects.create_user("other", password="x")
    Participation.objects.create(user=asker, contest=contest)
    Participation.objects.create(user=other, contest=contest)
    Clarification.objects.create(contest=contest, user=asker, question="secret?")

    client.force_login(other)
    r = client.get(reverse("contests:clarifications", args=[contest.pk]))
    assert list(r.context["clars"]) == []

    client.force_login(asker)
    r = client.get(reverse("contests:clarifications", args=[contest.pk]))
    assert len(r.context["clars"]) == 1


@pytest.mark.django_db
def test_unanswered_clarification_visible_to_staff(client, contest):
    asker = User.objects.create_user("asker", password="x")
    staff = User.objects.create_user("staff", password="x", is_staff=True)
    Participation.objects.create(user=asker, contest=contest)
    Clarification.objects.create(contest=contest, user=asker, question="secret?")

    client.force_login(staff)
    r = client.get(reverse("contests:clarifications", args=[contest.pk]))
    assert len(r.context["clars"]) == 1


@pytest.mark.django_db
def test_staff_can_answer_clarification_then_visible_to_all(client, contest):
    asker = User.objects.create_user("asker", password="x")
    other = User.objects.create_user("other", password="x")
    staff = User.objects.create_user("staff", password="x", is_staff=True)
    Participation.objects.create(user=asker, contest=contest)
    Participation.objects.create(user=other, contest=contest)
    clar = Clarification.objects.create(contest=contest, user=asker, question="secret?")

    client.force_login(staff)
    r = client.post(reverse("contests:answer_clarification", args=[contest.pk, clar.pk]), {"answer": "yes"})
    assert r.status_code == 302
    clar.refresh_from_db()
    assert clar.answer == "yes" and clar.answered_by == staff and clar.answered_at is not None

    client.force_login(other)
    r = client.get(reverse("contests:clarifications", args=[contest.pk]))
    assert len(r.context["clars"]) == 1


@pytest.mark.django_db
def test_non_staff_cannot_answer_clarification(client, contest):
    asker = User.objects.create_user("asker", password="x")
    Participation.objects.create(user=asker, contest=contest)
    clar = Clarification.objects.create(contest=contest, user=asker, question="secret?")

    client.force_login(asker)
    r = client.post(reverse("contests:answer_clarification", args=[contest.pk, clar.pk]), {"answer": "yes"})
    assert r.status_code == 403  # signed in, not staff: refused, not sent to the login form
    clar.refresh_from_db()
    assert clar.answer == ""



def test_standings_headers_are_words_not_symbols(client, contest):
    Participation.objects.create(user=User.objects.create_user("ali", password="x"), contest=contest)
    page = client.get(reverse("contests:standings", args=[contest.pk])).content.decode()
    assert ">Ball</th>" in page and ">=</th>" not in page
    Contest.objects.filter(pk=contest.pk).update(type=Contest.Type.ICPC)
    assert ">Yechildi</th>" in client.get(reverse("contests:standings", args=[contest.pk])).content.decode()

@pytest.mark.django_db
def test_disqualified_participant_ranks_last_and_cannot_submit(client):
    from django.utils import timezone

    from apps.accounts.models import User
    from apps.contests.standings import compute_standings
    from apps.problems.models import Language, Problem
    from apps.submissions.models import Submission

    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    a = User.objects.create_user("a", password="x")
    b = User.objects.create_user("b", password="x")
    p = Problem.objects.create(slug="p", title="P", statement_md="x", author=staff)
    p.testcases.create(input="1\n", expected="1\n")
    c = Contest.objects.create(title="C", start=timezone.now() - timezone.timedelta(minutes=10),
                               end=timezone.now() + timezone.timedelta(hours=1))
    ContestProblem.objects.create(contest=c, problem=p, label="A")
    lang = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    for u in (a, b):
        Participation.objects.create(user=u, contest=c)
    Submission.objects.create(user=a, problem=p, contest=c, language=lang, source="x", verdict="AC")

    assert [r["user"] for r in compute_standings(c)] == [a, b]

    client.force_login(staff)
    r = client.post(reverse("contests:disqualify", args=[c.pk, a.pk]), {"disqualified": "1", "reason": "paste"})
    assert r.status_code == 302
    rows = compute_standings(c)
    assert [r["user"] for r in rows] == [b, a] and rows[1]["disqualified"] and rows[1]["rank"] == 2

    client.force_login(a)
    r = client.post(reverse("submissions:submit", args=["p"]), {"language": "python", "source": "print(1)"})
    assert r.status_code == 400

    client.force_login(staff)
    client.post(reverse("contests:disqualify", args=[c.pk, a.pk]), {"disqualified": "0"})
    assert [r["user"] for r in compute_standings(c)] == [a, b]


@pytest.mark.django_db
def test_disqualify_requires_staff(client):
    from django.utils import timezone

    from apps.accounts.models import User

    u = User.objects.create_user("u", password="x")
    c = Contest.objects.create(title="C", start=timezone.now(), end=timezone.now() + timezone.timedelta(hours=1))
    client.force_login(u)
    assert client.post(reverse("contests:disqualify", args=[c.pk, u.pk])).status_code == 403


def test_newcomers_start_at_zero_and_ramp_up_to_their_real_rating():
    """The maths starts a newcomer at 1000 but shows 0; six bonuses close the gap. Two
    newcomers who always tie lose 1 a contest to the fee, so they end at 1000 - 6."""
    from apps.contests.rating import RAMP, START, _new_ratings, hidden

    assert hidden(0, 0) == START and hidden(700, len(RAMP)) == 700
    shown = [0, 0]
    for k in range(len(RAMP)):
        shown = _new_ratings([{"rank": 1, "disqualified": False}] * 2, shown, [k, k])
        assert shown == [sum(RAMP[:k + 1]) - (k + 1)] * 2
    assert shown == [START - 6] * 2


def test_last_place_newcomer_still_sees_a_gain(ended_rated_contest, problem_a, python):
    a, b = (User.objects.create_user(n, password="x") for n in ("a", "b"))
    assert a.rating == 0
    for u, verdict in ((a, "AC"), (b, "WA")):
        Participation.objects.create(user=u, contest=ended_rated_contest)
        _sub(u, problem_a, ended_rated_contest, python, verdict, 5)
    call_command("recalc_rating", ended_rated_contest.pk, stdout=StringIO())
    a.refresh_from_db()
    b.refresh_from_db()
    assert a.rating > b.rating > 0


def test_division_rates_only_its_range_and_recounts_places(ended_rated_contest, problem_a, python, veteran):
    """Div. 4 is rated below 1400: a 1500 winner is on the board out of competition, and
    the rated pair is rated as 1st and 2nd between themselves."""
    from .rating import deltas

    Contest.objects.filter(pk=ended_rated_contest.pk).update(division=Contest.Division.DIV4)
    ended_rated_contest.refresh_from_db()
    strong, ali, bob = veteran("strong", 1500), veteran("ali", 1000), veteran("bob", 1000)
    for i, (u, verdict) in enumerate(((strong, "AC"), (ali, "AC"), (bob, "WA"))):
        Participation.objects.create(user=u, contest=ended_rated_contest)
        _sub(u, problem_a, ended_rated_contest, python, verdict, 5 + i)
    rows = compute_standings(ended_rated_contest)
    assert [(r["user"].username, r["out"]) for r in rows] == [("strong", True), ("ali", False), ("bob", False)]

    call_command("recalc_rating", ended_rated_contest.pk, stdout=StringIO())
    for u in (strong, ali, bob):
        u.refresh_from_db()
    assert strong.rating == 1500
    assert Participation.objects.get(user=strong, contest=ended_rated_contest).rating_after is None
    assert [ali.rating - 1000, bob.rating - 1000] == deltas([1000, 1000], [1, 2])
    assert ended_rated_contest.rates(1399) and not ended_rated_contest.rates(1400)


def test_replay_rebuilds_ratings_from_zero(problem_a, python):
    """--replay re-applies every applied contest in end order: the same ratings as applying
    them one by one, whatever happened to the numbers in between."""
    from .rating import apply_rating

    ali, bob = (User.objects.create_user(n, password="x") for n in ("ali", "bob"))
    first = _rated_contest("First", 10, problem_a, python, [ali], [bob])
    second = _rated_contest("Second", 1, problem_a, python, [bob], [ali])
    apply_rating(first)
    apply_rating(second)
    applied = dict(User.objects.values_list("username", "rating"))
    User.objects.update(rating=1234)

    out = StringIO()
    call_command("recalc_rating", replay=True, stdout=out)
    assert "replayed 2 rated contests" in out.getvalue()
    assert dict(User.objects.values_list("username", "rating")) == applied
    p = Participation.objects.get(contest=second, user=ali)
    assert p.rating_before == Participation.objects.get(contest=first, user=ali).rating_after


def test_upcoming_contest_problem_titles_stay_secret(client, author):
    """Registered users see no problem titles before the start: standings, clarifications, profile map."""
    secret = Problem.objects.create(slug="secret-sauce", title="Maxfiy retsept", statement_md="x", author=author,
                                    is_public=True)
    c = Contest.objects.create(title="Soon", start=timezone.now() + timezone.timedelta(hours=2),
                               end=timezone.now() + timezone.timedelta(hours=4))
    ContestProblem.objects.create(contest=c, problem=secret, label="A", order=0, points=100)
    ali = User.objects.create_user("ali", password="x")
    Participation.objects.create(contest=c, user=ali)
    client.force_login(ali)
    for url in (reverse("contests:standings", args=[c.pk]), reverse("contests:clarifications", args=[c.pk]),
                reverse("profile", args=["ali"]), reverse("problems:list")):
        body = client.get(url).content.decode()
        assert "Maxfiy retsept" not in body and "secret-sauce" not in body, url


def test_duration_label_rolls_hours_into_days():
    start = timezone.now()
    c = Contest(start=start, end=start + timezone.timedelta(days=7, minutes=3))
    assert c.duration_label == "7 kun 3 daq"
    c.end = start + timezone.timedelta(hours=3)
    assert c.duration_label == "3 soat"


def test_upcoming_contest_problems_sealed_even_for_staff(client, author):
    secret = Problem.objects.create(slug="sealed", title="Muhrlangan", statement_md="x", author=author)
    c = Contest.objects.create(title="Soon", start=timezone.now() + timezone.timedelta(hours=2),
                               end=timezone.now() + timezone.timedelta(hours=4))
    ContestProblem.objects.create(contest=c, problem=secret, label="A", order=0, points=100)
    client.force_login(User.objects.create_user("boss", password="x", is_staff=True))
    for url in (reverse("contests:detail", args=[c.pk]), reverse("contests:standings", args=[c.pk]),
                reverse("contests:clarifications", args=[c.pk])):
        body = client.get(url).content.decode()
        assert "Muhrlangan" not in body and "/problems/sealed/" not in body, url


def test_backfill_published_at_marks_contests_the_old_publish_handled(author, python):
    import importlib

    from django.apps import apps

    from apps.submissions.models import UserProblemSolved

    migration = importlib.import_module("apps.contests.migrations.0006_contest_published_at")
    past = {"start": timezone.now() - timezone.timedelta(hours=3), "end": timezone.now() - timezone.timedelta(hours=2)}
    hidden = Problem.objects.create(slug="h", title="H", statement_md="x", author=author, is_public=False)
    public = Problem.objects.create(slug="o", title="O", statement_md="x", author=author, is_public=True)

    def contest(title, problems, **times):
        c = Contest.objects.create(title=title, **(times or past))
        for i, p in enumerate(problems):
            ContestProblem.objects.create(contest=c, problem=p, label="AB"[i])
        return c

    traced = contest("traced", [hidden])  # the old publish left a solve pointing at its AC
    ac = Submission.objects.create(user=author, problem=hidden, contest=traced, language=python, source="x",
                                   verdict="AC")
    UserProblemSolved.objects.create(user=author, problem=hidden, first_ac_submission=ac)
    opened = contest("opened", [public])  # every problem already public
    contest("closed", [hidden])
    contest("empty", [])
    contest("running", [public], start=timezone.now() - timezone.timedelta(hours=1),
            end=timezone.now() + timezone.timedelta(hours=1))

    migration.backfill_published_at(apps, None)

    got = dict(Contest.objects.values_list("title", "published_at"))
    assert got["traced"] == traced.end and got["opened"] == opened.end
    assert got["closed"] is None and got["empty"] is None and got["running"] is None


@pytest.mark.django_db
def test_disqualifying_after_publish_takes_contest_solves_back(client, problem_a, python):
    staff = User.objects.create_user("boss", password="x", is_staff=True)
    ali = User.objects.create_user("ali", password="x")
    problem_a.points = 50
    problem_a.save()
    c = Contest.objects.create(title="Past", start=timezone.now() - timezone.timedelta(hours=3),
                               end=timezone.now() - timezone.timedelta(hours=2))
    ContestProblem.objects.create(contest=c, problem=problem_a, label="A")
    Participation.objects.create(user=ali, contest=c)
    Submission.objects.create(user=ali, problem=problem_a, contest=c, language=python, source="x", verdict="AC")
    client.force_login(staff)
    client.post(reverse("moderation:contest_publish", args=[c.pk]))
    ali.refresh_from_db()
    assert ali.practice_points == 50

    url = reverse("contests:disqualify", args=[c.pk, ali.pk])
    client.post(url, {"disqualified": "1", "reason": "copy"})
    ali.refresh_from_db()
    assert ali.practice_points == 0 and not ali.userproblemsolved_set.exists()
    client.post(url, {"disqualified": "0"})  # re-qualify
    ali.refresh_from_db()
    assert ali.practice_points == 50 and ali.userproblemsolved_set.count() == 1


@pytest.mark.django_db
def test_disqualify_sets_the_asked_state_so_a_stale_click_changes_nothing(client, problem_a, python):
    """Two teachers, or one stale tab: a second "disqualify" must not re-qualify."""
    from django.core.cache import cache

    staff = User.objects.create_user("boss", password="x", is_staff=True)
    ali = User.objects.create_user("ali", password="x")
    c = Contest.objects.create(title="Live", start=timezone.now() - timezone.timedelta(hours=1),
                               end=timezone.now() + timezone.timedelta(hours=1))
    p = Participation.objects.create(user=ali, contest=c)
    url = reverse("contests:disqualify", args=[c.pk, ali.pk])
    client.force_login(staff)

    for reason in ("copy", "again"):
        assert client.post(url, {"disqualified": "1", "reason": reason}).status_code == 302
        p.refresh_from_db()
        assert p.disqualified and p.disqualified_reason == "copy"  # the second click keeps the first reason
    assert client.post(url, {"reason": "no state"}).status_code == 400
    p.refresh_from_db()
    assert p.disqualified
    page = client.get(reverse("contests:standings", args=[c.pk])).content.decode()
    assert 'name="disqualified" value="0"' in page  # the button undoes the DQ it shows
    client.post(url, {"disqualified": "0"})
    p.refresh_from_db()
    assert not p.disqualified and p.disqualified_reason == ""
    page = client.get(reverse("contests:standings", args=[c.pk])).content.decode()
    assert 'name="disqualified" value="1"' in page
    cache.clear()  # standings are cached by contest pk, and pks repeat across tests


def _rated_contest(title, hours_ago, problem, python, users_solving, users_trying=()):
    """An ended rated contest: users_solving get AC in order, users_trying only WA."""
    c = Contest.objects.create(title=title, is_rated=True, start=timezone.now() - timezone.timedelta(hours=hours_ago + 2),
                               end=timezone.now() - timezone.timedelta(hours=hours_ago))
    ContestProblem.objects.create(contest=c, problem=problem, label="A", points=100)
    for i, u in enumerate([*users_solving, *users_trying]):
        Participation.objects.create(user=u, contest=c)
        s = Submission.objects.create(user=u, problem=problem, contest=c, language=python, source="x",
                                      verdict="AC" if u in users_solving else "WA")
        Submission.objects.filter(pk=s.pk).update(created=c.start + timezone.timedelta(minutes=10 + i))
    return c


@pytest.mark.django_db
def test_dq_after_rating_recomputes_the_latest_contest(client, problem_a, python, veteran):
    from apps.integrity.models import AuditEntry

    from .rating import apply_rating

    staff = User.objects.create_user("boss", password="x", is_staff=True)
    cheat, ali, bob = (veteran(n, 1200) for n in ("cheat", "ali", "bob"))
    c = _rated_contest("Final", 1, problem_a, python, [cheat, ali], [bob])
    apply_rating(c)
    cheat.refresh_from_db()
    gained = cheat.rating - 1200
    assert gained > 0
    User.objects.filter(pk=cheat.pk).update(rating=cheat.rating + 7)  # a manual edit made since stays

    client.force_login(staff)
    r = client.post(reverse("contests:disqualify", args=[c.pk, cheat.pk]), {"disqualified": "1"}, follow=True)
    for u in (cheat, ali, bob):
        u.refresh_from_db()
    rows = {p.user_id: p for p in Participation.objects.filter(contest=c)}
    assert rows[cheat.pk].rating_before == 1200 + 7  # the manual edit survives the rollback
    assert cheat.rating == rows[cheat.pk].rating_after < 1200 + 7  # last place now: a loss
    assert rows[ali.pk].rank == 1 and ali.rating == rows[ali.pk].rating_after
    assert "Reyting qayta hisoblandi" in r.content.decode()
    assert AuditEntry.objects.filter(action="rating_recompute", contest=c).count() == 1


@pytest.mark.django_db
def test_a_disqualified_newcomer_gets_no_ramp_bonus_and_keeps_the_step(problem_a, python):
    """Last place plus a newcomer's +360 bonus used to come out as a gain. Disqualified: the change
    can only take away, and the ramp step waits for the next clean contest."""
    from .rating import RAMP, apply_rating

    cheat, ali, bob = (User.objects.create_user(n, password="x") for n in ("cheat", "ali", "bob"))
    c = _rated_contest("Debut", 30, problem_a, python, [cheat, ali], [bob])
    Participation.objects.filter(contest=c, user=cheat).update(disqualified=True)
    apply_rating(c)
    for u in (cheat, ali, bob):
        u.refresh_from_db()
    assert cheat.rating <= 0 < bob.rating < ali.rating  # bob, last of the clean ones, still gains

    nxt = _rated_contest("Next", 1, problem_a, python, [cheat])
    apply_rating(nxt)
    p = Participation.objects.get(contest=nxt, user=cheat)
    assert p.rating_after - p.rating_before >= RAMP[0] - 50  # the first step's bonus, on a lone win


@pytest.mark.django_db
def test_dq_after_rating_leaves_older_contests_alone(client, problem_a, python):
    from .rating import apply_rating

    staff = User.objects.create_user("boss", password="x", is_staff=True)
    cheat, ali = (User.objects.create_user(n, password="x") for n in ("cheat", "ali"))
    old = _rated_contest("Old", 10, problem_a, python, [cheat, ali])
    apply_rating(old)
    newer = _rated_contest("Newer", 1, problem_a, python, [ali, cheat])
    apply_rating(newer)
    before = dict(User.objects.values_list("username", "rating"))

    client.force_login(staff)
    r = client.post(reverse("contests:disqualify", args=[old.pk, cheat.pk]), {"disqualified": "1"}, follow=True)
    assert dict(User.objects.values_list("username", "rating")) == before
    assert "reyting o‘zgarmadi" in r.content.decode()


# ---- virtual contests ---------------------------------------------------------------------------

@pytest.fixture
def past_contest(problem_a, python):
    """Published 2-hour contest: ali solved A at 0:30 with one WA, bob at 1:00."""
    c = Contest.objects.create(title="O‘tgan", start=timezone.now() - timezone.timedelta(days=1),
                               end=timezone.now() - timezone.timedelta(days=1) + timezone.timedelta(hours=2),
                               published_at=timezone.now())
    ContestProblem.objects.create(contest=c, problem=problem_a, label="A", points=100)
    for name, minutes, wrong in (("ali", 30, 1), ("bob", 60, 0)):
        u = User.objects.create_user(name, password="x")
        Participation.objects.create(user=u, contest=c)
        for i in range(wrong):
            s = Submission.objects.create(user=u, problem=problem_a, contest=c, language=python, source="x",
                                          verdict="WA")
            Submission.objects.filter(pk=s.pk).update(created=c.start + timezone.timedelta(minutes=minutes - 5))
        s = Submission.objects.create(user=u, problem=problem_a, contest=c, language=python, source="x",
                                      verdict="AC")
        Submission.objects.filter(pk=s.pk).update(created=c.start + timezone.timedelta(minutes=minutes))
    problem_a.is_public = True
    problem_a.save()
    return c


@pytest.mark.django_db
def test_virtual_start_rules(client, past_contest):
    from .models import VirtualParticipation

    url = reverse("contests:virtual", args=[past_contest.pk])
    client.force_login(User.objects.get(username="ali"))
    assert client.post(url).status_code == 400  # took part for real
    vali = User.objects.create_user("vali", password="x")
    client.force_login(vali)
    Contest.objects.filter(pk=past_contest.pk).update(published_at=None)
    assert client.post(url).status_code == 400  # not published: its problems may still be hidden
    Contest.objects.filter(pk=past_contest.pk).update(published_at=timezone.now())
    assert client.post(url).status_code == 302
    assert client.post(url).status_code == 400  # once
    assert VirtualParticipation.objects.filter(user=vali).count() == 1


@pytest.mark.django_db
@patch("apps.submissions.views.django_rq.enqueue")
def test_virtual_run_tags_submissions_and_ranks_among_real_participants(enqueue, client, past_contest, problem_a):
    from .models import VirtualParticipation
    from .virtual import virtual_result

    vali = User.objects.create_user("vali", password="x")
    client.force_login(vali)
    client.post(reverse("contests:virtual", args=[past_contest.pk]))
    vp = VirtualParticipation.objects.get(user=vali)
    client.post(reverse("submissions:submit", args=[problem_a.slug]), {"language": "python", "source": "x"})
    s = Submission.objects.get(user=vali)
    assert s.virtual == vp and s.contest is None
    Submission.objects.filter(pk=s.pk).update(verdict="AC", created=vp.start + timezone.timedelta(minutes=45))

    res = virtual_result(vp)
    # ali: 30 min + 20 for the WA = 50; bob: 60; vali: 45 from the virtual start -> 1st of 2
    assert (res["score"], res["penalty"], res["rank"], res["field"]) == (100, 45, 1, 2)
    assert res["cells"][0]["time"] == "00:45"
    page = client.get(reverse("contests:detail", args=[past_contest.pk])).content.decode()
    assert "1-o‘rin" in page and "Virtual" in page

    VirtualParticipation.objects.filter(pk=vp.pk).update(start=timezone.now() - timezone.timedelta(hours=3))
    client.post(reverse("submissions:submit", args=[problem_a.slug]), {"language": "python", "source": "y"})
    assert Submission.objects.filter(user=vali).latest("id").virtual is None  # the window is over: practice


@pytest.mark.django_db
def test_live_contest_shows_your_place_on_the_list_and_at_home(client, contest, python, problem_a):
    """The live hero and the home strip read the place and progress from the standings."""
    cache.clear()  # standings are cached per contest id, and ids repeat between tests
    ali, bob = User.objects.create_user("ali", password="x"), User.objects.create_user("bob", password="x")
    for u in (ali, bob):
        Participation.objects.create(user=u, contest=contest)
    _sub(bob, problem_a, contest, python, "AC", 5)
    client.force_login(ali)
    live = client.get(reverse("contests:list")).context["running"][0]
    assert (live.my_rank, live.my_solved, live.n_problems) == (2, 0, 2)
    _sub(ali, problem_a, contest, python, "AC", 3)  # faster than bob: first
    cache.delete(f"contest-standings-{contest.pk}")
    r = client.get(reverse("contests:list"))
    assert (r.context["running"][0].my_rank, r.context["running"][0].my_solved) == (1, 1)
    assert "1-o‘rin" in r.content.decode()
    home = client.get("/")
    assert home.context["live"]["rank"] == 1 and home.context["live"]["solved"] == 1
    assert "Davom etish" in home.content.decode()


def test_standings_live_poll_gets_only_the_table_and_counts_skip_disqualified(client, contest, problem_a, python):
    cache.clear()
    ali = User.objects.create_user("ali", password="x")
    bob = User.objects.create_user("bob", password="x")
    Participation.objects.create(user=ali, contest=contest)
    Participation.objects.create(user=bob, contest=contest, disqualified=True)
    _sub(ali, problem_a, contest, python, "AC", 5)
    _sub(bob, problem_a, contest, python, "AC", 6)
    client.force_login(bob)
    url = reverse("contests:standings", args=[contest.pk])

    page = client.get(url)
    body = page.content.decode()
    assert "<html" in body and 'id="st-live"' in body and 'hx-trigger="every 20s' in body
    a = next(cp for cp in page.context["problems"] if cp.label == "A")
    assert (a.n_solved, a.n_tried) == (1, 1)  # bob's AC is shown in his row, not counted
    assert "diskvalifikatsiya" in body  # bob's pinned line says so instead of a plain rank

    poll = client.get(url, HTTP_HX_REQUEST="true").content.decode()
    assert poll.lstrip().startswith("<div id=\"st-live\"") and "<html" not in poll and "ca-nav" not in poll


def test_a_problem_added_mid_contest_gets_its_column_without_waiting_for_the_cache(client, contest, author, python, problem_a):
    """The standings are cached for 30 s; adding a problem must not serve rows with a cell missing."""
    ali = User.objects.create_user("ali", password="x")
    Participation.objects.create(user=ali, contest=contest)
    _sub(ali, problem_a, contest, python, "AC", 5)
    client.force_login(ali)
    assert client.get(reverse("contests:standings", args=[contest.pk])).status_code == 200  # now cached
    extra = Problem.objects.create(slug="c", title="C", statement_md="x", author=author, is_public=False)
    ContestProblem.objects.create(contest=contest, problem=extra, label="C", order=2, points=100)

    page = client.get(reverse("contests:detail", args=[contest.pk]))
    assert page.status_code == 200 and [cp.label for cp in page.context["problems"]] == ["A", "B", "C"]
    table = client.get(reverse("contests:standings", args=[contest.pk]))
    assert table.status_code == 200 and len(table.context["rows"][0]["cells"]) == 3


@pytest.mark.django_db
def test_add_class_contests_creates_two_contests_with_hidden_problems_once():
    User.objects.create_superuser("admin", password="x")
    call_command("add_class_contests", stdout=StringIO())
    call_command("add_class_contests", stdout=StringIO())  # re-run: nothing new
    assert Contest.objects.count() == 2
    ca4, mini = Contest.objects.get(title="CodeArena #4"), Contest.objects.get(title="Mini Contest #1")
    assert (timezone.localtime(ca4.start).strftime("%H:%M"), ca4.duration_label) == ("11:45", "1 soat")
    assert timezone.localtime(mini.start).strftime("%H:%M") == "15:10"
    assert [cp.points for cp in ca4.contest_problems.all()] == [100, 100, 100, 200, 200, 200, 300, 300]
    assert [cp.label for cp in mini.contest_problems.all()] == list("ABCD")
    problems = Problem.objects.filter(contests__in=[ca4, mini])
    assert problems.count() == 12 and not problems.exclude(is_public=False, ml_mb=64).exists()
    assert all(p.testcases.filter(is_sample=True).count() == 2 for p in problems)
    assert all(p.testcases.count() >= 20 for p in problems.filter(slug__startswith="ca4-"))



@pytest.mark.django_db
def test_add_codearena_weekend_1_attaches_seven_hidden_problems_with_cf_points_once():
    User.objects.create_superuser("admin", password="x")
    start = timezone.now() + timedelta(hours=3)
    c = Contest.objects.create(title="CodeArena Weekend #1", start=start, end=start + timedelta(hours=3),
                               type=Contest.Type.CF)
    call_command("add_codearena_weekend_1", stdout=StringIO())
    call_command("add_codearena_weekend_1", stdout=StringIO())  # re-run: nothing new
    cps = list(c.contest_problems.select_related("problem"))
    assert [(cp.label, cp.points) for cp in cps] == [
        ("A", 250), ("B", 250), ("C", 500), ("D", 750), ("E", 1000), ("F", 1000), ("G", 1250)]
    assert [cp.problem.difficulty for cp in cps] == ["beginner"] * 3 + ["easy"] * 3 + ["medium"]
    assert not any(cp.problem.is_public for cp in cps)
    assert all(cp.problem.testcases.filter(is_sample=True).count() == 2 for cp in cps)

# ---- official rating ------------------------------------------------------------------------------

def _official(title, hours_ago, problem, python, users_solving, users_trying=()):
    c = _rated_contest(title, hours_ago, problem, python, users_solving, users_trying)
    Contest.objects.filter(pk=c.pk).update(is_official=True, official_applied_at=timezone.now())
    return c


def _verified(*names):
    return [User.objects.create_user(n, password="x", verified_at=timezone.now()) for n in names]


@pytest.mark.django_db
def test_recalc_official_rates_only_verified_users_and_reranks_without_the_rest(problem_a, python):
    from .rating import RAMP, recalc_official

    ali, bob = _verified("ali", "bob")
    anon = User.objects.create_user("anon", password="x")  # not verified: open rating only
    c = _official("Lab", 1, problem_a, python, [anon, ali], [bob])
    recalc_official()

    for u in (ali, bob, anon):
        u.refresh_from_db()
    assert anon.official_rating is None and anon.rating == 0
    rows = {p.user_id: p for p in Participation.objects.filter(contest=c)}
    assert rows[anon.pk].official_after is None
    # ali was 2nd overall but 1st of the verified pair: a 2-person win, not a mid-table result.
    # Both are newcomers, so the first bonus (RAMP[0]) comes on top of the change.
    assert rows[ali.pk].official_before == 0 and ali.official_rating == rows[ali.pk].official_after > RAMP[0]
    assert bob.official_rating < RAMP[0]


@pytest.mark.django_db
def test_recalc_official_replays_in_end_order_and_is_repeatable(problem_a, python):
    from .rating import recalc_official

    ali, bob = _verified("ali", "bob")
    first = _official("First", 10, problem_a, python, [ali], [bob])
    second = _official("Second", 1, problem_a, python, [bob], [ali])
    Contest.objects.create(title="Not applied", is_official=True, start=first.start, end=first.end)
    recalc_official()
    once = dict(User.objects.values_list("username", "official_rating"))
    recalc_official()

    assert dict(User.objects.values_list("username", "official_rating")) == once
    p1 = Participation.objects.get(contest=first, user=ali)
    p2 = Participation.objects.get(contest=second, user=ali)
    assert p2.official_before == p1.official_after  # the chain carries from the older contest


@pytest.mark.django_db
def test_recalc_official_drops_a_contest_that_is_no_longer_official(problem_a, python):
    from .rating import recalc_official

    ali, bob = _verified("ali", "bob")
    c = _official("Lab", 1, problem_a, python, [ali], [bob])
    recalc_official()
    Contest.objects.filter(pk=c.pk).update(is_official=False)
    call_command("recalc_official", stdout=StringIO())

    ali.refresh_from_db()
    assert ali.official_rating is None
    assert Participation.objects.get(contest=c, user=ali).official_after is None


@pytest.fixture
def staff_client(client, db):
    client.force_login(User.objects.create_user("boss", password="x", is_staff=True))
    return client


def _online_official(problem, python, solving, trying=(), top_n=2):
    c = _rated_contest("Online", 1, problem, python, solving, trying)
    Contest.objects.filter(pk=c.pk).update(is_official=True, review_top_n=top_n)
    c.refresh_from_db()
    return c


@pytest.mark.django_db
def test_online_official_needs_top_n_explained_before_apply(staff_client, problem_a, python):
    from apps.integrity.models import AuditEntry

    from .rating import RAMP

    ali, bob, zarina = _verified("ali", "bob", "zarina")
    anon = User.objects.create_user("anon", password="x")
    c = _online_official(problem_a, python, [anon, ali, bob], [zarina])
    page = reverse("moderation:contest_official", args=[c.pk])
    apply = reverse("moderation:contest_apply_official", args=[c.pk])

    body = staff_client.get(page).content.decode()
    assert "ali" in body and "bob" in body and "zarina" not in body  # top 2 of the verified, anon skipped
    r = staff_client.post(apply, follow=True)
    assert "2 ta ishtirokchi hali tekshirilmagan" in r.content.decode()
    c.refresh_from_db()
    assert c.official_applied_at is None

    staff_client.post(reverse("moderation:contest_review", args=[c.pk, ali.pk]), {"reviewed": "1"})
    # bob can't explain his code: DQ pulls zarina into the top 2, who must be checked too
    staff_client.post(reverse("contests:disqualify", args=[c.pk, bob.pk]), {"disqualified": "1", "back": "official"})
    assert "zarina" in staff_client.get(page).content.decode()
    staff_client.post(apply)
    c.refresh_from_db()
    assert c.official_applied_at is None

    staff_client.post(reverse("moderation:contest_review", args=[c.pk, zarina.pk]), {"reviewed": "1"})
    staff_client.post(apply)
    c.refresh_from_db()
    ali.refresh_from_db()
    assert c.official_applied_at is not None and ali.official_rating > RAMP[0]
    assert AuditEntry.objects.filter(contest=c, action="official_review").count() == 2
    assert AuditEntry.objects.filter(contest=c, action="official_apply").exists()


@pytest.mark.django_db
def test_lab_contest_and_top_n_zero_apply_without_review(staff_client, problem_a, python):
    ali, bob = _verified("ali", "bob")
    lab = _online_official(problem_a, python, [ali], [bob])
    Contest.objects.filter(pk=lab.pk).update(allowed_ip_prefix="10.0.")
    staff_client.post(reverse("moderation:contest_apply_official", args=[lab.pk]))
    lab.refresh_from_db()
    assert lab.official_applied_at is not None

    old = _online_official(problem_a, python, [bob], [ali], top_n=0)  # a past contest marked afterwards
    staff_client.post(reverse("moderation:contest_apply_official", args=[old.pk]))
    old.refresh_from_db()
    assert old.official_applied_at is not None


@pytest.mark.django_db
def test_apply_official_refuses_unofficial_or_running_contest(staff_client, contest):
    staff_client.post(reverse("moderation:contest_apply_official", args=[contest.pk]))
    Contest.objects.filter(pk=contest.pk).update(is_official=True)
    staff_client.post(reverse("moderation:contest_apply_official", args=[contest.pk]))
    contest.refresh_from_db()
    assert contest.official_applied_at is None


@pytest.mark.django_db
def test_dq_after_official_apply_rebuilds_official_rating(staff_client, problem_a, python):
    cheat, ali = _verified("cheat", "ali")
    c = _official("Lab", 1, problem_a, python, [cheat, ali])
    from .rating import RAMP, recalc_official
    recalc_official()
    cheat.refresh_from_db()
    assert cheat.official_rating > RAMP[0]  # newcomer: the first bonus plus a win

    r = staff_client.post(reverse("contests:disqualify", args=[c.pk, cheat.pk]), {"disqualified": "1"}, follow=True)
    cheat.refresh_from_db()
    assert cheat.official_rating < RAMP[0]
    assert "Rasmiy reyting qayta hisoblandi" in r.content.decode()


@pytest.mark.django_db
def test_teacher_verifies_own_student_and_past_official_contest_counts(client, problem_a, python):
    from apps.accounts.models import Group
    from apps.integrity.models import AuditEntry

    from .rating import RAMP

    teacher = User.objects.create_user("ustoz", password="x", role="teacher")
    stranger = User.objects.create_user("begona", password="x", role="teacher")
    (ali,) = _verified("ali")
    student = User.objects.create_user("talaba", password="x")
    Group.objects.create(name="CS-1", teacher=teacher).members.add(student)
    _official("Lab", 1, problem_a, python, [student], [ali])
    url = reverse("verify_user", args=[student.pk])

    client.force_login(stranger)
    assert client.post(url, {"verified": "1"}).status_code == 403
    client.force_login(teacher)
    client.post(url, {"verified": "1", "note": "Pasport ko‘rildi"})
    student.refresh_from_db()
    assert student.verified_by == teacher and student.verified_note == "Pasport ko‘rildi"
    assert student.official_rating > RAMP[0]  # the lab contest before verification now counts
    assert AuditEntry.objects.filter(action="verify", subject=student, actor=teacher).exists()

    client.post(url, {"verified": "0"})
    student.refresh_from_db()
    assert student.verified_at is None and student.official_rating is None


# ---- a round's submissions, for staff -------------------------------------------------------------

@pytest.mark.django_db
def test_staff_see_a_running_rounds_submissions(client, contest, problem_a, problem_b, python):
    ali = User.objects.create_user("ali", password="x")
    Participation.objects.create(user=ali, contest=contest)
    _sub(ali, problem_a, contest, python, "WA", 5, passed=2)
    _sub(ali, problem_b, contest, python, "AC", 30)
    page = reverse("contests:submissions", args=[contest.pk])

    # the public status page hides a running round from everyone else, and so does this list
    client.force_login(User.objects.create_user("bob", password="x"))
    assert client.get(reverse("submissions:mine")).context["subs"].paginator.count == 0
    assert client.get(page).status_code in (302, 403)

    client.force_login(User.objects.create_user("boss", password="x", is_staff=True))
    assert client.get(reverse("submissions:mine")).context["subs"].paginator.count == 2
    r = client.get(page)
    assert [(s.label, s.verdict, s.elapsed) for s in r.context["page"]] == [("B", "AC", "00:30"), ("A", "WA", "00:05")]
    assert 'aria-current="page">Urinishlar</a>' in r.content.decode()  # the round's own tab
    assert [s.label for s in client.get(page + "?problem=A&user=ali").context["page"]] == ["A"]
    assert [s.label for s in client.get(page + "?verdict=AC").context["page"]] == ["B"]
    # while the round runs the table re-fetches itself; that request gets the table alone
    live = client.get(page, headers={"HX-Request": "true"})
    assert [t.name for t in live.templates][0] == "contests/_submissions_live.html"


@pytest.mark.django_db
def test_a_standings_cell_opens_its_submissions_for_staff_only(client, contest, problem_a, python):
    ali = User.objects.create_user("ali", password="x")
    Participation.objects.create(user=ali, contest=contest)
    _sub(ali, problem_a, contest, python, "AC", 12)
    link = f'{reverse("contests:submissions", args=[contest.pk])}?user=ali&amp;problem=A'
    standings = reverse("contests:standings", args=[contest.pk])
    client.force_login(ali)
    assert link not in client.get(standings).content.decode()
    client.force_login(User.objects.create_user("boss", password="x", is_staff=True))
    assert link in client.get(standings).content.decode()


# ---- voiding one problem ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_voiding_one_problem_keeps_the_rest_of_the_round_and_is_silent(client, contest, problem_a, problem_b, python):
    from apps.integrity.models import AuditEntry

    ali, bob = User.objects.create_user("ali", password="x"), User.objects.create_user("bob", password="x")
    for u in (ali, bob):
        Participation.objects.create(user=u, contest=contest)
    _sub(ali, problem_a, contest, python, "WA", 3, passed=1)
    _sub(ali, problem_a, contest, python, "AC", 10)
    _sub(ali, problem_b, contest, python, "AC", 20)
    _sub(bob, problem_a, contest, python, "AC", 5)
    url = reverse("contests:void", args=[contest.pk, ali.pk])

    def scores():
        return {r["user"].username: (r["rank"], r["score"]) for r in compute_standings(contest)}

    assert scores() == {"ali": (1, 200), "bob": (2, 100)}

    client.force_login(ali)  # only staff strike a result
    client.post(url, {"label": "A", "voided": "1"})
    assert scores()["ali"] == (1, 200)

    client.force_login(User.objects.create_user("boss", password="x", is_staff=True))
    client.post(url, {"label": "A", "voided": "1", "reason": "ko‘chirilgan"})
    client.post(url, {"label": "A", "voided": "1", "reason": "again"})  # a stale second click changes nothing
    row = next(r for r in compute_standings(contest) if r["user"] == ali)
    # A is untried now (no points, no wrong try); B and the rest of the round stand
    assert row["cells"][0] == {"solved": False, "wrong": 0, "minutes": None, "ac_at": None, "voided": True,
                               "penalty": False, "first": False}
    assert row["cells"][1]["solved"] and row["attempted"]
    assert scores() == {"bob": (1, 100), "ali": (2, 100)}  # equal points: bob's lower penalty first
    assert [(e.action, e.note) for e in AuditEntry.objects.filter(contest=contest)] == [("void", "A: ko‘chirilgan")]

    # nothing tells the participant or the public: the cell is just empty
    client.force_login(ali)
    page = client.get(reverse("contests:standings", args=[contest.pk])).content.decode()
    assert "Bekor qilingan" not in page and "ko‘chirilgan" not in page
    assert "Bekor qilingan" not in client.get(reverse("contests:detail", args=[contest.pk])).content.decode()

    client.force_login(User.objects.get(username="boss"))
    page = client.get(reverse("contests:submissions", args=[contest.pk]) + "?user=ali").content.decode()
    assert "Bekor qilingan" in page and "ko‘chirilgan" in page  # staff see it, with the reason
    client.post(url, {"label": "A", "voided": "0"})
    assert scores() == {"ali": (1, 200), "bob": (2, 100)}
    assert AuditEntry.objects.filter(contest=contest, action="unvoid", note="A").exists()


@pytest.mark.django_db
def test_voiding_after_publish_takes_that_practice_solve_back(client, problem_a, problem_b, python):
    staff = User.objects.create_user("boss", password="x", is_staff=True)
    ali = User.objects.create_user("ali", password="x")
    c = Contest.objects.create(title="Past", start=timezone.now() - timezone.timedelta(hours=3),
                               end=timezone.now() - timezone.timedelta(hours=2))
    ContestProblem.objects.create(contest=c, problem=problem_a, label="A")
    ContestProblem.objects.create(contest=c, problem=problem_b, label="B")
    Participation.objects.create(user=ali, contest=c)
    for p in (problem_a, problem_b):
        Submission.objects.create(user=ali, problem=p, contest=c, language=python, source="x", verdict="AC")
    client.force_login(staff)
    client.post(reverse("moderation:contest_publish", args=[c.pk]))
    assert set(ali.userproblemsolved_set.values_list("problem__slug", flat=True)) == {"a", "b"}

    url = reverse("contests:void", args=[c.pk, ali.pk])
    r = client.post(url, {"label": "A", "voided": "1", "next": reverse("integrity:contest_report", args=[c.pk])})
    assert r.url == reverse("integrity:contest_report", args=[c.pk])  # back where the click came from
    assert set(ali.userproblemsolved_set.values_list("problem__slug", flat=True)) == {"b"}
    assert client.post(url, {"label": "A", "voided": "0", "next": "https://evil.example/"}).url == reverse(
        "contests:standings", args=[c.pk])  # never off the site
    assert set(ali.userproblemsolved_set.values_list("problem__slug", flat=True)) == {"a", "b"}


@pytest.mark.django_db
def test_voiding_after_rating_recomputes_the_latest_contest(client, problem_a, python, veteran):
    from .rating import apply_rating

    cheat, ali = veteran("cheat", 1200), veteran("ali", 1200)
    c = _rated_contest("Final", 1, problem_a, python, [cheat, ali])
    apply_rating(c)
    assert Participation.objects.get(contest=c, user=cheat).rank == 1
    client.force_login(User.objects.create_user("boss", password="x", is_staff=True))
    r = client.post(reverse("contests:void", args=[c.pk, cheat.pk]), {"label": "A", "voided": "1"}, follow=True)
    rows = {p.user_id: p for p in Participation.objects.filter(contest=c)}
    assert rows[ali.pk].rank == 1 and rows[cheat.pk].rank == 2  # cheat still rated: took part, solved nothing
    cheat.refresh_from_db()
    assert cheat.rating == rows[cheat.pk].rating_after < 1200
    assert "Reyting qayta hisoblandi" in r.content.decode()


@pytest.mark.django_db
@patch("apps.submissions.views.django_rq.enqueue")
def test_ai_penalty_returns_the_solution_as_a_wrong_try_and_blocks_the_problem(enqueue, client, contest, problem_a, problem_b, python):
    from apps.integrity.models import AuditEntry

    ali, bob = User.objects.create_user("ali", password="x"), User.objects.create_user("bob", password="x")
    for u in (ali, bob):
        Participation.objects.create(user=u, contest=contest)
    _sub(ali, problem_a, contest, python, "WA", 2, passed=1)
    _sub(ali, problem_a, contest, python, "AC", 10)
    _sub(ali, problem_b, contest, python, "AC", 20)
    _sub(bob, problem_a, contest, python, "AC", 5)
    url = reverse("contests:void", args=[contest.pk, ali.pk])
    staff = User.objects.create_user("boss", password="x", is_staff=True)

    def row():
        return next(r for r in compute_standings(contest) if r["user"] == ali)

    assert row()["cells"][0]["solved"] and row()["cells"][0]["wrong"] == 1

    client.force_login(ali)  # only staff strike a result
    client.post(url, {"label": "A", "voided": "1", "penalty": "1"})
    assert row()["cells"][0]["solved"]

    client.force_login(staff)
    client.post(url, {"label": "A", "voided": "1", "penalty": "1", "reason": "AI ishlatgan"})
    client.post(url, {"label": "A", "voided": "1", "penalty": "1"})  # a stale second click changes nothing
    # the cancelled solution is returned as a wrong try, on top of the earlier WA;
    # B and the rest of the round stand
    assert row()["cells"][0] == {"solved": False, "wrong": 2, "minutes": None, "ac_at": None,
                                 "voided": True, "penalty": True, "first": False}
    assert row()["cells"][1]["solved"]
    assert [(e.action, e.note) for e in AuditEntry.objects.filter(contest=contest)] == [
        ("penalty", "A: AI ishlatgan")]

    # blocked: no more submissions to A until the round ends; the rest of the round stays open
    client.force_login(ali)
    assert client.post(reverse("submissions:submit", args=[problem_a.slug]),
                       {"language": "python", "source": "print(1)"}).status_code == 400
    assert client.post(reverse("submissions:submit", args=[problem_b.slug]),
                       {"language": "python", "source": "print(1)"}).status_code == 302
    # the problem page says so and locks the submit bar
    assert "Bu masala siz uchun bloklangan" in client.get(
        reverse("problems:detail", args=[problem_a.slug])).content.decode()
    # silent otherwise: the board shows a plain wrong try, no mention of the penalty
    assert "AI jarimasi" not in client.get(reverse("contests:standings", args=[contest.pk])).content.decode()

    client.force_login(staff)
    page = client.get(reverse("contests:submissions", args=[contest.pk]) + "?user=ali").content.decode()
    assert "AI jarimasi" in page and "xato urinish hisoblandi, masala bloklangan" in page
    # restore: the solve and the access come back
    client.post(url, {"label": "A", "voided": "0"})
    assert row()["cells"][0]["solved"] and row()["cells"][0]["wrong"] == 1
    client.force_login(ali)
    assert client.post(reverse("submissions:submit", args=[problem_a.slug]),
                       {"language": "python", "source": "print(2)"}).status_code == 302
    assert AuditEntry.objects.filter(contest=contest, action="unvoid", note="A").exists()


# ---- CodeArena Marathon #1 and round badges --------------------------------------------------------

@pytest.mark.django_db
def test_add_codearena_marathon_1_creates_an_unrated_48_hour_round_of_ten_hidden_problems_once(client):
    User.objects.create_superuser("admin", password="x")
    with pytest.raises(CommandError):  # no round yet, and no start to create it with
        call_command("add_codearena_marathon_1", stdout=StringIO())
    start = (timezone.localtime() + timedelta(days=3)).replace(hour=18, minute=0, second=0, microsecond=0)
    call_command("add_codearena_marathon_1", start=start.strftime("%Y-%m-%d %H:%M"), stdout=StringIO())
    call_command("add_codearena_marathon_1", stdout=StringIO())  # re-run: the same round, nothing new

    c = Contest.objects.get(title="CodeArena Marathon #1")
    assert c.start == start and c.end - c.start == timedelta(hours=48)
    assert (c.type, c.is_rated, c.division, c.badge) == ("score", False, 0, "Marathon #1")
    cps = list(c.contest_problems.select_related("problem"))
    assert [cp.label for cp in cps] == list("ABCDEFGHIJ")
    assert [cp.points for cp in cps] == [100, 100, 200, 200, 250, 300, 350, 400, 500, 500]
    assert [cp.problem.difficulty for cp in cps] == ["beginner"] * 2 + ["easy"] * 3 + ["medium"] * 3 + ["hard"] * 2
    assert not any(cp.problem.is_public for cp in cps)
    assert all(cp.problem.testcases.count() >= 20 and cp.problem.testcases.filter(is_sample=True).count() == 2
               for cp in cps)
    page = client.get(reverse("contests:detail", args=[c.pk])).content.decode()
    assert "Musobaqa haqida" in page and "48 soatlik marafon" in page  # its description, rendered
    assert "Reytingsiz" in page and "«Marathon #1» nishoni" in page


@pytest.mark.django_db
def test_a_published_round_with_a_badge_marks_its_solvers_profiles(client, problem_a, problem_b, python):
    now = timezone.now()
    c = Contest.objects.create(title="Marathon", badge="Marathon #1", start=now - timedelta(hours=3),
                               end=now - timedelta(hours=1))
    ContestProblem.objects.create(contest=c, problem=problem_a, label="A", order=0, points=100)
    ContestProblem.objects.create(contest=c, problem=problem_b, label="B", order=1, points=100)
    users = {n: User.objects.create_user(n, password="x") for n in ("first", "second", "third", "fourth", "none", "cheat")}
    for u in users.values():
        Participation.objects.create(user=u, contest=c)
    _sub(users["first"], problem_a, c, python, "AC", 5)
    _sub(users["first"], problem_b, c, python, "AC", 6)
    for name, minutes in (("second", 10), ("third", 20), ("fourth", 30)):
        _sub(users[name], problem_a, c, python, "AC", minutes)
    _sub(users["none"], problem_a, c, python, "WA", 7, passed=1)
    _sub(users["cheat"], problem_a, c, python, "AC", 1)
    _sub(users["cheat"], problem_b, c, python, "AC", 2)
    Participation.objects.filter(user=users["cheat"]).update(disqualified=True)

    def badges(name):
        return client.get(reverse("profile", args=[name])).context["contest_badges"]
    assert badges("first") == []  # results are final once staff publish the round
    Contest.objects.filter(pk=c.pk).update(published_at=now)
    cache.clear()
    assert [(b["name"], b["medal"], b["solved"], b["total"]) for b in badges("first")] == [("Marathon #1", 1, 2, 2)]
    assert [b["medal"] for b in badges("third")] == [3]
    assert [(b["medal"], b["solved"]) for b in badges("fourth")] == [(None, 1)]
    assert badges("none") == [] and badges("cheat") == []
    page = client.get(reverse("profile", args=["fourth"])).content.decode()
    assert "Marathon #1 · 1/2" in page and "ca-badge-contest" in page
    assert "ca-badge-medal-1" in client.get(reverse("profile", args=["first"])).content.decode()


def test_calendar_file_is_the_round_with_a_reminder_an_hour_before(client, contest):
    """«Kalendarga qo‘shish» on the round's cover: one event any calendar app opens, no account needed."""
    r = client.get(reverse("contests:calendar", args=[contest.pk]))
    body = r.content.decode()
    assert r.status_code == 200 and r["Content-Type"].startswith("text/calendar")
    assert "attachment" in r["Content-Disposition"]
    assert body.count("BEGIN:VEVENT") == 1 and "SUMMARY:Sprint" in body and "TRIGGER:-PT1H" in body
    import datetime
    assert f"DTSTART:{contest.start.astimezone(datetime.timezone.utc):%Y%m%dT%H%M%SZ}" in body
    assert f"/contests/{contest.pk}/" in body
