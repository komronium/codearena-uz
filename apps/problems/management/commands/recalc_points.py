from django.core.management.base import BaseCommand
from django.db.models import Count

from apps.problems.models import Problem
from apps.problems.scoring import compute_points


class Command(BaseCommand):
    help = ("Recompute each approved problem's points from its difficulty band and solve "
            "rate (solvers / distinct attempters). Idempotent, cron-friendly.")

    def handle(self, *args, **opts):
        problems = Problem.objects.filter(status=Problem.Status.APPROVED).annotate(
            attempts=Count("submissions__user", distinct=True),
            solvers=Count("userproblemsolved", distinct=True),
        )
        updated = 0
        for p in problems:
            points = compute_points(p.difficulty, p.solvers, p.attempts)
            if points != p.points:
                p.points = points
                p.save(update_fields=["points"])
                updated += 1
        self.stdout.write(self.style.SUCCESS(f"{updated} problem(s) repointed"))
