from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounts", "0033_user_language")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="apple_sub",
            field=models.CharField(blank=True, max_length=64, null=True, unique=True),
        ),
    ]
