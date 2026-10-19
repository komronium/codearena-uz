"""Loads the duel question bank (apps.classroom.quiz_bank) into the database: new questions are added,
changed ones updated, ones gone from the bank retired (kept for the duels that used them).

    python manage.py load_duel_questions [--verify] [--dry-run]

--verify runs every question in the judge sandbox first (the worker container has it) and loads nothing
if any question is wrong.
"""
from concurrent.futures import ThreadPoolExecutor

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.classroom.models import DuelQuestion
from apps.classroom.quiz_bank import entries
from apps.classroom.quiz_check import check, sandbox_run
from apps.classroom.quiz_variants import acceptable

FIELDS = ("language", "level", "kind", "code", "full", "expect", "options", "answer", "accept", "explain")


class Command(BaseCommand):
    help = "Loads (and with --verify, first checks) the duel question bank."

    def add_arguments(self, parser):
        parser.add_argument("--verify", action="store_true", help="Run every question in the judge sandbox first")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--workers", type=int, default=4)

    def handle(self, *args, **opts):
        bank = list(entries())
        if opts["verify"]:
            with ThreadPoolExecutor(opts["workers"]) as pool:
                results = list(pool.map(lambda e: check(e, sandbox_run), bank))
            bad = [(e, errs) for e, errs in zip(bank, results) if errs]
            for e, errs in bad:
                self.stdout.write(self.style.ERROR(f"{e['key']}: {e['code'][:60]!r}"))
                for err in errs:
                    self.stdout.write(f"    {err}")
            if bad:
                raise CommandError(f"{len(bad)} ta savol xato — hech narsa yuklanmadi.")
            self.stdout.write(self.style.SUCCESS(f"{len(bank)} ta savolning hammasi tekshirildi."))

        with transaction.atomic():
            have = {q.key: q for q in DuelQuestion.objects.all()}
            added = changed = 0
            for e in bank:
                q = have.get(e["key"])
                values = {f: e[f] for f in FIELDS}
                if q is None:
                    DuelQuestion.objects.create(key=e["key"], **values)
                    added += 1
                elif not q.is_active or any(getattr(q, f) != v for f, v in values.items()):
                    DuelQuestion.objects.filter(pk=q.pk).update(is_active=True, **values)
                    changed += 1
            keys = [e["key"] for e in bank]
            retired = (DuelQuestion.objects.filter(is_active=True, origin="").exclude(key__in=keys)
                       .update(is_active=False))
            # variants follow their original out of the bank, and a pick question's variant is never typed
            variants = DuelQuestion.objects.filter(is_active=True).exclude(origin="")
            retired += variants.exclude(origin__in=keys).update(is_active=False)
            picks = set(DuelQuestion.objects.filter(origin="", key__in=keys).exclude(options=[]).values_list("key", flat=True))
            retired += variants.filter(options=[], origin__in=picks).update(is_active=False)
            origin_code = {e["key"]: e["code"] for e in bank}
            poor = [q.pk for q in variants.filter(origin__in=keys) if not acceptable(q.code, q.answer, origin_code[q.origin])]
            retired += DuelQuestion.objects.filter(pk__in=poor).update(is_active=False)
            self.stdout.write(f"Yangi: {added}, o‘zgargan: {changed}, olib tashlangan: {retired}, "
                              f"jami faol: {DuelQuestion.objects.filter(is_active=True).count()}.")
            if opts["dry_run"]:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("Dry run — hech narsa saqlanmadi."))
