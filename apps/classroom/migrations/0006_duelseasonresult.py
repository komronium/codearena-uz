import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("classroom", "0005_duel_quiz"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DuelSeasonResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("season", models.CharField(max_length=7)),
                ("rank", models.PositiveSmallIntegerField()),
                ("rating", models.IntegerField()),
                ("duels", models.PositiveIntegerField()),
                ("user", models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name="duel_medals", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["season", "rank"]},
        ),
        migrations.AddConstraint(
            model_name="duelseasonresult",
            constraint=models.UniqueConstraint(fields=("season", "rank"), name="one_user_per_season_rank"),
        ),
    ]
