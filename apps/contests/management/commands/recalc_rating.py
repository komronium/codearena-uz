from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.contests.models import Contest
from apps.contests.rating import apply_rating


class Command(BaseCommand):
    help = ("Apply Elo-style rating deltas for a finished rated contest (apps.contests.rating). "
            "Idempotent via Contest.rating_applied. Omit contest_id to process every ended rated "
            "contest that hasn't had rating applied yet (cron-friendly).")

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
        if apply_rating(contest):
            self.stdout.write(self.style.SUCCESS(f"rating applied for contest {contest.pk}"))
        else:
            self.stdout.write(f"contest {contest.pk}: already applied, no-op")
