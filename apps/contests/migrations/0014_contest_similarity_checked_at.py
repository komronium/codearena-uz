from django.db import migrations, models
from django.utils import timezone


def past_rounds_are_done(apps, schema_editor):
    """Rounds that ended before the automatic sweep were checked by hand or not at all on purpose:
    the sweep starts with the next one rather than reopening their flags."""
    Contest = apps.get_model("contests", "Contest")
    now = timezone.now()
    Contest.objects.filter(end__lte=now).update(similarity_checked_at=now)


class Migration(migrations.Migration):

    dependencies = [
        ("contests", "0013_voidedproblem"),
    ]

    operations = [
        migrations.AddField(
            model_name="contest",
            name="similarity_checked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(past_rounds_are_done, migrations.RunPython.noop),
    ]
