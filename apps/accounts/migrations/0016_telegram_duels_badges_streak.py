from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0015_userbadge"),
    ]

    operations = [
        migrations.AddField(model_name="telegramlink", name="notify_duels", field=models.BooleanField(default=True)),
        migrations.AddField(model_name="telegramlink", name="notify_badges", field=models.BooleanField(default=True)),
        migrations.AddField(model_name="telegramlink", name="notify_streak", field=models.BooleanField(default=True)),
    ]
