"""Queue today's daily problem and one-hour contest reminders; recover pending delivery jobs."""
import datetime
from datetime import timedelta
from html import escape

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from apps.accounts.models import TelegramLink, TelegramLinkToken, TelegramOutbox
from apps.accounts.telegram import queue_notification, recover_outbox
from apps.contests.models import Contest
from apps.problems.daily import daily_for
from apps.submissions.models import Submission


DAILY_TIPS = (
    "Masalani kodlashdan oldin kirish va chiqish formatini o‘qing. Kichik misolni qo‘lda yechib, algoritm nima qilishi kerakligini aniqlang.",
    "Chekka holatlarni tekshiring: n=1, eng kichik qiymatlar, takroriy sonlar va javob chegaralari ko‘p xatolarni topadi.",
    "Murakkablikni baholang: n 10⁵ bo‘lsa, O(n²) algoritm odatda sekinlik qiladi. Avval yechimning vaqt va xotira sarfini hisoblang.",
    "Katta yechimdan oldin kichik brute-force yozib ko‘ring. Tasodifiy kichik testlarda tez algoritm bilan solishtirish xatolarni topishga yordam beradi.",
    "Xato javob chiqsa, bir o‘zgarishni tekshiring: oraliq qiymatlar, sikl chegarasi va indekslar. Debug chiqarishlarini yakuniy javobdan olib tashlang.",
    "Yechimni topshirishdan oldin namunadan tashqari o‘zingiz tuzgan kamida bitta testda ham sinang.",
    "Masalani yechgach, boshqa yechimni o‘qing va o‘zingiznikiga solishtiring. Yangi g‘oyani keyingi masalada qo‘llab ko‘ring.",
)


class Command(BaseCommand):
    help = "Queue Telegram daily learning, trending problem, contest and assignment notifications."

    def handle(self, *args, **options):
        now = timezone.now()
        TelegramLinkToken.objects.filter(expires_at__lt=now - timedelta(days=7)).delete()
        TelegramOutbox.objects.filter(
            status__in=[TelegramOutbox.Status.SENT, TelegramOutbox.Status.FAILED],
            created_at__lt=now - timedelta(days=90),
        ).delete()
        if not settings.TELEGRAM_BOT_TOKEN:
            return
        site_url = settings.SITE_URL.rstrip("/")
        daily = daily_for()
        day = timezone.localdate()
        if daily:
            url = f"{site_url}/problems/{daily.problem.slug}/"
            text = (
                f"<b>📅 Bugungi masala</b>\n\n"
                f"<b>{escape(daily.problem.title)}</b>\n"
                f'<a href="{url}">Masalani ochish →</a>'
            )
            for user_id in TelegramLink.objects.filter(
                is_active=True, notify_daily_problem=True, user__is_active=True
            ).values_list("user_id", flat=True).iterator():
                queue_notification(user_id, "notify_daily_problem", f"daily:{daily.date.isoformat()}", text)

        tip = DAILY_TIPS[day.toordinal() % len(DAILY_TIPS)]
        tip_text = (
            f"<b>💡 Kunlik tavsiya</b>\n\n{escape(tip)}\n\n"
            f'<a href="{site_url}/problems/">Yechishga o‘tish →</a>'
        )
        for user_id in TelegramLink.objects.filter(
            is_active=True, notify_daily_tip=True, user__is_active=True
        ).values_list("user_id", flat=True).iterator():
            queue_notification(user_id, "notify_daily_tip", f"tip:{day.isoformat()}", tip_text)

        # Pick among today's top five practice problems by distinct users who tried them
        # during the last week. Rotate ties/trending candidates by date and skip the daily pick.
        trending = list(Submission.objects.filter(
            created__gte=now - timedelta(days=7), contest__isnull=True,
            problem__is_public=True, problem__status="approved",
        ).values("problem_id").annotate(
            people=Count("user_id", distinct=True), attempts=Count("pk"),
        ).order_by("-people", "-attempts", "problem_id").values_list("problem_id", flat=True)[:10])
        if daily:
            trending = [problem_id for problem_id in trending if problem_id != daily.problem_id]
        if trending:
            from apps.problems.models import Problem

            trend_problem = Problem.objects.filter(pk=trending[day.toordinal() % min(5, len(trending))]).first()
            if trend_problem:
                trend_url = f"{site_url}/problems/{trend_problem.slug}/"
                trend_text = (
                    f"<b>🔥 Trenddagi masala</b>\n\n"
                    f"<b>{escape(trend_problem.title)}</b>\n"
                    "So‘nggi 7 kunda ko‘p foydalanuvchi sinab ko‘rgan masala.\n\n"
                    f'<a href="{trend_url}">Masalani ochish →</a>'
                )
                for user_id in TelegramLink.objects.filter(
                    is_active=True, notify_trending_problem=True, user__is_active=True
                ).values_list("user_id", flat=True).iterator():
                    queue_notification(user_id, "notify_trending_problem", f"trending:{day.isoformat()}", trend_text)

        upcoming = Contest.objects.filter(start__gt=now, start__lte=now + datetime.timedelta(hours=1))
        for contest in upcoming.iterator():
            when = timezone.localtime(contest.start).strftime("%d.%m, %H:%M")
            url = f"{site_url}/contests/{contest.pk}/"
            text = (
                f"<b>🏆 Musobaqa 1 soat ichida</b>\n\n"
                f"<b>{escape(contest.title)}</b>\n"
                f"Boshlanishi: {when}\n\n"
                f'<a href="{url}">Musobaqani ko‘rish →</a>'
            )
            user_ids = (TelegramLink.objects.filter(
                is_active=True, notify_contests=True, user__is_active=True,
                user__participations__contest=contest, user__participations__disqualified=False,
            ).values_list("user_id", flat=True).distinct())
            for user_id in user_ids.iterator():
                queue_notification(user_id, "notify_contests", f"contest:{contest.pk}:start", text)

        recover_outbox()
