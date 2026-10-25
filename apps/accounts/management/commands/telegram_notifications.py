"""Queue today's daily problem and one-hour contest reminders; recover pending delivery jobs."""
import datetime
from datetime import timedelta
from html import escape

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone, translation
from django.utils.translation import gettext as _t, gettext_lazy as _tl

from apps.accounts.models import TelegramLink, TelegramLinkToken, TelegramOutbox
from apps.accounts.telegram import queue_notification, recover_outbox
from apps.contests.models import Contest
from apps.problems.daily import daily_for
from apps.submissions.models import Submission
from apps.translations.mixin import localized


DAILY_TIPS = (
    _tl("Masalani kodlashdan oldin kirish va chiqish formatini o‘qing. Kichik misolni qo‘lda yechib, algoritm nima qilishi kerakligini aniqlang."),
    _tl("Chekka holatlarni tekshiring: n=1, eng kichik qiymatlar, takroriy sonlar va javob chegaralari ko‘p xatolarni topadi."),
    _tl("Murakkablikni baholang: n 10⁵ bo‘lsa, O(n²) algoritm odatda sekinlik qiladi. Avval yechimning vaqt va xotira sarfini hisoblang."),
    _tl("Katta yechimdan oldin kichik brute-force yozib ko‘ring. Tasodifiy kichik testlarda tez algoritm bilan solishtirish xatolarni topishga yordam beradi."),
    _tl("Xato javob chiqsa, bir o‘zgarishni tekshiring: oraliq qiymatlar, sikl chegarasi va indekslar. Debug chiqarishlarini yakuniy javobdan olib tashlang."),
    _tl("Yechimni topshirishdan oldin namunadan tashqari o‘zingiz tuzgan kamida bitta testda ham sinang."),
    _tl("Masalani yechgach, boshqa yechimni o‘qing va o‘zingiznikiga solishtiring. Yangi g‘oyani keyingi masalada qo‘llab ko‘ring."),
)


def push(user_ids, preference: str, key: str, build) -> None:
    """Queue one message to each user in that user's own language: `build()` is called once per language, with it active."""
    from apps.accounts.models import User

    by_lang: dict = {}
    for uid, lang in User.objects.filter(pk__in=list(user_ids)).values_list("pk", "language"):
        by_lang.setdefault(lang or settings.LANGUAGE_CODE, []).append(uid)
    for lang, ids in by_lang.items():
        with translation.override(lang):
            text = build()
        for uid in ids:
            queue_notification(uid, preference, key, text)


class Command(BaseCommand):
    help = "Queue Telegram daily learning, trending problem, and contest notifications."

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
            push(TelegramLink.objects.filter(is_active=True, notify_daily_problem=True, user__is_active=True)
                 .values_list("user_id", flat=True), "notify_daily_problem", f"daily:{daily.date.isoformat()}",
                 lambda: ("<b>" + _t("📅 Bugungi masala") + f"</b>\n\n<b>{escape(localized(daily.problem, 'title'))}</b>\n"
                          + f'<a href="{url}">' + _t("Masalani ochish →") + "</a>"))

        tip = DAILY_TIPS[day.toordinal() % len(DAILY_TIPS)]
        push(TelegramLink.objects.filter(is_active=True, notify_daily_tip=True, user__is_active=True)
             .values_list("user_id", flat=True), "notify_daily_tip", f"tip:{day.isoformat()}",
             lambda: ("<b>" + _t("💡 Kunlik tavsiya") + f"</b>\n\n{escape(str(tip))}\n\n"
                      + f'<a href="{site_url}/problems/">' + _t("Yechishga o‘tish →") + "</a>"))

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
                push(TelegramLink.objects.filter(is_active=True, notify_trending_problem=True, user__is_active=True)
                     .values_list("user_id", flat=True), "notify_trending_problem", f"trending:{day.isoformat()}",
                     lambda: ("<b>" + _t("🔥 Trenddagi masala") + f"</b>\n\n<b>{escape(localized(trend_problem, 'title'))}</b>\n"
                              + _t("So‘nggi 7 kunda ko‘p foydalanuvchi sinab ko‘rgan masala.") + "\n\n"
                              + f'<a href="{trend_url}">' + _t("Masalani ochish →") + "</a>"))

        upcoming = Contest.objects.filter(start__gt=now, start__lte=now + datetime.timedelta(hours=1))
        for contest in upcoming.iterator():
            when = timezone.localtime(contest.start).strftime("%d.%m, %H:%M")
            url = f"{site_url}/contests/{contest.pk}/"
            user_ids = (TelegramLink.objects.filter(
                is_active=True, notify_contests=True, user__is_active=True,
                user__participations__contest=contest, user__participations__disqualified=False,
            ).values_list("user_id", flat=True).distinct())
            push(user_ids, "notify_contests", f"contest:{contest.pk}:start",
                 lambda contest=contest, when=when, url=url: (
                     "<b>" + _t("🏆 Musobaqa 1 soat ichida") + f"</b>\n\n<b>{escape(localized(contest, 'title'))}</b>\n"
                     + _t("Boshlanishi: {when}").format(when=when) + "\n\n"
                     + f'<a href="{url}">' + _t("Musobaqani ko‘rish →") + "</a>"))

        # in the evening, a nudge to anyone whose daily streak breaks tonight: a run going, today not solved yet
        if daily and timezone.localtime(now).hour >= 19:
            from apps.problems.daily import streaks
            from apps.problems.models import DailySolve
            from apps.problems.quests import today_quests

            solved_today = set(DailySolve.objects.filter(daily=daily).values_list("user_id", flat=True))
            url = f"{site_url}/problems/{daily.problem.slug}/"
            for link in TelegramLink.objects.filter(is_active=True, notify_streak=True, user__is_active=True
                                                    ).select_related("user").iterator():
                if link.user_id in solved_today or today_quests(link.user)["done"]:
                    continue  # the day's problem or any quest already keeps the Olov
                run = streaks(link.user)[0]
                if run < 1:
                    continue
                push([link.user_id], "notify_streak", f"streak:{day.isoformat()}",
                     lambda run=run: (
                         "<b>" + _t("🔥 Olov o‘chmasin!") + "</b>\n\n"
                         + _t("Ketma-ket <b>{run}</b> kun faol bo‘ldingiz. Bugun hali hech narsa qilmadingiz — yarim tungacha kun masalasini yoki bitta vazifani bajarsangiz, Olov <b>{next}</b> kun bo‘ladi.").format(run=run, next=run + 1)
                         + "\n\n" + f'<a href="{url}">{escape(localized(daily.problem, "title"))} →</a>'))

        recover_outbox()
