from io import StringIO

import pytest
from django.core.management import call_command, CommandError
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.problems.models import Language, Problem
from apps.submissions.models import Submission

from .models import Contest, ContestProblem, Participation
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


def _sub(user, problem, contest, python, verdict, minutes_after_start):
    s = Submission.objects.create(user=user, problem=problem, contest=contest, language=python,
                                  source="x", verdict=verdict)
    s.created = contest.start + timezone.timedelta(minutes=minutes_after_start)
    s.save(update_fields=["created"])
    return s


def test_icpc_ranks_by_solved_then_penalty(contest, problem_a, problem_b, python):
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


def test_icpc_more_solved_ranks_above_lower_penalty(contest, problem_a, problem_b, python):
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


def test_score_type_ranks_by_points_ties_by_last_ac(contest, problem_a, problem_b, python):
    contest.type = Contest.Type.SCORE
    contest.save()
    ali = User.objects.create_user("ali", password="x")
    bob = User.objects.create_user("bob", password="x")
    Participation.objects.create(user=ali, contest=contest)
    Participation.objects.create(user=bob, contest=contest)

    _sub(ali, problem_a, contest, python, "AC", 50)
    _sub(bob, problem_a, contest, python, "AC", 10)

    rows = compute_standings(contest)
    assert rows[0]["user"] == bob  # same score, earlier last AC wins
    assert rows[0]["score"] == rows[1]["score"] == 100


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
def test_standings_view_renders(client, contest):
    r = client.get(reverse("contests:standings", args=[contest.pk]))
    assert r.status_code == 200


@pytest.fixture
def ended_rated_contest(db, problem_a, problem_b):
    c = Contest.objects.create(title="Rated", is_rated=True,
                               start=timezone.now() - timezone.timedelta(hours=2),
                               end=timezone.now() - timezone.timedelta(hours=1))
    ContestProblem.objects.create(contest=c, problem=problem_a, label="A", order=0, points=100)
    ContestProblem.objects.create(contest=c, problem=problem_b, label="B", order=1, points=100)
    return c


def test_recalc_rating_applies_deltas_and_is_idempotent(ended_rated_contest, problem_a, python):
    winner = User.objects.create_user("winner", password="x", rating=1500)
    loser = User.objects.create_user("loser", password="x", rating=1500)
    Participation.objects.create(user=winner, contest=ended_rated_contest)
    Participation.objects.create(user=loser, contest=ended_rated_contest)
    _sub(winner, problem_a, ended_rated_contest, python, "AC", 5)

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


def test_recalc_rating_favorite_win_has_small_delta(ended_rated_contest, problem_a, python):
    """Unequal ratings: 1800 favorite finishing 1st vs 1200 underdog 2nd —
    favorite's gain must be small (performance ≈ seed expectation)."""
    from apps.contests.management.commands.recalc_rating import _expected_seed

    favorite = User.objects.create_user("fav", password="x", rating=1800)
    underdog = User.objects.create_user("dog", password="x", rating=1200)
    Participation.objects.create(user=favorite, contest=ended_rated_contest)
    Participation.objects.create(user=underdog, contest=ended_rated_contest)
    _sub(favorite, problem_a, ended_rated_contest, python, "AC", 5)

    # Seed for favorite (higher rating) must be better (lower) than underdog's.
    ratings = [1800, 1200]
    assert _expected_seed(0, ratings) < _expected_seed(1, ratings)

    call_command("recalc_rating", ended_rated_contest.pk, stdout=StringIO())

    favorite.refresh_from_db()
    underdog.refresh_from_db()
    assert favorite.rating > 1800
    assert favorite.rating - 1800 < 40
    assert underdog.rating < 1200


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
