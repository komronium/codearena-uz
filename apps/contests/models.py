from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.accounts.models import Group
from apps.problems.models import Problem


_UZ_MONTHS_SHORT = "Yan Fev Mar Apr May Iyn Iyl Avg Sen Okt Noy Dek".split()
_UZ_MONTHS = "Yanvar Fevral Mart Aprel May Iyun Iyul Avgust Sentabr Oktabr Noyabr Dekabr".split()


class Contest(models.Model):
    class Type(models.TextChoices):
        # ponytail: single format kept as a field so old rows/migrations stay valid;
        # ICPC was dropped — equal points per problem gives the same ranking.
        SCORE = "score", "Ball"

    title = models.CharField(max_length=200)
    description_md = models.TextField(blank=True)
    start = models.DateTimeField()
    end = models.DateTimeField()
    type = models.CharField(max_length=10, choices=Type.choices, default=Type.SCORE)
    is_rated = models.BooleanField(default=False)
    allowed_ip_prefix = models.CharField(max_length=50, blank=True)
    require_group = models.ForeignKey(Group, null=True, blank=True, on_delete=models.SET_NULL)
    rating_applied = models.BooleanField(default=False)
    # Supervised (lab, or online with a top-N code check): counts toward the official rating
    # once staff apply it (apps.contests.rating.recalc_official).
    is_official = models.BooleanField(default=False)
    official_applied_at = models.DateTimeField(null=True, blank=True)
    # Online official contests: this many top verified finishers must explain their code to staff
    # before the official rating is applied. Ignored for lab contests (allowed_ip_prefix); 0 = no check.
    review_top_n = models.PositiveSmallIntegerField(default=10)
    # Set by staff publishing the ended contest; from then on participants' contest ACs
    # count as practice solves (apps.submissions.solves).
    published_at = models.DateTimeField(null=True, blank=True)
    problems = models.ManyToManyField(Problem, through="ContestProblem", related_name="contests")

    def __str__(self):
        return self.title

    @property
    def is_running(self) -> bool:
        now = timezone.now()
        return self.start <= now < self.end

    @property
    def duration_label(self) -> str:
        minutes = int((self.end - self.start).total_seconds() // 60)
        h, m = divmod(minutes, 60)
        d, h = divmod(h, 24)
        parts = (f"{d} kun" if d else "", f"{h} soat" if h else "", f"{m} daq" if m else "")
        return " ".join(p for p in parts if p) or "0 daq"

    @property
    def start_month_short(self) -> str:
        return _UZ_MONTHS_SHORT[timezone.localtime(self.start).month - 1]

    @property
    def start_month(self) -> str:
        """Month and year of the start, like "Sentabr 2026"; the contests page groups ended contests by it."""
        start = timezone.localtime(self.start)
        return f"{_UZ_MONTHS[start.month - 1]} {start.year}"

    @property
    def has_ended(self) -> bool:
        return timezone.now() >= self.end

    @property
    def has_started(self) -> bool:
        return timezone.now() >= self.start


class ContestProblem(models.Model):
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name="contest_problems")
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE)
    label = models.CharField(max_length=2)
    order = models.IntegerField(default=0)
    points = models.IntegerField(default=100)

    class Meta:
        ordering = ["order"]
        unique_together = ("contest", "label")

    def __str__(self):
        return f"{self.contest} / {self.label}"


class Participation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="participations")
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name="participations")
    score = models.IntegerField(default=0)
    penalty = models.IntegerField(default=0)
    rank = models.IntegerField(null=True, blank=True)
    rating_before = models.IntegerField(null=True, blank=True)
    rating_after = models.IntegerField(null=True, blank=True)
    official_before = models.IntegerField(null=True, blank=True)
    official_after = models.IntegerField(null=True, blank=True)
    # Staff saw this finisher explain their code (online official contests, apps.contests.rating.review_queue)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    registered_at = models.DateTimeField(auto_now_add=True)
    # Set by staff for cheating: can't submit, ranked last (so rating drops), shown struck out.
    disqualified = models.BooleanField(default=False)
    disqualified_reason = models.CharField(max_length=200, blank=True)
    # Last heartbeat from the contest tracker; a submit long after it had no tracker running.
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "contest")


class Clarification(models.Model):
    """Contest Q&A. An unanswered question is visible only to its asker and
    staff; once answered it's visible to every participant (standard CP
    clarification-board behavior — answers are shared, questions in flight
    aren't)."""
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name="clarifications")
    problem = models.ForeignKey(ContestProblem, null=True, blank=True, on_delete=models.CASCADE,
                                related_name="clarifications")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="clarifications")
    question = models.TextField()
    answer = models.TextField(blank=True)
    answered_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="+")
    created = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created"]

    @property
    def is_answered(self) -> bool:
        return bool(self.answered_at)


class VirtualParticipation(models.Model):
    """Replaying a published contest on your own clock (apps.contests.virtual). Unrated;
    the submissions in the window are practice submissions tagged with it."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="virtuals")
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name="virtuals")
    start = models.DateTimeField()

    class Meta:
        unique_together = ("user", "contest")

    @property
    def end(self):
        return self.start + (self.contest.end - self.contest.start)

    @property
    def is_running(self):
        return self.start <= timezone.now() < self.end
