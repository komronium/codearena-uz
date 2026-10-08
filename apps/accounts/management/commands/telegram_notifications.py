"""Queue today's daily problem and one-hour contest reminders; recover pending delivery jobs."""
import datetime
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import TelegramLink, TelegramLinkToken, TelegramOutbox
from apps.accounts.telegram import queue_notification, recover_outbox
from apps.contests.models import Contest
from apps.problems.daily import daily_for


class Command(BaseCommand):
    help = "Queue Telegram daily-problem and contest notifications, and retry the outbox."

    def handle(self, *args, **options):
        now = timezone.now()
        TelegramLinkToken.objects.filter(expires_at__lt=now - timedelta(days=7)).delete()
        TelegramOutbox.objects.filter(
            status__in=[TelegramOutbox.Status.SENT, TelegramOutbox.Status.FAILED],
            created_at__lt=now - timedelta(days=90),
        ).delete()
        if not settings.TELEGRAM_BOT_TOKEN:
            return
        daily = daily_for()
        if daily:
            url = f"{settings.SITE_URL.rstrip('/')}/problems/{daily.problem.slug}/"
            text = f"CodeArena · Bugungi masala\n{daily.problem.title}\n{url}"
            for user_id in TelegramLink.objects.filter(
                is_active=True, notify_daily_problem=True, user__is_active=True
            ).values_list("user_id", flat=True).iterator():
                queue_notification(user_id, "notify_daily_problem", f"daily:{daily.date.isoformat()}", text)

        upcoming = Contest.objects.filter(start__gt=now, start__lte=now + datetime.timedelta(hours=1))
        for contest in upcoming.iterator():
            when = timezone.localtime(contest.start).strftime("%d.%m, %H:%M")
            url = f"{settings.SITE_URL.rstrip('/')}/contests/{contest.pk}/"
            text = f"CodeArena · Musobaqa 1 soat ichida\n{contest.title}\nBoshlanishi: {when}\n{url}"
            user_ids = (TelegramLink.objects.filter(
                is_active=True, notify_contests=True, user__is_active=True,
                user__participations__contest=contest, user__participations__disqualified=False,
            ).values_list("user_id", flat=True).distinct())
            for user_id in user_ids.iterator():
                queue_notification(user_id, "notify_contests", f"contest:{contest.pk}:start", text)

        recover_outbox()
