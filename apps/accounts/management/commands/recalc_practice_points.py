from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum

from apps.accounts.models import User
from apps.submissions.models import UserProblemSolved


class Command(BaseCommand):
    help = ("One-off backfill: recompute every user's practice_points from the CURRENT "
            "points value of each problem they've solved. Run once after changing how "
            "Problem.points is scored (e.g. recalc_points) to bring past solves onto the "
            "new values; not wired into the scheduler.")

    def handle(self, *args, **opts):
        totals = dict(
            UserProblemSolved.objects.values("user_id")
            .annotate(total=Sum("problem__points"))
            .values_list("user_id", "total")
        )
        updated = 0
        with transaction.atomic():
            for user in User.objects.all():
                new_total = totals.get(user.pk, 0)
                if user.practice_points != new_total:
                    user.practice_points = new_total
                    user.save(update_fields=["practice_points"])
                    updated += 1
        self.stdout.write(self.style.SUCCESS(f"{updated} user(s) repointed"))
