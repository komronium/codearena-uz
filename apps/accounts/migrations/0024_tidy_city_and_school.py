from django.db import migrations

from apps.accounts.places import canon_city, canon_school


def tidy(apps, schema_editor):
    """Old free-text cities and schools to the pickers' spellings ("Bukhara" -> "Buxoro"; "OXU 2-ATT-25" ->
    "Osiyo xalqaro universiteti"). Users without a country are Uzbek ones from before the field existed."""
    User = apps.get_model("accounts", "User")
    for user in User.objects.exclude(location="", school=""):
        country = user.country or "UZ"
        location, school = canon_city(country, user.location), canon_school(country, user.school)
        if (location, school) != (user.location, user.school):
            User.objects.filter(pk=user.pk).update(location=location, school=school)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0023_notification"),
    ]

    operations = [
        migrations.RunPython(tidy, migrations.RunPython.noop),
    ]
