from typing import ClassVar

from django.conf import settings
from django.db import models

from apps.contests.models import Contest
from apps.problems.models import Language, Problem
from apps.submissions.models import Submission
from django.utils.translation import gettext_lazy as _tl


class FocusEvent(models.Model):
    class Kind(models.TextChoices):
        BLUR = "blur"
        FOCUS = "focus"
        PASTE = "paste"
        COPY = "copy"
        FAST = "fast"  # sustained abnormal typing speed (evades the single-bulk-insert threshold)
        VIEW = "view"  # a contest problem page was opened: start of that problem's clock

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="focus_events")
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name="focus_events")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    # the contest problem page it happened on; None on the contest's own page
    problem = models.ForeignKey(Problem, null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    # on FOCUS: how long the participant was away since the matching BLUR
    away_ms = models.PositiveIntegerField(null=True, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes: ClassVar[list[models.Index]] = [models.Index(fields=["contest", "user"])]


class SimilarityFlag(models.Model):
    submission_a = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="+")
    submission_b = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="+")
    score = models.FloatField()
    reviewed = models.BooleanField(default=False)
    note = models.TextField(blank=True)
    # from one participant's deep check (flag_similarity --user), which compares every attempt:
    # the round's own sweep, comparing ACs and last tries, doesn't drop it
    deep = models.BooleanField(default=False)

    class Meta:
        ordering = ["-score"]


class CodeSnapshot(models.Model):
    """Editor contents saved every few seconds during a contest, so staff can replay
    how a solution was written: typed and reworked, or transcribed top to bottom."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name="+")
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name="+")
    language = models.ForeignKey(Language, null=True, on_delete=models.SET_NULL, related_name="+")
    source = models.TextField()
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes: ClassVar[list[models.Index]] = [models.Index(fields=["contest", "user", "problem", "at"])]


class DeviceSeen(models.Model):
    """A browser (random id kept in its localStorage) a participant used during a contest,
    from the tracker heartbeat. Two users on one device, or one user on two devices at
    the same time, is evidence for staff."""
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name="+")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    device = models.CharField(max_length=64)
    ip = models.GenericIPAddressField(null=True, blank=True)  # the last one seen
    first_at = models.DateTimeField(auto_now_add=True)
    last_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("contest", "user", "device")


class AuditEntry(models.Model):
    """Who did what to a result, and why. Links are SET_NULL so the record outlives them."""
    class Action(models.TextChoices):
        DISQUALIFY = "disqualify", _tl("Diskvalifikatsiya")
        REQUALIFY = "requalify", _tl("Diskvalifikatsiya bekor")
        VOID = "void", _tl("Masala natijasi bekor")
        UNVOID = "unvoid", _tl("Masala natijasi tiklandi")
        PENALTY = "penalty", _tl("AI jarimasi: xato urinish, masala bloklandi")
        REJUDGE = "rejudge", _tl("Qayta tekshiruv")
        PUBLISH = "publish", _tl("Masalalar ochildi")
        RATING_APPLY = "rating_apply", _tl("Reyting hisoblandi")
        RATING_RECOMPUTE = "rating_recompute", _tl("Reyting qayta hisoblandi")
        FLAG_REVIEW = "flag_review", _tl("O‘xshashlik ko‘rildi")
        PROBLEM_DELETE = "problem_delete", _tl("Masala o‘chirildi")
        DAILY_SELECT = "daily_select", _tl("Kun masalasi tanlandi")
        CONTEST_DELETE = "contest_delete", _tl("Musobaqa o‘chirildi")
        USER_DELETE = "user_delete", _tl("Foydalanuvchi o‘chirildi")
        VERIFY = "verify", _tl("Shaxsi tasdiqlandi")
        UNVERIFY = "unverify", _tl("Shaxs tasdig‘i bekor")
        OFFICIAL_REVIEW = "official_review", _tl("Kodini tushuntirdi")
        OFFICIAL_APPLY = "official_apply", _tl("Rasmiy reyting qo‘llandi")
        PROBLEM_TOGGLE = "problem_toggle", _tl("Masala ko‘rinishi o‘zgardi")
        TAG_DELETE = "tag_delete", _tl("Mavzu o‘chirildi")
        PLAN_DELETE = "plan_delete", _tl("Kurs o‘chirildi")
        USER_EDIT = "user_edit", _tl("Foydalanuvchi tahrirlandi")
        CONTEST_EDIT = "contest_edit", _tl("Musobaqa tahrirlandi")
        UNPUBLISH = "unpublish", _tl("Masalalar yopildi")
        DUEL_VOID = "duel_void", _tl("Duel bekor qilindi")
        DAILY_SWAP = "daily_swap", _tl("Kun masalasi almashtirildi")
        DRAFT_PUBLISH = "draft_publish", _tl("Qoralama raund e’lon qilindi")

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=20, choices=Action.choices)
    contest = models.ForeignKey(Contest, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    subject = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="+")
    note = models.CharField(max_length=300, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-at", "-id"]


class PracticeEvent(models.Model):
    """What the practice editor saw, for spotting solves copied from an AI: a paste attempt, code
    that appeared at once, the page opened, time spent in another window. Practice is not
    policed like a contest; these only feed the teacher's report (practice_report)."""
    class Kind(models.TextChoices):
        VIEW = "view"    # the problem page was opened
        PASTE = "paste"  # a long paste or drop into the editor (blocked on Beginner/Easy)
        BULK = "bulk"    # a large block of code appeared in one go, or typing too fast to be typing
        AWAY = "away"    # back from another window or tab; away_ms says how long

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name="+")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    away_ms = models.PositiveIntegerField(null=True, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes: ClassVar[list[models.Index]] = [models.Index(fields=["user", "problem", "at"])]


class PracticeReview(models.Model):
    """A teacher's decision on a practice solve the report flagged. Confirmed: it was not the
    student's own work, so it earns no practice points (sync_practice_points leaves it out)."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name="+")
    confirmed = models.BooleanField()  # False: looked at, nothing wrong
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "problem")


class PracticeSnapshot(models.Model):
    """The practice editor's contents every few seconds and at each submit (the last KEEP per
    student and problem), so the server can tell code written in the editor from code that
    arrived some other way — which blocking the browser script can't hide."""
    KEEP = 60

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name="+")
    source = models.TextField()
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes: ClassVar[list[models.Index]] = [models.Index(fields=["user", "problem", "at"])]


class Report(models.Model):
    """What a signed-in user tells staff: a report about another user (a profile, a duel) or an appeal against
    their own result in a contest. Staff read them at /integrity/reports/ and mark them done."""
    class Kind(models.TextChoices):
        USER = "user", _tl("Shikoyat")
        APPEAL = "appeal", _tl("Apellyatsiya")

    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    target = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="+")
    contest = models.ForeignKey(Contest, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    link = models.CharField(max_length=300, blank=True)  # the page it was sent from
    text = models.CharField(max_length=600)
    created = models.DateTimeField(auto_now_add=True)
    done_at = models.DateTimeField(null=True, blank=True)
    done_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="+")
    outcome = models.CharField(max_length=400, blank=True)  # what staff tell the reporter when they close it

    class Meta:
        ordering = ["done_at", "-created", "-id"]
