from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("classroom", "0007_livequiz"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="duel",
            name="difficulty",
        ),
        migrations.RemoveField(
            model_name="livequiz",
            name="level",
        ),
    ]
