"""A short Telegram summary on Monday mornings: your rating, the practice points, the next round and today's problem.
Safe to run every few minutes: the event key holds one message per person per ISO week."""
from html import escape

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import TelegramLink
from apps.accounts.telegram import queue_notification
from apps.contests.models import Contest
from apps.problems.daily import daily_for


class Command(BaseCommand):
    help = "Queue the Monday Telegram digest (once per person per week)."

    def handle(self, *args, **options):
        now = timezone.localtime()
        if not settings.TELEGRAM_BOT_TOKEN or now.weekday() != 0 or now.hour < 9:
            return
        week = now.isocalendar()
        site = settings.SITE_URL.rstrip("/")
        nxt = Contest.objects.filter(start__gt=timezone.now()).order_by("start").first()
        daily = daily_for()
        queued = 0
        for link in TelegramLink.objects.filter(is_active=True, notify_contests=True).select_related("user"):
            u = link.user
            lines = ["<b>📊 Haftalik xulosa</b>", ""]
            lines.append(f"Musobaqa reytingi: <b>{u.rating}</b> · amaliyot balli: <b>{u.practice_points}</b>")
            if nxt:
                lines.append(f'Keyingi musobaqa: <a href="{site}/contests/{nxt.pk}/">{escape(nxt.title)}</a>, '
                             f"{timezone.localtime(nxt.start):%d.%m %H:%M} (UTC+5)")
            if daily:
                lines.append(f'Bugungi masala: <a href="{site}/problems/{daily.problem.slug}/">{escape(daily.problem.title)}</a>')
            queue_notification(u.pk, "notify_contests", f"weekly:{week.year}-{week.week}", "\n".join(lines))
            queued += 1
        self.stdout.write(f"{queued} digest(s) queued")
