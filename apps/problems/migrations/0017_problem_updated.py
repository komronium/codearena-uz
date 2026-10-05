import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("problems", "0016_problem_rating"),
    ]

    operations = [
        migrations.AddField(
            model_name="problem",
            name="updated",
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
