from django.core.management.base import BaseCommand

from apps.problems.difficulty import estimate, guess, results
from apps.problems.models import Problem


class Command(BaseCommand):
    help = ("Re-rate each approved problem from who tried it and who solved it "
            "(apps.problems.difficulty). Idempotent, cron-friendly.")

    def handle(self, *args, **opts):
        problems = list(Problem.objects.filter(status=Problem.Status.APPROVED)
                        .only("pk", "difficulty", "rating", "rating_guess"))
        attempts = results(problems)
        changed = []
        for p in problems:
            rating = estimate(attempts.get(p.pk, []), guess(p))
            if rating != p.rating:
                p.rating = rating
                changed.append(p)
        Problem.objects.bulk_update(changed, ["rating"])  # no save(): it would re-rate each one again
        self.stdout.write(self.style.SUCCESS(f"{len(changed)} problem(s) re-rated"))
