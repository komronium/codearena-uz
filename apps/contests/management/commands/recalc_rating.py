from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.contests.models import Contest, Participation
from apps.contests.standings import compute_standings


# Tuned for a classroom pool where everyone starts at 1200: winning a 15-person
# contest ≈ +100, last place ≈ -100. Sum of expected seeds equals sum of ranks, so
# the Elo part is zero-sum; PARTICIPATION_BONUS is the only inflation.
K_NEW, K_ESTABLISHED = 100, 60        # first 10 rated contests vs after
SCALE = 800                           # wider than classic Elo's 400 so gains don't stall at ~1600
PARTICIPATION_BONUS = 1               # every finisher gets this on top: mild inflation, pool grows by n per contest


def _expected_seed(idx, ratings):
    """Elo-style expected rank: 1 + sum of P(j beats i) for every other participant."""
    r_i = ratings[idx]
    return 1 + sum(
        1 / (1 + 10 ** ((r_i - ratings[j]) / SCALE))
        for j in range(len(ratings)) if j != idx
    )


def rating_delta(seed: float, rank: int, n: int, k: int) -> int:
    """Normalised so that in an all-equal field 1st place gets +k and last gets -k,
    whatever the contest size."""
    return round(k * 2 * (seed - rank) / max(n - 1, 1)) + PARTICIPATION_BONUS


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

        rows = compute_standings(contest)
        if not rows:
            contest.rating_applied = True
            contest.save(update_fields=["rating_applied"])
            self.stdout.write(f"contest {contest.pk}: no participants, marked applied")
            return

        users = [r["user"] for r in rows]
        ratings = [u.rating for u in users]

        with transaction.atomic():
            for i, (row, user) in enumerate(zip(rows, users)):
                seed = _expected_seed(i, ratings)
                past_rated = Participation.objects.filter(user=user, rating_after__isnull=False).count()
                k = K_NEW if past_rated < 10 else K_ESTABLISHED
                new_rating = user.rating + rating_delta(seed, row["rank"], len(rows), k)

                p = row["participation"]
                p.rank, p.score, p.penalty = row["rank"], row["score"], row["penalty"]
                p.rating_before, p.rating_after = user.rating, new_rating
                p.save(update_fields=["rank", "score", "penalty", "rating_before", "rating_after"])

                user.rating = new_rating
                user.save(update_fields=["rating"])

            contest.rating_applied = True
            contest.save(update_fields=["rating_applied"])

        self.stdout.write(self.style.SUCCESS(f"rating applied for contest {contest.pk}"))
