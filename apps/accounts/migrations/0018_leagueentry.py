import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0017_telegramloginrequest"),
    ]

    operations = [
        migrations.CreateModel(
            name="LeagueEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("week", models.DateField()),
                ("tier", models.PositiveSmallIntegerField(default=0)),
                ("group", models.PositiveIntegerField(default=1)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="league_entries", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "indexes": [models.Index(fields=["week", "tier", "group"], name="accounts_le_week_e09ef5_idx")],
            },
        ),
        migrations.AddConstraint(
            model_name="leagueentry",
            constraint=models.UniqueConstraint(fields=("user", "week"), name="one_league_entry_per_week"),
        ),
    ]
