from io import StringIO

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


def _sub(user, problem, contest, python, verdict, minutes_after_start):
    s = Submission.objects.create(user=user, problem=problem, contest=contest, language=python,
                                  source="x", verdict=verdict)
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


def test_recalc_rating_favorite_win_has_small_delta(ended_rated_contest, problem_a, python):
    """Unequal ratings: 1800 favorite finishing 1st vs 1200 underdog 2nd —
    favorite's gain must be small (performance ≈ seed expectation)."""
    from apps.contests.management.commands.recalc_rating import _expected_seed

    favorite = User.objects.create_user("fav", password="x", rating=1800)
    underdog = User.objects.create_user("dog", password="x", rating=1200)
    Participation.objects.create(user=favorite, contest=ended_rated_contest)
    Participation.objects.create(user=underdog, contest=ended_rated_contest)
    _sub(favorite, problem_a, ended_rated_contest, python, "AC", 5)
    _sub(underdog, problem_a, ended_rated_contest, python, "WA", 7)

    # Seed for favorite (higher rating) must be better (lower) than underdog's.
    ratings = [1800, 1200]
    assert _expected_seed(0, ratings) < _expected_seed(1, ratings)

    call_command("recalc_rating", ended_rated_contest.pk, stdout=StringIO())

    favorite.refresh_from_db()
    underdog.refresh_from_db()
    assert favorite.rating > 1800
    assert favorite.rating - 1800 < 60  # vs +226 for an upset win in an equal field
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


def test_tied_results_share_rank_and_rating_delta(ended_rated_contest, problem_a, python):
    """Same solved+penalty -> same rank ("1, 1, 3") and identical rating change; the
    arbitrary sort order between equals must not decide who gains and who loses."""
    users = [User.objects.create_user(f"u{i}", password="x", rating=1500) for i in range(3)]
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


def test_rating_gain_scales_with_solved_fraction():
    """Same rank, more solved -> bigger gain (margin of victory); losses are damped."""
    from apps.contests.management.commands.recalc_rating import rating_delta
    full = rating_delta(seed=8, rank=1, n=15, k=150, solved_frac=1.0)
    partial = rating_delta(seed=8, rank=1, n=15, k=150, solved_frac=0.9)
    assert full > partial > 0
    loss = rating_delta(seed=8, rank=15, n=15, k=150, solved_frac=0.0)
    assert -full < loss < 0


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
    assert "#2" in html and "Sizning o‘rningiz" in html  # bob solved A earlier -> lower penalty
    assert 'title="Yechilgan 10:00"' in html
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
    assert r.status_code == 302  # staff_required redirects to login
    clar.refresh_from_db()
    assert clar.answer == ""


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
    r = client.post(reverse("contests:disqualify", args=[c.pk, a.pk]), {"reason": "paste"})
    assert r.status_code == 302
    rows = compute_standings(c)
    assert [r["user"] for r in rows] == [b, a] and rows[1]["disqualified"] and rows[1]["rank"] == 2

    client.force_login(a)
    r = client.post(reverse("submissions:submit", args=["p"]), {"language": "python", "source": "print(1)"})
    assert r.status_code == 400

    client.force_login(staff)
    client.post(reverse("contests:disqualify", args=[c.pk, a.pk]))
    assert [r["user"] for r in compute_standings(c)] == [a, b]


@pytest.mark.django_db
def test_disqualify_requires_staff(client):
    from django.utils import timezone

    from apps.accounts.models import User

    u = User.objects.create_user("u", password="x")
    c = Contest.objects.create(title="C", start=timezone.now(), end=timezone.now() + timezone.timedelta(hours=1))
    client.force_login(u)
    assert client.post(reverse("contests:disqualify", args=[c.pk, u.pk])).status_code == 302


def test_rating_delta_classroom_scale():
    """15 newbies at 1200: full-solve winner +226, 8th +1, last -74 (losses halved)."""
    from apps.contests.management.commands.recalc_rating import _expected_seed, rating_delta

    ratings = [1200] * 15
    seed = _expected_seed(0, ratings)  # 8.0 for an all-equal field
    assert rating_delta(seed, 1, 15, 150, 1.0) == 226
    assert rating_delta(seed, 1, 15, 150, 0.2) == 106  # same rank, 1/5 solved: smaller gain
    assert rating_delta(seed, 8, 15, 150, 0.5) == 1
    assert rating_delta(seed, 15, 15, 150, 0.0) == -74
