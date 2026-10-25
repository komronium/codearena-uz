from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classroom', '0015_duelanswer_away'),
    ]

    operations = [
        migrations.AddField(
            model_name='duel',
            name='friend',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='duel',
            name='unranked',
            field=models.BooleanField(default=False),
        ),
    ]
