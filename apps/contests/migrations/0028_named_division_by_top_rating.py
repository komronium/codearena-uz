# The old rounds' division names follow the strongest player who took part (the smallest division whose range covers
# everyone), not the median: Round #12 had a 1421 player, so it is Div. 2, not Div. 4. Still a name only.

from django.db import migrations

NAMED = {1: 5, 2: 5, 3: 5, 4: 5, 5: 5, 6: 5, 7: 4, 8: 3, 9: 3, 10: 2, 11: 2, 12: 2}  # Round number -> Div.


def rename(apps, schema_editor):
    Contest = apps.get_model("contests", "Contest")
    for c in Contest.objects.filter(kind="round", division=0, number__in=NAMED):
        c.named_division = NAMED[c.number]
        c.title = f"CodeArena Round #{c.number} (Div. {c.named_division})"
        c.save(update_fields=["named_division", "title"])


class Migration(migrations.Migration):

    dependencies = [("contests", "0027_named_division")]

    operations = [migrations.RunPython(rename, migrations.RunPython.noop)]
