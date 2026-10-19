from django.db import migrations, models


def to_students(apps, schema_editor):
    """The teacher role and the homework and review bell lines go with the classroom; teachers are ordinary
    users now (staff keep their is_staff)."""
    apps.get_model("accounts", "User").objects.filter(role="teacher").update(role="student")
    apps.get_model("accounts", "Notification").objects.filter(kind__in=["assignment", "review"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0026_tidy_school_codes"),
        ("classroom", "0011_remove_assignments_and_reviews"),  # the models that point at Group
        ("contests", "0019_remove_require_group"),
    ]

    operations = [
        migrations.RunPython(to_students, migrations.RunPython.noop),
        migrations.RemoveField(model_name="telegramlink", name="notify_assignments"),
        migrations.RemoveField(model_name="user", name="teacher_requested"),
        migrations.AlterField(
            model_name="notification",
            name="kind",
            field=models.CharField(choices=[("duel", "Duel"), ("badge", "Nishon")], max_length=12),
        ),
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(choices=[("student", "Student"), ("admin", "Admin")], default="student", max_length=10),
        ),
        migrations.DeleteModel(name="Group"),
    ]
