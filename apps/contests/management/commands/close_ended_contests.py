from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.contests.models import Contest


class Command(BaseCommand):
    help = "Flip is_public=True on problems of contests whose end has passed (spec §3). Idempotent; run via cron."

    def handle(self, *args, **opts):
        made_public = 0
        for contest in Contest.objects.filter(end__lte=timezone.now()):
            for cp in contest.contest_problems.select_related("problem"):
                if not cp.problem.is_public:
                    cp.problem.is_public = True
                    cp.problem.save(update_fields=["is_public"])
                    made_public += 1
        self.stdout.write(self.style.SUCCESS(f"{made_public} problem(s) made public"))
