import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("learn", "0003_studyplan_updated"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PlanRead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("read_at", models.DateTimeField(auto_now_add=True)),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reads", to="learn.studyplan")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="plan_reads", to=settings.AUTH_USER_MODEL)),
            ],
            options={"unique_together": {("user", "plan")}},
        ),
    ]
