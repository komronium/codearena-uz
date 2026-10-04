from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.contests.models import Contest
from apps.contests.rating import apply_rating, recalc_official, replay


class Command(BaseCommand):
    help = ("Apply the rating changes of a finished rated contest (apps.contests.rating). "
            "Idempotent via Contest.rating_applied. Omit contest_id to process every ended rated "
            "contest that hasn't had rating applied yet (cron-friendly). --replay rebuilds every "
            "rating from zero over the applied contests, after a change to the rating maths.")

    def add_arguments(self, parser):
        parser.add_argument("contest_id", type=int, nargs="?", default=None)
        parser.add_argument("--replay", action="store_true",
                            help="rebuild every rating from zero; manual rating edits are lost")

    def handle(self, *args, **opts):
        if opts["replay"]:
            if opts["contest_id"] is not None:
                raise CommandError("--replay takes no contest_id")
            n = replay()
            recalc_official()  # same maths
            self.stdout.write(self.style.SUCCESS(f"replayed {n} rated contests and the official rating"))
            return
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
