from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.contests.models import Contest, Participation
from apps.contests.standings import compute_standings


def _expected_seed(idx, ratings):
    """Elo-style expected rank: 1 + sum of P(j beats i) for every other participant."""
    r_i = ratings[idx]
    return 1 + sum(
        1 / (1 + 10 ** ((r_i - ratings[j]) / 400))
        for j in range(len(ratings)) if j != idx
    )


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
                # K=40 for a user's first 10 rated contests, else 20 (spec §3).
                past_rated = Participation.objects.filter(user=user, rating_after__isnull=False).count()
                k = 40 if past_rated < 10 else 20
                new_rating = round(user.rating + k * (seed - row["rank"]))

                p = row["participation"]
                p.rank, p.score, p.penalty = row["rank"], row["score"], row["penalty"]
                p.rating_before, p.rating_after = user.rating, new_rating
                p.save(update_fields=["rank", "score", "penalty", "rating_before", "rating_after"])

                user.rating = new_rating
                user.save(update_fields=["rating"])

            contest.rating_applied = True
            contest.save(update_fields=["rating_applied"])

        self.stdout.write(self.style.SUCCESS(f"rating applied for contest {contest.pk}"))
