from django.db import migrations, models
from django.utils import timezone


def backfill_published_at(apps, schema_editor):
    """Contests the old publish button already processed are published at their end: it
    left solves pointing at their submissions, or opened all of their problems."""
    Contest = apps.get_model("contests", "Contest")
    UserProblemSolved = apps.get_model("submissions", "UserProblemSolved")
    traced = set(UserProblemSolved.objects.values_list("first_ac_submission__contest_id", flat=True))
    for contest in Contest.objects.filter(end__lte=timezone.now(), published_at__isnull=True):
        public = list(contest.contest_problems.values_list("problem__is_public", flat=True))
        if contest.pk in traced or (public and all(public)):
            contest.published_at = contest.end
            contest.save(update_fields=["published_at"])


class Migration(migrations.Migration):

    dependencies = [
        ("contests", "0005_drop_icpc_type"),
        ("submissions", "0003_testresult_mem_kb"),
    ]

    operations = [
        migrations.AddField(
            model_name="contest",
            name="published_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_published_at, migrations.RunPython.noop),
    ]
