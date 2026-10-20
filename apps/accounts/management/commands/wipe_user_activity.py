"""Erase one user's duels, submissions and contest participations, then rebuild what they had touched
(contest and official rating, duel Elo and season podiums, solves and practice points) so nobody else keeps a
rank or a rating that depended on them. The account itself stays. Prints the counts and stops unless --yes."""
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from apps.accounts.models import User
from apps.classroom.models import Duel, DuelSeasonResult
from apps.contests.models import Clarification, Participation, VirtualParticipation
from apps.submissions.models import Submission, UserProblemSolved


class Command(BaseCommand):
    help = ("Delete a user's duels, submissions and contest participations and replay the ratings. "
            "Dry run unless --yes. The replays drop manual rating edits (same as recalc_rating --replay).")

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("--yes", action="store_true", help="do it; without this only the counts are shown")

    def handle(self, *args, **opts):
        try:
            user = User.objects.get(username=opts["username"])
        except User.DoesNotExist:
            raise CommandError(f"no user {opts['username']!r}")
        sets = {
            "duels": Duel.objects.filter(Q(challenger=user) | Q(opponent=user)),
            "duel season results": DuelSeasonResult.objects.filter(user=user),
            "submissions": Submission.objects.filter(user=user),
            "solves": UserProblemSolved.objects.filter(user=user),
            "contest participations": Participation.objects.filter(user=user),
            "virtual runs": VirtualParticipation.objects.filter(user=user),
            "clarifications": Clarification.objects.filter(user=user),
        }
        for name, qs in sets.items():
            self.stdout.write(f"{name}: {qs.count()}")
        if not opts["yes"]:
            self.stdout.write("dry run: pass --yes to delete these and replay the ratings")
            return
        with transaction.atomic():
            for qs in sets.values():
                qs.delete()
        call_command("recalc_rating", replay=True, stdout=self.stdout)
        call_command("recalc_duel_rating", stdout=self.stdout)
        call_command("recalc_practice_points", stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS(f"{user.username}: activity erased, ratings rebuilt"))
