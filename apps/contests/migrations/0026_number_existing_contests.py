# Seeds the five divisions and gives every existing contest its kind and number: the marathons count on their own,
# everything else (Round, Mini, Monday, Weekend) becomes a Round, numbered in the order they were played.

import re

from django.db import migrations

DIVISIONS = {1: (1500, None), 2: (None, 1500), 3: (None, 1300), 4: (None, 1100), 5: (None, 900)}


def number(apps, schema_editor):
    Contest = apps.get_model("contests", "Contest")
    DivisionRange = apps.get_model("contests", "DivisionRange")
    for n, (floor, ceiling) in DIVISIONS.items():
        DivisionRange.objects.get_or_create(number=n, defaults={"floor": floor, "ceiling": ceiling})
    counters = {"round": 0, "marathon": 0}
    for c in Contest.objects.order_by("start", "pk"):
        kind = "marathon" if re.search(r"marathon", c.title, re.I) else "round"
        counters[kind] += 1
        c.kind, c.number = kind, counters[kind]
        c.title = f"CodeArena {kind.capitalize()} #{c.number}" + (f" (Div. {c.division})" if c.division else "")
        c.save(update_fields=["kind", "number", "title"])
    # the title is built now, in every language: the English drafts of the old titles are no longer used
    ContentTranslation = apps.get_model("translations", "ContentTranslation")
    ContentTranslation.objects.filter(content_type__app_label="contests", content_type__model="contest", field="title").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("contests", "0025_divisions_and_numbered_titles"),
        ("translations", "0001_initial"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [migrations.RunPython(number, migrations.RunPython.noop)]
