from django.db import migrations, models
from django.db.models import Max


def backfill(apps, schema_editor):
    """A finished duel's own date: the last answer of the two runs, else the later run deadline (a run
    nobody touched ends at its start + RUN_LIMIT), else when it was created."""
    Duel = apps.get_model("classroom", "Duel")
    DuelAnswer = apps.get_model("classroom", "DuelAnswer")
    for duel in Duel.objects.filter(status="finished").iterator():
        last = DuelAnswer.objects.filter(duel_id=duel.pk).aggregate(m=Max("answered_at"))["m"]
        duel.finished_at = max([x for x in (last, duel.opponent_ends_at, duel.ends_at, duel.created) if x])
        duel.save(update_fields=["finished_at"])


class Migration(migrations.Migration):

    dependencies = [
        ("classroom", "0008_remove_duel_difficulty_remove_livequiz_level"),
    ]

    operations = [
        migrations.AddField(
            model_name="duel",
            name="finished_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
