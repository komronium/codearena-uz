import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("learn", "0002_courses_from_tags"),
    ]

    operations = [
        migrations.AddField(
            model_name="studyplan",
            name="updated",
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
