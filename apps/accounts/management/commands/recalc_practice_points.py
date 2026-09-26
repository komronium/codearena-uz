from django.core.management.base import BaseCommand

from apps.submissions.models import Submission, UserProblemSolved
from apps.submissions.solves import refresh_solves, sync_practice_points


class Command(BaseCommand):
    help = ("Rebuild every solve from the eligibility rule (apps.submissions.solves), then "
            "every user's practice_points. Idempotent. Run once after deploying the honest-results "
            "change; the recalc_points sweep keeps points live after that.")

    def handle(self, *args, **opts):
        problem_ids = (set(Submission.objects.filter(verdict=Submission.Verdict.AC).values_list("problem_id", flat=True))
                       | set(UserProblemSolved.objects.values_list("problem_id", flat=True)))
        for problem_id in problem_ids:
            refresh_solves(problem_id)
        sync_practice_points()  # users with no solve left drop to 0
        self.stdout.write(self.style.SUCCESS(f"{len(problem_ids)} problem(s) resynced"))
