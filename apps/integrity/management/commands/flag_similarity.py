from itertools import combinations

from django.core.management.base import BaseCommand, CommandError

from apps.contests.models import Contest
from apps.integrity.models import SimilarityFlag
from apps.integrity.similarity import THRESHOLD, similarity
from apps.submissions.models import Submission


class Command(BaseCommand):
    help = "Flag AC-submission pairs above the similarity threshold for a contest (spec §4.2). Idempotent."

    def add_arguments(self, parser):
        parser.add_argument("contest_id", type=int)

    def handle(self, *args, **opts):
        try:
            contest = Contest.objects.get(pk=opts["contest_id"])
        except Contest.DoesNotExist:
            raise CommandError(f"no contest {opts['contest_id']}")

        problem_ids = contest.contest_problems.values_list("problem_id", flat=True)
        created = 0
        for problem_id in problem_ids:
            subs = list(Submission.objects.filter(contest=contest, problem_id=problem_id, verdict="AC"))
            for a, b in combinations(subs, 2):
                if a.user_id == b.user_id:
                    continue
                score = similarity(a.source, b.source)
                if score < THRESHOLD:
                    continue
                lo, hi = (a, b) if a.pk < b.pk else (b, a)
                if SimilarityFlag.objects.filter(submission_a=lo, submission_b=hi).exists():
                    continue
                SimilarityFlag.objects.create(submission_a=lo, submission_b=hi, score=score)
                created += 1

        self.stdout.write(self.style.SUCCESS(f"{created} similarity flag(s) created"))
