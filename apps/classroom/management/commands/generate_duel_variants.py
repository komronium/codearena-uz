"""Makes variants of the duel question bank (apps.classroom.quiz_variants): same programs, other numbers, the
answers worked out in the judge sandbox. Safe to run again: variants that exist are kept.

    python manage.py generate_duel_variants [--per-question 6] [--language python] [--dry-run]
"""
import random
from concurrent.futures import ThreadPoolExecutor

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.classroom.models import DuelQuestion
from apps.classroom.quiz_bank import entries
from apps.classroom.quiz_check import sandbox_run
from apps.classroom.quiz_variants import variants_of

FIELDS = ("language", "level", "kind", "code", "full", "expect", "options", "answer", "accept", "explain", "origin")


class Command(BaseCommand):
    help = "Generates variants of the duel questions (needs the judge sandbox: run it in the worker container)."

    def add_arguments(self, parser):
        parser.add_argument("--per-question", type=int, default=6)
        parser.add_argument("--language", action="append", help="only this language (repeatable)")
        parser.add_argument("--workers", type=int, default=4)
        parser.add_argument("--seed", type=int, default=None)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        bank = [e for e in entries() if not opts["language"] or e["language"] in opts["language"]]

        def work(item):
            i, e = item
            return list(variants_of(e, sandbox_run, opts["per_question"], random.Random(None if opts["seed"] is None else opts["seed"] + i)))

        with ThreadPoolExecutor(opts["workers"]) as pool:
            made = list({v["key"]: v for batch in pool.map(work, enumerate(bank)) for v in batch}.values())
        with transaction.atomic():
            have = set(DuelQuestion.objects.filter(key__in=[v["key"] for v in made]).values_list("key", flat=True))
            new = [DuelQuestion(key=v["key"], **{f: v[f] for f in FIELDS}) for v in made if v["key"] not in have]
            DuelQuestion.objects.bulk_create(new)
            self.stdout.write(f"{len(bank)} ta savoldan {len(made)} ta variant chiqdi, yangi: {len(new)}, "
                              f"jami faol: {DuelQuestion.objects.filter(is_active=True).count()}.")
            if opts["dry_run"]:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("Dry run — hech narsa saqlanmadi."))
