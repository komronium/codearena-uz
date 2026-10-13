from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0018_leagueentry"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="duel_season",
            field=models.CharField(blank=True, default="", max_length=7),
        ),
    ]
