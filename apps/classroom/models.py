from django.conf import settings
from django.db import models

from apps.problems.models import Problem
from django.utils.translation import gettext_lazy as _tl


class DuelQuestion(models.Model):
    """One duel question: a short program in one language, and either "what does it print?" or a blank
    (`___`) to fill so that it prints `expect`. With `options` the player picks one; without, they type it,
    and spacing doesn't count. The bank lives in apps.classroom.quiz_bank; load_duel_questions loads it and
    checks every answer by running the code in the judge sandbox."""
    class Kind(models.TextChoices):
        OUTPUT = "output", _tl("Nima chiqaradi?")
        FILL = "fill", _tl("Bo‘sh joyni to‘ldiring")

    class Lang(models.TextChoices):
        PYTHON = "python", "Python"
        CPP = "cpp", "C++"
        JAVA = "java", "Java"
        JS = "js", "JavaScript"

    class Level(models.TextChoices):
        BEGINNER = "beginner", "Beginner"
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"

    key = models.CharField(max_length=40, unique=True)  # from the bank entry, so a reload updates in place
    language = models.CharField(max_length=10, choices=Lang.choices)
    level = models.CharField(max_length=10, choices=Level.choices)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    code = models.TextField()
    full = models.BooleanField(default=False)  # C++/Java: a whole program, else the inside of main()
    expect = models.TextField(blank=True)  # fill: what the finished program prints
    options = models.JSONField(default=list, blank=True)  # the answer and wrong ones; empty: typed
    answer = models.CharField(max_length=200)
    accept = models.JSONField(default=list, blank=True)  # typed: other right spellings
    explain = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    # for a generated variant: the key of the bank question it was made from (apps.classroom.quiz_variants);
    # "" for a bank question. load_duel_questions leaves variants alone.
    origin = models.CharField(max_length=40, blank=True, db_index=True)

    class Meta:
        ordering = ["language", "level", "id"]

    def __str__(self):
        return f"{self.key}: {self.code[:40]}"

    @property
    def code_parts(self) -> list[str]:
        """The code split at the blank, so a page can mark it: one part for an output question."""
        return self.code.split("___", 1)

    @property
    def in_main(self) -> bool:
        """C++/Java shown without its main(): the page says so."""
        return self.language in (self.Lang.CPP, self.Lang.JAVA) and not self.full

    @property
    def has_error_option(self) -> bool:
        return "Xato" in self.options


class Duel(models.Model):
    """1v1 quiz: the same five questions for both, each player on their own clock: the challenger's
    starts when they open the duel, the opponent's when they join. More right answers wins, then the
    equal is a draw (apps.classroom.duels). No opponent yet = an open duel: the next player who asks for a match
    in that language gets the same questions. Duels before the quiz were coding races on one
    problem (mode "code"); they stay as history."""
    class Mode(models.TextChoices):
        QUIZ = "quiz", _tl("Savollar")
        CODE = "code", _tl("Masala")

    class Status(models.TextChoices):
        PENDING = "pending", _tl("Raqib kutilmoqda")
        ACTIVE = "active", _tl("Davom etmoqda")
        FINISHED = "finished", _tl("Tugagan")
        DECLINED = "declined", _tl("Rad etilgan")
        EXPIRED = "expired", _tl("Muddati o‘tgan")
        VOID = "void", _tl("Bekor qilingan")  # staff took the result back (rating replays without it)

    challenger = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    opponent = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE,
                                 related_name="+")
    mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.QUIZ)
    language = models.CharField(max_length=10, choices=DuelQuestion.Lang.choices, blank=True)
    questions = models.JSONField(default=list, blank=True)  # DuelQuestion ids, in order
    problem = models.ForeignKey(Problem, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)  # the challenger's clock
    ends_at = models.DateTimeField(null=True, blank=True)
    opponent_started_at = models.DateTimeField(null=True, blank=True)
    opponent_ends_at = models.DateTimeField(null=True, blank=True)
    winner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="+")
    challenger_delta = models.IntegerField(null=True, blank=True)
    opponent_delta = models.IntegerField(null=True, blank=True)
    # When the duel ended (both runs over), set by settle(); the date a finished duel is shown under
    finished_at = models.DateTimeField(null=True, blank=True)
    # Made by challenging a named friend (not a quick match): the only duels Telegram tells the result of
    friend = models.BooleanField(default=False)
    # Settled as practice: a player had no ranked duels left that day (apps.classroom.duels.ranked_left), so no rating
    # change and no badge progress
    unranked = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created", "-id"]

    def clock(self, user_id):
        """(start, end) of that player's own time; None before it starts."""
        if user_id == self.challenger_id and self.started_at:
            return self.started_at, self.ends_at
        if user_id is not None and user_id == self.opponent_id and self.opponent_started_at:
            return self.opponent_started_at, self.opponent_ends_at
        return None

    def players(self):
        return (self.challenger_id, self.opponent_id)

    @property
    def ended_at(self):
        """When the duel finished (both runs over); its creation time until then, so a pending, declined or
        expired duel still carries a date."""
        return self.finished_at or self.created


class DuelAnswer(models.Model):
    """One player's go at one duel question. The row is made when the question is first shown, so its
    20 seconds run from then whatever the page does; `answered_at` None = not answered (yet)."""
    duel = models.ForeignKey(Duel, on_delete=models.CASCADE, related_name="answers")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    index = models.PositiveSmallIntegerField()
    question = models.ForeignKey(DuelQuestion, on_delete=models.PROTECT, related_name="+")
    shown_at = models.DateTimeField()
    answered_at = models.DateTimeField(null=True, blank=True)
    answer = models.CharField(max_length=200, blank=True)
    correct = models.BooleanField(default=False)
    away_ms = models.PositiveIntegerField(default=0, help_text="how long the page was out of focus while the question was open (the browser's word)")
    blurs = models.PositiveSmallIntegerField(default=0, help_text="how many times the page lost focus on this question")

    class Meta:
        ordering = ["index"]
        constraints = [models.UniqueConstraint(fields=["duel", "user", "index"], name="one_answer_per_question")]


class DuelSeasonResult(models.Model):
    """A closed month's podium of the duel rating: who stood where when the season ended."""
    season = models.CharField(max_length=7)  # YYYY-MM
    rank = models.PositiveSmallIntegerField()
    # rank 0 is the marker of a month with no podium (too quiet): no user
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE, related_name="duel_medals")
    rating = models.IntegerField()
    duels = models.PositiveIntegerField()

    class Meta:
        ordering = ["season", "rank"]
        constraints = [models.UniqueConstraint(fields=["season", "rank"], name="one_user_per_season_rank")]


class DuelSwitch(models.Model):
    """One row (pk 1): the staff's switch that closes the duels for the students, say for the length of a lesson.
    `until` empty while closed means closed until the staff open it again."""

    closed = models.BooleanField(default=False)
    until = models.DateTimeField(null=True, blank=True)
    changed_at = models.DateTimeField(auto_now=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
