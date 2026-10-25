"""Queue the morning message (today's problem, a tip, what is trending), new-round announcements, one-hour contest
reminders and the evening streak warning; recover pending delivery jobs."""
import datetime
from datetime import timedelta
from html import escape

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count, Q
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


MORNING_FROM = 9  # local hour: the morning message goes after this, in one piece, not three at midnight
ANNOUNCE_DAYS = 7  # a round is announced once its start is this close
STREAK_HOURS = (19, 21)  # the evening check runs in the first quarter of these hours, not every five minutes until midnight


def push(user_ids, preference: str, key: str, build, quiet: bool | None = None) -> None:
    """Queue one message to each user in that user's own language: `build()` is called once per language, with it active."""
    from apps.accounts.models import User

    by_lang: dict = {}
    for uid, lang in User.objects.filter(pk__in=list(user_ids)).values_list("pk", "language"):
        by_lang.setdefault(lang or settings.LANGUAGE_CODE, []).append(uid)
    for lang, ids in by_lang.items():
        with translation.override(lang):
            text = build()
        for uid in ids:
            queue_notification(uid, preference, key, text, quiet=quiet)


def trending_problem(now, daily, day):
    """One of today's top five practice problems by distinct users who tried them in the last week, rotated by date,
    skipping the daily pick."""
    trending = list(Submission.objects.filter(
        created__gte=now - timedelta(days=7), contest__isnull=True,
        problem__is_public=True, problem__status="approved",
    ).values("problem_id").annotate(
        people=Count("user_id", distinct=True), attempts=Count("pk"),
    ).order_by("-people", "-attempts", "problem_id").values_list("problem_id", flat=True)[:10])
    if daily:
        trending = [problem_id for problem_id in trending if problem_id != daily.problem_id]
    if not trending:
        return None
    from apps.problems.models import Problem

    return Problem.objects.filter(pk=trending[day.toordinal() % min(5, len(trending))]).first()


def morning(now, site_url, daily, day) -> None:
    """One message a day with what each person asked for: today's problem, what is trending and a tip."""
    trend = trending_problem(now, daily, day)
    tip = DAILY_TIPS[day.toordinal() % len(DAILY_TIPS)]
    groups: dict = {}
    links = (TelegramLink.objects.filter(is_active=True, user__is_active=True)
             .filter(Q(notify_daily_problem=True) | Q(notify_trending_problem=True) | Q(notify_daily_tip=True))
             .values_list("user_id", "user__language", "notify_daily_problem", "notify_trending_problem", "notify_daily_tip"))
    for uid, lang, want_daily, want_trend, want_tip in links:
        groups.setdefault((lang or settings.LANGUAGE_CODE, bool(want_daily and daily), bool(want_trend and trend),
                           bool(want_tip)), []).append((uid, want_daily, want_trend))
    for (lang, has_daily, has_trend, has_tip), people in groups.items():
        if not (has_daily or has_trend or has_tip):
            continue
        with translation.override(lang):
            lines = ["<b>" + _t("☀️ Bugun CodeArena’da") + "</b>", ""]
            if has_daily:
                lines.append("📅 " + _t("Kun masalasi:") + f' <a href="{site_url}/problems/{daily.problem.slug}/">'
                             + escape(localized(daily.problem, "title")) + "</a>")
            if has_trend:
                lines.append("🔥 " + _t("Trenddagi:") + f' <a href="{site_url}/problems/{trend.slug}/">' + escape(localized(trend, "title")) + "</a>")
            if has_tip:
                lines += ["", "💡 " + escape(str(tip))]
            lines += ["", f'<a href="{site_url}/problems/">' + _t("Yechishga o‘tish →") + "</a>"]
            text = "\n".join(lines)
        for uid, want_daily, want_trend in people:
            pref = "notify_daily_problem" if want_daily else "notify_trending_problem" if want_trend else "notify_daily_tip"
            queue_notification(uid, pref, f"morning:{day.isoformat()}", text)


def announce_rounds(now, site_url) -> None:
    """Tell people who are not in a round yet that it is coming: once each, a week ahead."""
    for contest in Contest.objects.filter(is_draft=False, start__gt=now, start__lte=now + timedelta(days=ANNOUNCE_DAYS)):
        when = timezone.localtime(contest.start).strftime("%d.%m, %H:%M")
        url = f"{site_url}/contests/{contest.pk}/"
        ids = (TelegramLink.objects.filter(is_active=True, notify_contests=True, user__is_active=True)
               .exclude(user__participations__contest=contest).values_list("user_id", flat=True).distinct())
        push(ids, "notify_contests", f"contest:{contest.pk}:new",
             lambda contest=contest, when=when, url=url: (
                 "<b>" + _t("🆕 Yangi musobaqa") + f"</b>\n\n<b>{escape(localized(contest, 'title'))}</b>\n"
                 + _t("Boshlanishi: {when}").format(when=when) + "\n\n" + f'<a href="{url}">' + _t("Ro‘yxatdan o‘tish →") + "</a>"),
             quiet=True)


class Command(BaseCommand):
    help = "Queue the Telegram morning message, new-round announcements, contest reminders and streak warnings."

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
        local = timezone.localtime(now)

        if local.hour >= MORNING_FROM:
            morning(now, site_url, daily, day)
        announce_rounds(now, site_url)

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
                     + f'<a href="{url}">' + _t("Musobaqani ko‘rish →") + "</a>"), quiet=False)

        # in the evening, a nudge to anyone whose daily streak breaks tonight: a run going, today not solved yet. Checked at
        # the start of two evening hours only (each person is told once a day, whatever the key), and not for those already told.
        if daily and local.hour in STREAK_HOURS and local.minute < 15:
            from apps.problems.daily import streaks
            from apps.problems.models import DailySolve
            from apps.problems.quests import today_quests

            solved_today = set(DailySolve.objects.filter(daily=daily).values_list("user_id", flat=True))
            told = set(TelegramOutbox.objects.filter(event_key=f"streak:{day.isoformat()}").values_list("link__user_id", flat=True))
            url = f"{site_url}/problems/{daily.problem.slug}/"
            for link in (TelegramLink.objects.filter(is_active=True, notify_streak=True, user__is_active=True)
                         .exclude(user_id__in=solved_today | told).select_related("user").iterator()):
                if today_quests(link.user)["done"]:
                    continue  # any quest already keeps the Olov
                run = streaks(link.user)[0]
                if run < 1:
                    continue
                push([link.user_id], "notify_streak", f"streak:{day.isoformat()}",
                     lambda run=run: (
                         "<b>" + _t("🔥 Olov o‘chmasin!") + "</b>\n\n"
                         + _t("Ketma-ket <b>{run}</b> kun faol bo‘ldingiz. Bugun hali hech narsa qilmadingiz — yarim tungacha kun masalasini yoki bitta vazifani bajarsangiz, Olov <b>{next}</b> kun bo‘ladi.").format(run=run, next=run + 1)
                         + "\n\n" + f'<a href="{url}">{escape(localized(daily.problem, "title"))} →</a>'), quiet=False)

        recover_outbox()
