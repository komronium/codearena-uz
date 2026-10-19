from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("classroom", "0010_remove_live_quiz"),
    ]

    operations = [
        migrations.DeleteModel(name="AssignmentProblem"),
        migrations.DeleteModel(name="Assignment"),
        migrations.DeleteModel(name="ReviewComment"),
    ]
