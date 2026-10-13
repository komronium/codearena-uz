import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0019_user_duel_season"),
    ]

    operations = [
        migrations.CreateModel(
            name="Follow",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("target", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="followers", to=settings.AUTH_USER_MODEL)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="following", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="follow",
            constraint=models.UniqueConstraint(fields=("user", "target"), name="one_follow_per_pair"),
        ),
        migrations.AddConstraint(
            model_name="follow",
            constraint=models.CheckConstraint(condition=models.Q(("user", models.F("target")), _negated=True), name="no_self_follow"),
        ),
    ]
