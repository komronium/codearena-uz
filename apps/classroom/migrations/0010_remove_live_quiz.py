# The teachers' live quiz is gone (2026-10-18): its three tables, answers and players first.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('classroom', '0009_duel_finished_at'),
    ]

    operations = [
        migrations.DeleteModel(name='LiveQuizAnswer'),
        migrations.DeleteModel(name='LiveQuizPlayer'),
        migrations.DeleteModel(name='LiveQuiz'),
    ]
