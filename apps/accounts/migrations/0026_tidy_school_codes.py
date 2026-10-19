from django.db import migrations

from apps.accounts.places import canon_school


def tidy(apps, schema_editor):
    """The group codes and spellings 0024 missed ("2-ATT", "OXU_2-ATT-25", "att 2- kurs") to the institution."""
    User = apps.get_model("accounts", "User")
    for user in User.objects.exclude(school=""):
        school = canon_school(user.country or "UZ", user.school)
        if school != user.school:
            User.objects.filter(pk=user.pk).update(school=school)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0025_backfill_country"),
    ]

    operations = [
        migrations.RunPython(tidy, migrations.RunPython.noop),
    ]
