"""AI drafts of the other language for problems, courses and contests that have none yet. The drafts stay closed to readers
until an admin confirms them (/moderation/translations/). Runs in this process with a few threads (not in the RQ queue,
which the judge shares), so it can be started from a one-off container and left alone.

    python manage.py translate_content [problems|courses|contests|all] [--workers 4] [--redo] [--limit N]
"""
from concurrent.futures import ThreadPoolExecutor

from django.core.management.base import BaseCommand
from django.db import connection

from apps.translations import service


class Command(BaseCommand):
    help = "Translate problems, courses and contests that have no translation yet (AI drafts, unconfirmed)."

    def add_arguments(self, parser):
        parser.add_argument("kind", nargs="?", default="all", choices=["problems", "courses", "contests", "all"])
        parser.add_argument("--workers", type=int, default=4)
        parser.add_argument("--redo", action="store_true", help="also translate the ones that already have a draft")
        parser.add_argument("--limit", type=int, default=0)

    def handle(self, *args, **opts):
        kinds = list(service.KINDS) if opts["kind"] == "all" else [opts["kind"]]
        todo = []
        for kind in kinds:
            for obj in service.model_of(kind).objects.all().order_by("pk"):
                status = service.status(obj)
                if status == "none" or (opts["redo"] and status != "confirmed"):
                    todo.append((kind, obj.pk))
        if opts["limit"]:
            todo = todo[:opts["limit"]]
        self.stdout.write(f"{len(todo)} to translate")
        done = failed = 0

        def work(item):
            kind, pk = item
            try:
                obj = service.model_of(kind).objects.get(pk=pk)
                return item, service.ai_translate(obj), None
            except Exception as e:  # one failure must not stop the rest
                return item, 0, e
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=opts["workers"]) as pool:
            for item, n, err in pool.map(work, todo):
                if err:
                    failed += 1
                    self.stderr.write(f"FAILED {item}: {err}")
                else:
                    done += 1
                    self.stdout.write(f"{done + failed}/{len(todo)} {item[0]}#{item[1]}: {n} texts")
        self.stdout.write(self.style.SUCCESS(f"done {done}, failed {failed}"))
