from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0034_remove_user_official_rating_remove_user_verified_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='telegramlink',
            name='notify_digest',
            field=models.BooleanField(default=True),
        ),
    ]
