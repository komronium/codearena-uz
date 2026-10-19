from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("classroom", "0011_remove_assignments_and_reviews"),
    ]

    operations = [
        migrations.AddField(
            model_name="duelquestion",
            name="origin",
            field=models.CharField(blank=True, db_index=True, max_length=40),
        ),
    ]
