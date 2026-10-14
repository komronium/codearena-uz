#!/usr/bin/env python3
"""Standalone script to load and seed Python beginner & easy duel questions.

Usage:
    python scripts/seed_python_duels.py
"""
import os
import sys
from pathlib import Path

# Setup Django environment
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django
django.setup()

from django.db import transaction
from apps.classroom.models import DuelQuestion
from apps.classroom.quiz_bank import entries

FIELDS = ("language", "level", "kind", "code", "full", "expect", "options", "answer", "accept", "explain")


def main():
    python_questions = [
        e for e in entries()
        if e["language"] == "python" and e["level"] in ("beginner", "easy")
    ]

    print(f"Jami tekshirilayotgan savollar: {len(python_questions)} ta")

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

        total_active = DuelQuestion.objects.filter(
            language="python", level__in=("beginner", "easy"), is_active=True
        ).count()

        print(
            f"Muvaffaqiyatli bajarildi!\n"
            f"  - Yangi qo'shilgan: {added}\n"
            f"  - Yangilangan: {changed}\n"
            f"  - Jami faol Python (beginner + easy): {total_active} ta"
        )


if __name__ == "__main__":
    main()
