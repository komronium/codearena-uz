"""Reads {key: translated text} (keys as in export_translations) and stores each as a draft in the other language; --confirm
shows them to readers at once. A key the site doesn't know is reported and skipped."""
import json

from django.apps import apps
from django.core.management.base import BaseCommand

from apps.translations import service


class Command(BaseCommand):
    help = "Import translated texts as drafts (or confirmed with --confirm)."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--lang", default="en")
        parser.add_argument("--confirm", action="store_true")

    def handle(self, *args, **opts):
        with open(opts["path"], encoding="utf-8") as f:
            data = json.load(f)
        models = {"problem": "problems.Problem", "problemhint": "problems.ProblemHint", "studyplan": "learn.StudyPlan",
                  "plansection": "learn.PlanSection", "contest": "contests.Contest"}
        saved = skipped = 0
        for key, text in data.items():
            model_name, pk, field = key.split(".", 2)
            model = apps.get_model(models[model_name]) if model_name in models else None
            row = model.objects.filter(pk=int(pk)).first() if model else None
            text = (text if isinstance(text, str) else text.get("text", "")).strip()
            if row is None or not text or field not in type(row).TRANSLATABLE:
                skipped += 1
                self.stderr.write(f"skipped {key}")
                continue
            service.save_draft(row, field, opts["lang"], text, by_ai=True, confirm=opts["confirm"])
            saved += 1
        self.stdout.write(self.style.SUCCESS(f"{saved} saved, {skipped} skipped"))
