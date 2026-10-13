from django.conf import settings
from django.db import models

from apps.accounts.models import Group
from apps.problems.models import Problem
from apps.submissions.models import Submission


class Assignment(models.Model):
    """Homework: a problem set a group's teacher gives with a deadline. Progress is read
    from submissions (apps.classroom.progress), so rejudges flow through by themselves."""
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="assignments")
    title = models.CharField(max_length=200)
    description_md = models.TextField(blank=True)
    start = models.DateTimeField()
    deadline = models.DateTimeField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-deadline", "-id"]

    def __str__(self):
        return self.title


class AssignmentProblem(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name="assignment_problems")
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name="+")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        unique_together = ("assignment", "problem")


class ReviewComment(models.Model):
    """A teacher's note on a student's code (line = None: on the whole submission), or
    the student's reply. `read` is for the student's unread badge."""
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="reviews")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    line = models.PositiveIntegerField(null=True, blank=True)
    body = models.TextField(max_length=2000)
    created = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

    class Meta:
        ordering = ["created", "id"]


class DuelQuestion(models.Model):
    """One duel question: a short program in one language, and either "what does it print?" or a blank
    (`___`) to fill so that it prints `expect`. With `options` the player picks one; without, they type it,
    and spacing doesn't count. The bank lives in apps.classroom.quiz_bank; load_duel_questions loads it and
    checks every answer by running the code in the judge sandbox."""
    class Kind(models.TextChoices):
        OUTPUT = "output", "Nima chiqaradi?"
        FILL = "fill", "Bo‘sh joyni to‘ldiring"

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
    faster (apps.classroom.duels). No opponent yet = an open duel: the next player who asks for a match
    in that language and level gets the same questions. Duels before the quiz were coding races on one
    problem (mode "code"); they stay as history."""
    class Mode(models.TextChoices):
        QUIZ = "quiz", "Savollar"
        CODE = "code", "Masala"

    class Status(models.TextChoices):
        PENDING = "pending", "Raqib kutilmoqda"
        ACTIVE = "active", "Davom etmoqda"
        FINISHED = "finished", "Tugagan"
        DECLINED = "declined", "Rad etilgan"
        EXPIRED = "expired", "Muddati o‘tgan"

    challenger = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    opponent = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE,
                                 related_name="+")
    mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.QUIZ)
    language = models.CharField(max_length=10, choices=DuelQuestion.Lang.choices, blank=True)
    difficulty = models.CharField(max_length=10, choices=Problem.Difficulty.choices)
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


class LiveQuiz(models.Model):
    """A teacher's live quiz, Kahoot-style: the host screen goes on the projector, students join with a code on
    their phones, everyone gets the same question at once and faster right answers score more. The questions come
    from the duel bank. The state machine lives in apps.classroom.live."""
    class Status(models.TextChoices):
        LOBBY = "lobby", "Kutish zali"
        QUESTION = "question", "Savol"
        REVEAL = "reveal", "Natija"
        DONE = "done", "Tugagan"

    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    title = models.CharField(max_length=120, blank=True)
    code = models.CharField(max_length=6, db_index=True)
    language = models.CharField(max_length=10, choices=DuelQuestion.Lang.choices)
    level = models.CharField(max_length=10, choices=DuelQuestion.Level.choices)
    questions = models.JSONField(default=list)  # DuelQuestion ids, in order
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.LOBBY)
    index = models.IntegerField(default=-1)
    question_started_at = models.DateTimeField(null=True, blank=True)
    seconds = models.PositiveSmallIntegerField(default=20)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]


class LiveQuizPlayer(models.Model):
    quiz = models.ForeignKey(LiveQuiz, on_delete=models.CASCADE, related_name="players")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    score = models.IntegerField(default=0)
    joined = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["quiz", "user"], name="one_player_per_live_quiz")]


class LiveQuizAnswer(models.Model):
    quiz = models.ForeignKey(LiveQuiz, on_delete=models.CASCADE, related_name="answers")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    index = models.PositiveSmallIntegerField()
    answer = models.CharField(max_length=200, blank=True)
    correct = models.BooleanField(default=False)
    points = models.PositiveIntegerField(default=0)
    ms = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["quiz", "user", "index"], name="one_live_answer")]
