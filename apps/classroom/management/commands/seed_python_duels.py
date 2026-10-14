"""Management command to seed or update Python beginner & easy duel questions.

Usage:
    python manage.py seed_python_duels
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.classroom.models import DuelQuestion
from apps.classroom.quiz_bank import entries

FIELDS = ("language", "level", "kind", "code", "full", "expect", "options", "answer", "accept", "explain")


class Command(BaseCommand):
    help = "Loads and updates Python beginner and easy duel questions in the database."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Preview changes without saving")

    def handle(self, *args, **opts):
        python_questions = [
            e for e in entries()
            if e["language"] == "python" and e["level"] in ("beginner", "easy")
        ]

        with transaction.atomic():
            have = {q.key: q for q in DuelQuestion.objects.filter(language="python", level__in=("beginner", "easy"))}
            added = changed = 0
            for e in python_questions:
                q = have.get(e["key"])
                values = {f: e[f] for f in FIELDS}
                if q is None:
                    DuelQuestion.objects.create(key=e["key"], **values)
                    added += 1
                elif not q.is_active or any(getattr(q, f) != v for f, v in values.items()):
                    DuelQuestion.objects.filter(pk=q.pk).update(is_active=True, **values)
                    changed += 1

            total_active = DuelQuestion.objects.filter(language="python", level__in=("beginner", "easy"), is_active=True).count()
            self.stdout.write(self.style.SUCCESS(
                f"Python duellari muvaffaqiyatli yangilandi!\n"
                f"  - Yangi qo'shildi: {added}\n"
                f"  - Yangilandi: {changed}\n"
                f"  - Jami faol (beginner + easy): {total_active}"
            ))

            if opts.get("dry_run"):
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("Dry run — o'zgarishlar bekor qilindi."))
