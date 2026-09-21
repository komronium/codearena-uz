from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.contests.models import Contest, Participation
from apps.contests.standings import compute_standings


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


class Command(BaseCommand):
    help = ("Apply Elo-style rating deltas for a finished rated contest. Idempotent via "
            "Contest.rating_applied. Omit contest_id to process every ended rated contest "
            "that hasn't had rating applied yet (cron-friendly).")

    def add_arguments(self, parser):
        parser.add_argument("contest_id", type=int, nargs="?", default=None)

    def handle(self, *args, **opts):
        if opts["contest_id"] is not None:
            try:
                contest = Contest.objects.get(pk=opts["contest_id"])
            except Contest.DoesNotExist:
                raise CommandError(f"no contest {opts['contest_id']}")
            if not contest.is_rated:
                raise CommandError("contest is not rated")
            if not contest.rating_applied and not contest.has_ended:
                raise CommandError("contest has not ended yet")
            self._apply(contest)
            return

        contests = Contest.objects.filter(is_rated=True, rating_applied=False, end__lte=timezone.now())
        for contest in contests:
            self._apply(contest)

    def _apply(self, contest):
        if contest.rating_applied:
            self.stdout.write(f"contest {contest.pk}: already applied, no-op")
            return

        # Registered but never submitted = didn't take part; rated only if you played
        # (Codeforces/AtCoder rule). Disqualified stays in: ranking last is the penalty.
        rows = [r for r in compute_standings(contest) if r["attempted"] or r["disqualified"]]
        if not rows:
            contest.rating_applied = True
            contest.save(update_fields=["rating_applied"])
            self.stdout.write(f"contest {contest.pk}: no participants, marked applied")
            return

        users = [r["user"] for r in rows]
        ratings = [u.rating for u in users]
        # Tied rows share a rank in standings; for Elo use the tie group's mean position
        # (AtCoder convention) so a group at 3rd-6th is rated as 4.5, not all as 3.
        tie_size = {}
        for r in rows:
            tie_size[r["rank"]] = tie_size.get(r["rank"], 0) + 1
        elo_rank = {rank: rank + (size - 1) / 2 for rank, size in tie_size.items()}
        max_score = sum(cp.points for cp in contest.contest_problems.all()) or 1

        with transaction.atomic():
            for i, (row, user) in enumerate(zip(rows, users)):
                seed = _expected_seed(i, ratings)
                past_rated = Participation.objects.filter(user=user, rating_after__isnull=False).count()
                k = K_NEW if past_rated < 10 else K_ESTABLISHED
                new_rating = user.rating + rating_delta(seed, elo_rank[row["rank"]], len(rows), k,
                                                        row["score"] / max_score)

                p = row["participation"]
                p.rank, p.score, p.penalty = row["rank"], row["score"], row["penalty"]
                p.rating_before, p.rating_after = user.rating, new_rating
                p.save(update_fields=["rank", "score", "penalty", "rating_before", "rating_after"])

                user.rating = new_rating
                user.save(update_fields=["rating"])

            contest.rating_applied = True
            contest.save(update_fields=["rating_applied"])

        self.stdout.write(self.style.SUCCESS(f"rating applied for contest {contest.pk}"))
