import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0014_telegram_learning_notifications"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserBadge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("family", models.CharField(max_length=30)),
                ("tier", models.PositiveSmallIntegerField()),
                ("earned_at", models.DateTimeField(auto_now_add=True)),
                ("seen", models.BooleanField(default=False)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="badges", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="userbadge",
            constraint=models.UniqueConstraint(fields=("user", "family", "tier"), name="one_row_per_badge_tier"),
        ),
    ]
