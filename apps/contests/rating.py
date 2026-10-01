"""Elo-style contest rating: apply, and roll back for a recompute after a late DQ."""
from django.db import transaction
from django.db.models import F

from apps.accounts.models import User

from .models import Contest, Participation
from .standings import compute_standings

# Tuned for a classroom pool where everyone starts at 1200. Rank-based Elo (as on
# Codeforces/AtCoder) with a margin-of-victory twist borrowed from sports Elo: the
# gain is scaled by how much of the contest you solved, so a full solve at 1st place
# beats a 1-problem 1st place. Losses are damped by LOSS_FACTOR (students, not pros),
# which makes the system inflationary on purpose — the pool drifts up as people improve.
# In an all-1200 15-person field: 1st with full solve ≈ +225, last with 0 ≈ -75.
K_NEW, K_ESTABLISHED = 150, 90        # first 10 rated contests vs after
SCALE = 800                           # wider than classic Elo's 400 so gains don't stall at ~1600
PARTICIPATION_BONUS = 1               # every finisher gets this on top
GAIN_BASE = 0.5                       # gain multiplier = GAIN_BASE + solved fraction, i.e. 0.5..1.5
LOSS_FACTOR = 0.5                     # negative deltas are halved


def _expected_seed(idx, ratings):
    """Elo-style expected rank: 1 + sum of P(j beats i) for every other participant."""
    r_i = ratings[idx]
    return 1 + sum(
        1 / (1 + 10 ** ((r_i - ratings[j]) / SCALE))
        for j in range(len(ratings)) if j != idx
    )


def rating_delta(seed: float, rank: float, n: int, k: int, solved_frac: float = 1.0) -> int:
    """Elo part is normalised so that in an all-equal field 1st place is +k and last
    is -k whatever the contest size; then scaled by margin of victory (gains) or
    damped (losses)."""
    elo = k * 2 * (seed - rank) / max(n - 1, 1)
    factor = (GAIN_BASE + solved_frac) if elo > 0 else LOSS_FACTOR
    return round(elo * factor) + PARTICIPATION_BONUS


def _rated_rows(contest) -> list:
    # Registered but never submitted = didn't take part; rated only if you played
    # (Codeforces/AtCoder rule). Disqualified stays in: ranking last is the penalty.
    return [r for r in compute_standings(contest) if r["attempted"] or r["disqualified"]]


def _new_ratings(contest, rows, ratings, past_rated) -> list[int]:
    """Elo over `rows` (standings order), each starting from `ratings[i]` with `past_rated[i]`
    earlier rated contests behind it."""
    # Ranks are recounted inside `rows`, which may be a subset of the standings (official
    # rating skips unverified users). Tied rows get the tie group's mean position
    # (AtCoder convention) so a group at 3rd-6th is rated as 4.5, not all as 3.
    first, size = {}, {}
    for i, r in enumerate(rows):
        first.setdefault(r["rank"], i + 1)
        size[r["rank"]] = size.get(r["rank"], 0) + 1
    max_score = sum(cp.points for cp in contest.contest_problems.all()) or 1
    out = []
    for i, row in enumerate(rows):
        k = K_NEW if past_rated[i] < 10 else K_ESTABLISHED
        position = first[row["rank"]] + (size[row["rank"]] - 1) / 2
        out.append(ratings[i] + rating_delta(_expected_seed(i, ratings), position, len(rows), k,
                                             row["score"] / max_score))
    return out


def apply_rating(contest) -> bool:
    """Rate a finished contest once; False if it was already applied."""
    if contest.rating_applied:
        return False
    rows = _rated_rows(contest)
    users = [r["user"] for r in rows]
    for u in users:
        u.refresh_from_db(fields=["rating"])  # standings may come from an older read
    ratings = [u.rating for u in users]
    past = [Participation.objects.filter(user=u, rating_after__isnull=False).count() for u in users]
    new = _new_ratings(contest, rows, ratings, past)

    with transaction.atomic():
        for row, user, new_rating in zip(rows, users, new):
            p = row["participation"]
            p.rank, p.score, p.penalty = row["rank"], row["score"], row["penalty"]
            p.rating_before, p.rating_after = user.rating, new_rating
            p.save(update_fields=["rank", "score", "penalty", "rating_before", "rating_after"])

            user.rating = new_rating
            user.save(update_fields=["rating"])

        contest.rating_applied = True
        contest.save(update_fields=["rating_applied"])
    return True


OFFICIAL_START = 1200


def review_queue(contest) -> list:
    """Standings rows an online official contest must check before its official rating applies:
    the top `review_top_n` verified, not disqualified finishers. A DQ pulls the next one in."""
    if contest.allowed_ip_prefix or not contest.review_top_n:
        return []
    rows = [r for r in _rated_rows(contest) if r["user"].verified_at and not r["disqualified"]]
    return rows[:contest.review_top_n]


def recalc_official() -> None:
    """Rebuild every official rating from scratch: applied official contests in end order,
    verified users only. A full replay, so a late DQ, a late verification or un-marking a
    contest all come out right with no rollback bookkeeping."""
    current: dict[int, int] = {}
    played: dict[int, int] = {}
    with transaction.atomic():
        Participation.objects.filter(official_after__isnull=False).update(official_before=None, official_after=None)
        contests = Contest.objects.filter(is_official=True, official_applied_at__isnull=False).order_by("end", "pk")
        for contest in contests:
            rows = [r for r in _rated_rows(contest) if r["user"].verified_at]
            ratings = [current.get(r["user"].pk, OFFICIAL_START) for r in rows]
            new = _new_ratings(contest, rows, ratings, [played.get(r["user"].pk, 0) for r in rows])
            for row, before, after in zip(rows, ratings, new):
                p = row["participation"]
                p.official_before, p.official_after = before, after
                p.save(update_fields=["official_before", "official_after"])
                current[p.user_id] = after
                played[p.user_id] = played.get(p.user_id, 0) + 1
        User.objects.exclude(pk__in=current).filter(official_rating__isnull=False).update(official_rating=None)
        User.objects.bulk_update([User(pk=pk, official_rating=r) for pk, r in current.items()], ["official_rating"])


def is_latest(contest) -> bool:
    """True when none of the contest's rated participants was rated in a later contest,
    so undoing this contest's deltas can't break anyone's rating chain."""
    rated = Participation.objects.filter(contest=contest, rating_after__isnull=False).values("user_id")
    return not (Participation.objects.filter(user_id__in=rated, rating_after__isnull=False,
                                             contest__end__gt=contest.end)
                .exclude(contest=contest).exists())


def rollback(contest) -> None:
    """Undo the contest's rating. Each user loses exactly this contest's delta, so a
    manual rating edit made since is kept."""
    with transaction.atomic():
        for p in Participation.objects.select_for_update().filter(contest=contest, rating_after__isnull=False):
            User.objects.filter(pk=p.user_id).update(rating=F("rating") - (p.rating_after - p.rating_before))
            p.rating_before = p.rating_after = None
            p.save(update_fields=["rating_before", "rating_after"])
        contest.rating_applied = False
        contest.save(update_fields=["rating_applied"])


def recompute(contest) -> None:
    with transaction.atomic():
        rollback(contest)
        apply_rating(contest)
