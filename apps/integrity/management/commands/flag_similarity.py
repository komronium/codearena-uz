from itertools import combinations

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.contests.models import Contest
from apps.integrity.models import SimilarityFlag
from apps.integrity.similarity import MIN_LINES, THRESHOLD, code_lines, similarity
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
        """Keep exactly one flag per (problem, user pair): their most similar AC pair,
        if both sides have MIN_LINES+ lines of code and score >= THRESHOLD.
        Unreviewed flags that no longer qualify (older, looser rules) are dropped;
        reviewed ones stay — a human already looked at them."""
        created = 0
        keep: set[int] = set()
        for problem_id in contest.contest_problems.values_list("problem_id", flat=True):
            subs = [s for s in Submission.objects.filter(contest=contest, problem_id=problem_id, verdict="AC")
                    if code_lines(s.source) >= MIN_LINES]
            best: dict[tuple[int, int], tuple[float, Submission, Submission]] = {}
            for a, b in combinations(subs, 2):
                # different languages read too differently for a text similarity score to mean anything
                if a.user_id == b.user_id or a.language_id != b.language_id:
                    continue
                score = similarity(a.source, b.source)
                pair = tuple(sorted((a.user_id, b.user_id)))
                if score >= THRESHOLD and score > best.get(pair, (0,))[0]:
                    lo, hi = (a, b) if a.pk < b.pk else (b, a)
                    best[pair] = (score, lo, hi)
            for score, lo, hi in best.values():
                flag = (SimilarityFlag.objects.filter(submission_a__user=lo.user_id, submission_b__user=hi.user_id,
                                                      submission_a__problem_id=problem_id, submission_a__contest=contest)
                        | SimilarityFlag.objects.filter(submission_a__user=hi.user_id, submission_b__user=lo.user_id,
                                                        submission_a__problem_id=problem_id, submission_a__contest=contest)
                        ).first()
                if flag is None:
                    flag = SimilarityFlag.objects.create(submission_a=lo, submission_b=hi, score=score)
                    created += 1
                elif not flag.reviewed:
                    flag.submission_a, flag.submission_b, flag.score = lo, hi, score
                    flag.save(update_fields=["submission_a", "submission_b", "score"])
                keep.add(flag.pk)
        SimilarityFlag.objects.filter(submission_a__contest=contest, reviewed=False).exclude(pk__in=keep).delete()
        return created
