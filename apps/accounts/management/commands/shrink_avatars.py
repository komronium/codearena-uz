"""Re-save every avatar as a 256 px WebP (apps/accounts/avatars.py); new uploads are shrunk when they arrive."""
from django.core.management.base import BaseCommand

from apps.accounts.avatars import is_small, shrink
from apps.accounts.models import User


class Command(BaseCommand):
    help = "Shrink the avatars uploaded before the upload form did it."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, dry_run=False, **options):
        saved = done = 0
        for user in User.objects.exclude(avatar="").exclude(avatar__isnull=True):
            try:
                size = user.avatar.size
                if is_small(user.avatar.name, size):
                    continue
                if dry_run:
                    self.stdout.write(f"{user.username}: {user.avatar.name} {size // 1024} KB")
                    continue
                old = user.avatar.name
                with user.avatar.open("rb") as handle:
                    small = shrink(handle, f"avatar-{user.pk}")
                user.avatar.save(small.name, small, save=True)
                user.avatar.storage.delete(old)
                saved += size - small.size
                done += 1
            except Exception as exc:  # noqa: BLE001 - a missing or broken file is skipped, the rest go on
                self.stderr.write(f"{user.username}: {exc}")
        self.stdout.write(f"{done} avatars shrunk, {saved // 1024} KB less")
