from django.core.management.base import BaseCommand

from apps.contests.rating import recalc_official


class Command(BaseCommand):
    help = ("Rebuild the official rating from every applied official contest, verified users only "
            "(apps.contests.rating.recalc_official). Safe to run any time.")

    def handle(self, *args, **opts):
        recalc_official()
        self.stdout.write(self.style.SUCCESS("official rating rebuilt"))
