from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("learn", "0005_studyplan_source_lang"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlanDone",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("done_at", models.DateTimeField(auto_now_add=True)),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="dones", to="learn.studyplan")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="plan_dones", to=settings.AUTH_USER_MODEL)),
            ],
            options={"unique_together": {("user", "plan")}},
        ),
    ]
