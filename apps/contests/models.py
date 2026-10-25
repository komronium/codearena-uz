from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.problems.models import Problem
from django.utils.translation import gettext as _t, gettext_lazy as _tl

from apps.translations.mixin import Translatable


_UZ_MONTHS_SHORT = [_tl("Yan"), _tl("Fev"), _tl("Mar"), _tl("Apr"), _tl("May"), _tl("Iyn"), _tl("Iyl"), _tl("Avg"), _tl("Sen"), _tl("Okt"), _tl("Noy"), _tl("Dek")]
_UZ_MONTHS = [_tl("Yanvar"), _tl("Fevral"), _tl("Mart"), _tl("Aprel"), _tl("May"), _tl("Iyun"), _tl("Iyul"), _tl("Avgust"), _tl("Sentabr"), _tl("Oktabr"), _tl("Noyabr"), _tl("Dekabr")]

# What the divisions rate until staff edit them (moderation:divisions): shown ratings in [floor, ceiling),
# None = no bound. The tier steps of RATING_TIERS: Div. 1 from Candidate Master up, then 200 lower each.
DEFAULT_DIVISIONS = {1: (1500, None), 2: (None, 1500), 3: (None, 1300), 4: (None, 1100), 5: (None, 900)}
_RANGES_KEY = "contest-division-ranges"


class DivisionRange(models.Model):
    """A division and the shown ratings it rates: [floor, ceiling), None = no bound. Staff edit the rows, so the
    lines can move (and divisions be added) as the players change. A contest keeps only the division's number."""
    number = models.PositiveSmallIntegerField(unique=True, validators=[MinValueValidator(1)])
    floor = models.IntegerField(null=True, blank=True)
    ceiling = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ["number"]

    def __str__(self):
        return f"Div. {self.number}"

    @property
    def span(self) -> str:
        """The rated range in words: "1500+", "below 900", "700–1100"."""
        if self.floor is not None and self.ceiling is not None:
            return f"{self.floor}–{self.ceiling}"
        if self.floor is not None:
            return f"{self.floor}+"
        return _t("{n} dan past").format(n=self.ceiling) if self.ceiling is not None else _t("hamma")


def division_ranges() -> dict:
    """{number: (floor, ceiling)}, cached for a minute and dropped whenever staff save a division."""
    ranges = cache.get(_RANGES_KEY)
    if ranges is None:
        ranges = {d.number: (d.floor, d.ceiling) for d in DivisionRange.objects.all()} or dict(DEFAULT_DIVISIONS)
        cache.set(_RANGES_KEY, ranges, 60)
    return ranges


@receiver([post_save, post_delete], sender=DivisionRange)
def _drop_ranges(sender, **kwargs):
    cache.delete(_RANGES_KEY)


class Contest(Translatable, models.Model):
    class Type(models.TextChoices):
        # The contest's rules; apps.contests.standings ranks by them. Codeforces runs its own
        # rules for Div. 1/2 rounds and ICPC for Div. 3/4; "score" is the original rule, kept
        # for the contests played under it.
        SCORE = "score", _tl("Ball: to‘liq ball, tenglikda jarima")
        CF = "cf", _tl("Codeforces: ball vaqt bilan kamayadi")
        ICPC = "icpc", _tl("ICPC: yechilganlar soni va jarima")

    class Kind(models.TextChoices):
        ROUND = "round", "Round"  # names, not translated
        MARATHON = "marathon", "Marathon"

    class Division(models.IntegerChoices):
        OPEN = 0, _tl("Ochiq (hamma uchun)")  # the others are DivisionRange rows

    # the title is built from kind, number and division (compose_title), the same in every language: not translated
    TRANSLATABLE = ("description_md", "badge")
    SHORT = ("badge",)
    source_lang = models.CharField(max_length=2, default="uz", choices=[("uz", "O‘zbekcha"), ("en", "English")])

    # "CodeArena Round #8 (Div. 3)": every contest is a Round or a Marathon with its own running number.
    # Contests made before numbering (number null) keep the title they were typed with.
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.ROUND)
    number = models.PositiveIntegerField(null=True, blank=True)
    title = models.CharField(max_length=200, blank=True)
    description_md = models.TextField(blank=True)
    start = models.DateTimeField()
    end = models.DateTimeField()
    type = models.CharField(max_length=10, choices=Type.choices, default=Type.SCORE)
    is_rated = models.BooleanField(default=False)
    allowed_ip_prefix = models.CharField(max_length=50, blank=True)
    rating_applied = models.BooleanField(default=False)
    # A round with a window longer than the time each person gets (a marathon): every participant starts their
    # own clock with "Boshlash" and has this many minutes from then, never past `end`. 0 = one clock for all.
    personal_minutes = models.PositiveSmallIntegerField(default=0)
    # the scheduler publishes the problems and applies the rating by itself once the round has been over for a while
    # and no similarity flag is left open (contests.management.commands.finish_contests); off unless staff turn it on
    auto_finish = models.BooleanField(default=False)
    # Rated only for users in the division's range; the rest take part out of competition:
    # on the board, but not rated (apps.contests.rating).
    division = models.PositiveSmallIntegerField(default=Division.OPEN)  # 0 = open, else a DivisionRange number
    # Set by staff publishing the ended contest; from then on participants' contest ACs
    # count as practice solves (apps.submissions.solves).
    published_at = models.DateTimeField(null=True, blank=True)
    # A badge on the profiles of everyone who solved something, once the round is published: this name
    # ("Marathon #1") with a medal for the top three, else how many problems they solved. Empty: none.
    badge = models.CharField(max_length=40, blank=True)
    # The people who wrote the round (named on its pages, like Codeforces' writers). They may take part, but out of
    # competition: on the board with a star instead of a place, never rated, no badge, and not counted in anyone's place.
    authors = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="authored_contests")
    # A round a trusted writer (User.is_setter) prepared: only staff and its authors see it until staff publish it.
    is_draft = models.BooleanField(default=False)
    # Until the round ends, staff who are not its authors cannot read its problems, tests or solutions on the staff pages,
    # so a person who runs the site can still play it (the round's writers stay out of competition).
    blind = models.BooleanField(default=False)
    problems = models.ManyToManyField(Problem, through="ContestProblem", related_name="contests")
    updated = models.DateTimeField(auto_now=True)  # the sitemap's lastmod; partial saves leave it
    # When the similarity check last ran over every problem by itself, after the end (flag_similarity
    # --pending, the scheduler's sweep); staff's own runs for a few problems leave it. Rounds from
    # before the sweep carry their end: done, but never swept.
    similarity_checked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["kind", "number"], name="contest_kind_number_uniq")]

    def __str__(self):
        return self.title

    @classmethod
    def next_number(cls, kind) -> int:
        return (cls.objects.filter(kind=kind).aggregate(m=models.Max("number"))["m"] or 0) + 1

    def compose_title(self) -> str:
        title = f"CodeArena {self.get_kind_display()} #{self.number}"
        return f"{title} (Div. {self.division})" if self.division else title

    def save(self, *args, **kwargs):
        if self.number:
            self.title = self.compose_title()
            if (update := kwargs.get("update_fields")) is not None:
                kwargs["update_fields"] = {*update, "title"}
        super().save(*args, **kwargs)

    @property
    def division_label(self) -> str:
        return f"Div. {self.division}" if self.division else _t("Ochiq")

    @property
    def division_span(self) -> str:
        """What this contest's division rates, in words ("1500+"); empty for an open contest."""
        floor, ceiling = division_ranges().get(self.division, (None, None))
        return DivisionRange(number=self.division, floor=floor, ceiling=ceiling).span if self.division else ""

    @property
    def wrong_try_minutes(self) -> int | None:
        """Penalty minutes per wrong try before a solve; None under Codeforces rules, where a
        wrong try costs 50 points instead and there is no penalty."""
        return {self.Type.SCORE: 20, self.Type.ICPC: 10}.get(self.type)

    def rates(self, rating: int) -> bool:
        """Whether a user with this shown rating competes officially (is rated) in this contest."""
        floor, ceiling = division_ranges().get(self.division, (None, None))
        return (floor is None or rating >= floor) and (ceiling is None or rating < ceiling)

    @property
    def is_running(self) -> bool:
        now = timezone.now()
        return self.start <= now < self.end

    @property
    def duration_label(self) -> str:
        minutes = int((self.end - self.start).total_seconds() // 60)
        h, m = divmod(minutes, 60)
        d, h = divmod(h, 24)
        parts = (_t("{n} kun").format(n=d) if d else "", _t("{n} soat").format(n=h) if h else "",
                 _t("{n} daq").format(n=m) if m else "")
        return " ".join(p for p in parts if p) or _t("0 daq")

    @property
    def start_month_short(self) -> str:
        return str(_UZ_MONTHS_SHORT[timezone.localtime(self.start).month - 1])

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


# A round's problem is worth at least 200: under Codeforces rules each wrong try costs 50 and a solve never
# drops below 30%, so a 100-point problem is at its floor after two wrong tries and the scores stop meaning
# anything. By level, the Codeforces scale the rounds so far have used.
MIN_POINTS = 200
LEVEL_POINTS = {"beginner": 250, "easy": 500, "medium": 750, "hard": 1000}


class ContestProblem(models.Model):
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name="contest_problems")
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE)
    label = models.CharField(max_length=2)
    order = models.IntegerField(default=0)
    points = models.IntegerField(default=500, validators=[MinValueValidator(
        MIN_POINTS, f"Kamida {MIN_POINTS} ball: har noto‘g‘ri urinish −50, 100 ballik masala ikki xatodan keyin "
                    "eng past bahoga tushadi.")])

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
    registered_at = models.DateTimeField(auto_now_add=True)
    # Set by staff for cheating: can't submit, ranked last (so rating drops), shown struck out.
    disqualified = models.BooleanField(default=False)
    disqualified_reason = models.CharField(max_length=200, blank=True)
    # Last heartbeat from the contest tracker; a submit long after it had no tracker running.
    last_seen_at = models.DateTimeField(null=True, blank=True)
    # Personal-clock rounds (Contest.personal_minutes): when this participant pressed "Boshlash".
    started_at = models.DateTimeField(null=True, blank=True)

    @property
    def clock_start(self):
        """Where this participant's time counts from: their own start in a personal-clock round, else the contest's."""
        return self.started_at if self.contest.personal_minutes and self.started_at else self.contest.start

    @property
    def personal_end(self):
        """When this participant's own time runs out (a personal-clock round, once started); None otherwise."""
        if not (self.contest.personal_minutes and self.started_at):
            return None
        return min(self.contest.end, self.started_at + timedelta(minutes=self.contest.personal_minutes))

    def can_submit_now(self) -> bool:
        """Whether this participant may send code to the round right now."""
        now = timezone.now()
        if not (self.contest.start <= now < self.contest.end):
            return False
        return not self.contest.personal_minutes or (self.started_at is not None and now < self.personal_end)

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


class VoidedProblem(models.Model):
    """A participant's result on one problem of a round, struck by staff because the work was not
    their own. The cell counts as untried (no points, no wrong tries) and the rest of the round
    stands, unlike a disqualification. Silent: nothing on the site tells the participant; staff see
    it in the round's submissions and the integrity report, and the audit log keeps who and why.

    `penalty` (AI caught red-handed): the strike counts as a wrong try instead — the cancelled
    solution is returned as a failed attempt on the board — and the problem is blocked for the
    participant for the rest of the round: no more submissions to it."""
    participation = models.ForeignKey(Participation, on_delete=models.CASCADE, related_name="voids")
    contest_problem = models.ForeignKey(ContestProblem, on_delete=models.CASCADE, related_name="voids")
    reason = models.CharField(max_length=200, blank=True)
    # AI/cheat penalty: one wrong try for the struck solution, problem blocked until the round ends
    penalty = models.BooleanField(default=False)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("participation", "contest_problem")
