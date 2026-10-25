from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from apps.contests.models import Contest
from apps.integrity.ai_baselines import generate
from apps.integrity.models import AiBaseline
from apps.moderation.ai import DEFAULT_MODEL
from apps.problems.models import Language
from apps.submissions.models import Submission


class Command(BaseCommand):
    help = ("Ask an AI to solve every problem of a contest, to compare submissions with (flag_similarity does "
            "that afterwards). Languages default to the ones the participants used most. Costs API calls: "
            "problems x languages x --per-language.")

    def add_arguments(self, parser):
        parser.add_argument("contest_id", type=int)
        parser.add_argument("--per-language", type=int, default=4)
        parser.add_argument("--languages", default="", help="comma-separated codes (python,cpp); default: the 3 most used")
        parser.add_argument("--model", default=DEFAULT_MODEL)
        parser.add_argument("--replace", action="store_true", help="drop the problem's existing baselines first")

    def handle(self, *args, **opts):
        try:
            contest = Contest.objects.get(pk=opts["contest_id"])
        except Contest.DoesNotExist:
            raise CommandError(f"no contest {opts['contest_id']}")
        codes = [c.strip() for c in opts["languages"].split(",") if c.strip()]
        if not codes:
            used = Counter(Submission.objects.filter(contest=contest).values_list("language__code", flat=True))
            codes = [c for c, _ in used.most_common(3)] or ["python"]
        languages = list(Language.objects.filter(code__in=codes))
        if not languages:
            raise CommandError(f"no language among {codes}")
        total = 0
        for cp in contest.contest_problems.select_related("problem"):
            if opts["replace"]:
                AiBaseline.objects.filter(problem=cp.problem).delete()
            for language in languages:
                if not opts["replace"] and AiBaseline.objects.filter(problem=cp.problem, language=language).exists():
                    continue
                made = generate(cp.problem, language, opts["per_language"], opts["model"])
                total += made
                self.stdout.write(f"{cp.label} {language.code}: {made}")
        self.stdout.write(self.style.SUCCESS(f"{total} AI baseline(s) made; run flag_similarity {contest.pk} to compare"))
