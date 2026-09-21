from itertools import combinations

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.contests.models import Contest
from apps.integrity.models import SimilarityFlag
from apps.integrity.similarity import THRESHOLD, similarity
from apps.submissions.models import Submission


class Command(BaseCommand):
    help = ("Flag AC-submission pairs above the similarity threshold for a contest (spec §4.2). "
            "Idempotent. Omit contest_id to process every ended contest (cron-friendly).")

    def add_arguments(self, parser):
        parser.add_argument("contest_id", type=int, nargs="?", default=None)

    def handle(self, *args, **opts):
        if opts["contest_id"] is not None:
            try:
                contest = Contest.objects.get(pk=opts["contest_id"])
            except Contest.DoesNotExist:
                raise CommandError(f"no contest {opts['contest_id']}")
            created = self._flag(contest)
            self.stdout.write(self.style.SUCCESS(f"{created} similarity flag(s) created"))
            return

        total = 0
        for contest in Contest.objects.filter(end__lte=timezone.now()):
            total += self._flag(contest)
        self.stdout.write(self.style.SUCCESS(f"{total} similarity flag(s) created"))

    def _flag(self, contest) -> int:
        problem_ids = contest.contest_problems.values_list("problem_id", flat=True)
        created = 0
        for problem_id in problem_ids:
            subs = list(Submission.objects.filter(contest=contest, problem_id=problem_id, verdict="AC"))
            for a, b in combinations(subs, 2):
                # different languages read too differently for a text similarity score to mean anything
                if a.user_id == b.user_id or a.language_id != b.language_id:
                    continue
                score = similarity(a.source, b.source)
                if score < THRESHOLD:
                    continue
                lo, hi = (a, b) if a.pk < b.pk else (b, a)
                if SimilarityFlag.objects.filter(submission_a=lo, submission_b=hi).exists():
                    continue
                SimilarityFlag.objects.create(submission_a=lo, submission_b=hi, score=score)
                created += 1
        return created
