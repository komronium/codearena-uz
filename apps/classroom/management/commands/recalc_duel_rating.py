"""Rebuild the duel Elo from scratch: every finished duel's deltas and every user's duel_rating/duel_season,
oldest first (apps.classroom.duels.replay), then every past season's podium. The duel rating is its own
system (never the contest rating); this is the duel counterpart of `recalc_rating`. Manual rating edits are
lost, exactly like a replay."""
from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.classroom import duels
from apps.classroom.models import Duel, DuelSeasonResult

START_RATING = duels.START_RATING


class Command(BaseCommand):
    help = ("Rebuild every finished duel's Elo (deltas) and every user's duel_rating, and rebuild the "
            "season podiums. Manual duel-rating edits are lost. Safe to run any time; idempotent.")

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-seasons", action="store_true",
            help="Recompute the ratings only; leave the stored season podiums as they are.")

    def handle(self, *args, **options):
        before = dict(User.objects.values_list("id", "duel_rating"))
        duels.replay(Duel.objects.all(), User.objects.all())
        finished = Duel.objects.filter(status=Duel.Status.FINISHED).count()
        after = dict(User.objects.values_list("id", "duel_rating"))
        changed = sum(1 for u, r in before.items() if after.get(u) != r)
        self.stdout.write(f"Replayed {finished} finished duels; {changed} user(s) changed rating")

        from apps.accounts import badges
        self.stdout.write(f"Stored {badges.backfill()} badge level(s) the new ratings reach, quietly (no award window, no message)")

        if not options["no_seasons"]:
            # the podiums are derived from the duels: drop the stored ones and work them out again
            DuelSeasonResult.objects.all().delete()
            duels.close_seasons()
            self.stdout.write(f"Rebuilt {DuelSeasonResult.objects.count()} season podium row(s)")
