"""Close the rounds staff left on automatic: some hours after the end, when no similarity flag of the round is still
unreviewed, make its problems public (their solves count as practice) and, for a rated round, apply the rating.
Run by the scheduler; idempotent. A round is only touched when its `auto_finish` is on."""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.contests import rating
from apps.contests.models import Contest
from apps.integrity.models import AuditEntry, SimilarityFlag
from apps.problems.models import Problem
from apps.submissions.solves import refresh_solves


class Command(BaseCommand):
    help = "Publish and rate finished rounds that have auto_finish on, once nothing is left to review."

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=12, help="wait this long after the end (default 12)")

    def handle(self, *args, **opts):
        cutoff = timezone.now() - timedelta(hours=opts["hours"])
        done = 0
        for contest in Contest.objects.filter(auto_finish=True, end__lte=cutoff):
            needs_publish = contest.published_at is None
            needs_rating = contest.is_rated and not contest.rating_applied
            if not (needs_publish or needs_rating):
                continue
            if SimilarityFlag.objects.filter(submission_a__contest=contest, reviewed=False).exists():
                self.stdout.write(f"#{contest.pk} {contest.title}: open similarity flags, left for staff")
                continue
            with transaction.atomic():
                if needs_publish:
                    Problem.objects.filter(contests=contest).update(is_public=True)
                    contest.published_at = timezone.now()
                    contest.save(update_fields=["published_at"])
                    for problem_id in contest.contest_problems.values_list("problem_id", flat=True):
                        refresh_solves(problem_id)
                    AuditEntry.objects.create(actor=None, action=AuditEntry.Action.PUBLISH, contest=contest,
                                              note="avtomatik")
                if needs_rating and rating.apply_rating(contest):
                    AuditEntry.objects.create(actor=None, action=AuditEntry.Action.RATING_APPLY, contest=contest,
                                              note="avtomatik")
            done += 1
            self.stdout.write(self.style.SUCCESS(f"#{contest.pk} {contest.title}: closed"))
        self.stdout.write(f"{done} round(s) closed")
