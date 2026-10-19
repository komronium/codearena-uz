from django.db import migrations

from apps.accounts.places import CITIES


def backfill(apps, schema_editor):
    """Users who named an Uzbek city before the country field existed are in Uzbekistan: give them the country,
    so their flag shows and the place filters find them."""
    User = apps.get_model("accounts", "User")
    cities = [city for _, group in CITIES["UZ"] for city in group]
    User.objects.filter(country="", location__in=cities).update(country="UZ")


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0024_tidy_city_and_school"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
