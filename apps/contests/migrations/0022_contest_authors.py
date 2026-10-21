from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("contests", "0021_contest_source_lang"),
    ]

    operations = [
        migrations.AddField(
            model_name="contest",
            name="authors",
            field=models.ManyToManyField(blank=True, related_name="authored_contests", to=settings.AUTH_USER_MODEL),
        ),
    ]
