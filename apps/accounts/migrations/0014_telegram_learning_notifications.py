from django.db import migrations, models


def discard_queued_submission_alerts(apps, schema_editor):
    TelegramOutbox = apps.get_model("accounts", "TelegramOutbox")
    TelegramOutbox.objects.filter(
        preference="notify_submissions",
        status__in=["pending", "sending"],
    ).update(status="failed", last_error="Submission notifications were removed")


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0013_telegram_notifications"),
    ]

    operations = [
        migrations.RunPython(discard_queued_submission_alerts, migrations.RunPython.noop),
        migrations.RemoveField(model_name="telegramlink", name="notify_submissions"),
        migrations.AddField(
            model_name="telegramlink",
            name="notify_daily_tip",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="telegramlink",
            name="notify_trending_problem",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="telegramlink",
            name="notify_assignments",
            field=models.BooleanField(default=True),
        ),
    ]
