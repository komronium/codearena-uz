"""Stores every badge level each user has reached (apps.accounts.badges). Run once when the badges
arrive, with --seen, so nobody gets a toast for levels earned before; afterwards the site keeps them
up to date by itself.

    python manage.py sync_badges [--seen]
"""
from django.core.management.base import BaseCommand

from apps.accounts import badges
from apps.accounts.models import User, UserBadge


class Command(BaseCommand):
    help = "Stores the badge levels every user has reached."

    def add_arguments(self, parser):
        parser.add_argument("--seen", action="store_true", help="Mark them as already shown (no toast)")

    def handle(self, *args, **opts):
        users = User.objects.filter(is_active=True)
        for user in users.iterator():
            badges.sync(user)
        if opts["seen"]:
            UserBadge.objects.filter(seen=False).update(seen=True)
        self.stdout.write(self.style.SUCCESS(
            f"{users.count()} ta foydalanuvchi, {UserBadge.objects.count()} ta bosqich saqlangan."))
