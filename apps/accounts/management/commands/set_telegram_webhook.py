"""Register the production Telegram bot webhook using the configured secret header."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.telegram import bot_api


class Command(BaseCommand):
    help = "Set Telegram webhook to SITE_URL/accounts/telegram/webhook/."

    def handle(self, *args, **options):
        if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_WEBHOOK_SECRET:
            raise CommandError("Set TELEGRAM_BOT_TOKEN and TELEGRAM_WEBHOOK_SECRET first.")
        url = f"{settings.SITE_URL.rstrip('/')}/accounts/telegram/webhook/"
        bot_api("setWebhook", {
            "url": url,
            "secret_token": settings.TELEGRAM_WEBHOOK_SECRET,
            "allowed_updates": ["message"],
            "drop_pending_updates": False,
        })
        self.stdout.write(self.style.SUCCESS(f"Telegram webhook configured: {url}"))
