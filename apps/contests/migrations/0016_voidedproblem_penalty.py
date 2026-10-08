from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contests", "0015_contest_badge"),
    ]

    operations = [
        migrations.AddField(
            model_name="voidedproblem",
            name="penalty",
            field=models.BooleanField(default=False),
        ),
    ]
