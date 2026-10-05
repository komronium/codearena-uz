import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contests", "0011_contest_rules"),
    ]

    operations = [
        migrations.AddField(
            model_name="contest",
            name="updated",
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
