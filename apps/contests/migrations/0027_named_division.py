# The old rounds are named after the division that fits them (the players' ratings and the problems' levels at the
# time); it is a name only: they stay open, so a replay of the ratings rates everyone as it did.

from django.db import migrations, models

NAMED = {1: 5, 2: 5, 3: 5, 4: 5, 5: 5, 6: 5, 7: 4, 8: 4, 9: 4, 10: 4, 11: 4, 12: 4}  # Round number -> Div.


def name(apps, schema_editor):
    Contest = apps.get_model("contests", "Contest")
    for c in Contest.objects.filter(kind="round", division=0, number__in=NAMED):
        c.named_division = NAMED[c.number]
        c.title = f"CodeArena Round #{c.number} (Div. {c.named_division})"
        c.save(update_fields=["named_division", "title"])


def unname(apps, schema_editor):
    Contest = apps.get_model("contests", "Contest")
    for c in Contest.objects.filter(named_division__gt=0):
        c.title = f"CodeArena Round #{c.number}"
        c.save(update_fields=["title"])


class Migration(migrations.Migration):

    dependencies = [("contests", "0026_number_existing_contests")]

    operations = [
        migrations.AddField(model_name="contest", name="named_division",
                            field=models.PositiveSmallIntegerField(default=0, editable=False)),
        migrations.RunPython(name, unname),
    ]
