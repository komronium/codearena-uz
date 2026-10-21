"""Writes the texts that still have no translation to a JSON file ({key: original}) for a person (or an AI session) to translate;
`import_translations` reads the translated file back. Keys look like "problem.12.statement_md"."""
import json

from django.core.management.base import BaseCommand

from apps.translations import service
from apps.translations.models import ContentTranslation
from django.contrib.contenttypes.models import ContentType


class Command(BaseCommand):
    help = "Export untranslated texts (problems, courses, contests) to a JSON file."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("kind", nargs="?", default="all", choices=["problems", "courses", "contests", "all"])

    def handle(self, *args, **opts):
        kinds = list(service.KINDS) if opts["kind"] == "all" else [opts["kind"]]
        out = {}
        for kind in kinds:
            for obj in service.model_of(kind).objects.all().order_by("pk"):
                lang = service.other(obj.source_lang)
                for row, field, text in service.units(obj):
                    ct = ContentType.objects.get_for_model(row)
                    if ContentTranslation.objects.filter(content_type=ct, object_id=row.pk, lang=lang, field=field).exists():
                        continue
                    out[service.key(row, field)] = {"lang": lang, "text": text}
        with open(opts["path"], "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=0)
        self.stdout.write(f"{len(out)} texts -> {opts['path']}")
