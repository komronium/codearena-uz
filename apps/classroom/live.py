"""The live quiz's rules: creating one, joining, the host's steps, answering and scoring. Time is the server's: a
question shows for `seconds`; an answer scores 500 for being right plus up to 500 for being quick."""
import random
import secrets
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from .duels import is_right
from .models import DuelQuestion, LiveQuiz, LiveQuizAnswer, LiveQuizPlayer

COUNTS = (5, 8, 10)
GRACE = timedelta(seconds=1)
BASE, SPEED = 500, 500


def _new_code() -> str:
    for _ in range(50):
        code = f"{secrets.randbelow(900000) + 100000}"
        if not LiveQuiz.objects.filter(code=code).exclude(status=LiveQuiz.Status.DONE).exists():
            return code
    raise RuntimeError("no free quiz code")


def create(teacher, language: str, level: str, count: int, title: str = "", seconds: int = 20):
    """A quiz of `count` random bank questions; (quiz, "") or (None, why not)."""
    if language not in dict(DuelQuestion.Lang.choices) or level not in dict(DuelQuestion.Level.choices):
        return None, "Til va darajani tanlang."
    if count not in COUNTS:
        count = COUNTS[0]
    pool = list(DuelQuestion.objects.filter(language=language, level=level, is_active=True).values_list("pk", flat=True))
    if len(pool) < count:
        return None, f"Bu tilda va darajada savol yetarli emas ({len(pool)} ta bor, {count} ta kerak)."
    picked = random.sample(pool, count)
    return LiveQuiz.objects.create(teacher=teacher, title=title.strip()[:120], code=_new_code(), language=language,
                                   level=level, questions=picked, seconds=max(10, min(60, seconds))), ""


def join(user, code: str):
    quiz = LiveQuiz.objects.filter(code=code.strip().replace(" ", "")).exclude(status=LiveQuiz.Status.DONE).first()
    if quiz is None:
        return None
    LiveQuizPlayer.objects.get_or_create(quiz=quiz, user=user)
    return quiz


def question(quiz: LiveQuiz):
    if 0 <= quiz.index < len(quiz.questions):
        return DuelQuestion.objects.get(pk=quiz.questions[quiz.index])
    return None


def deadline(quiz: LiveQuiz):
    return quiz.question_started_at + timedelta(seconds=quiz.seconds) if quiz.question_started_at else None


def tick(quiz: LiveQuiz) -> LiveQuiz:
    """Time or everyone answered closes the open question: its results show."""
    if quiz.status != LiveQuiz.Status.QUESTION:
        return quiz
    answered = LiveQuizAnswer.objects.filter(quiz=quiz, index=quiz.index).count()
    everyone = answered and answered >= quiz.players.count()
    if everyone or timezone.now() > deadline(quiz) + GRACE:
        LiveQuiz.objects.filter(pk=quiz.pk, status=LiveQuiz.Status.QUESTION, index=quiz.index).update(status=LiveQuiz.Status.REVEAL)
        quiz.refresh_from_db()
    return quiz


def step(quiz: LiveQuiz, action: str) -> LiveQuiz:
    """The host's buttons: start, show the results now, next question, end."""
    with transaction.atomic():
        quiz = LiveQuiz.objects.select_for_update().get(pk=quiz.pk)
        now = timezone.now()
        if action == "start" and quiz.status == LiveQuiz.Status.LOBBY and quiz.players.exists():
            quiz.status, quiz.index, quiz.question_started_at = LiveQuiz.Status.QUESTION, 0, now
        elif action == "reveal" and quiz.status == LiveQuiz.Status.QUESTION:
            quiz.status = LiveQuiz.Status.REVEAL
        elif action == "next" and quiz.status == LiveQuiz.Status.REVEAL:
            if quiz.index + 1 >= len(quiz.questions):
                quiz.status = LiveQuiz.Status.DONE
            else:
                quiz.status, quiz.index, quiz.question_started_at = LiveQuiz.Status.QUESTION, quiz.index + 1, now
        elif action == "end":
            quiz.status = LiveQuiz.Status.DONE
        else:
            return quiz
        quiz.save(update_fields=["status", "index", "question_started_at"])
    return quiz


def answer(quiz: LiveQuiz, user, index: int, given: str) -> LiveQuizAnswer | None:
    """One answer per player per question; late or out of turn is ignored (None)."""
    quiz = tick(quiz)
    now = timezone.now()
    if quiz.status != LiveQuiz.Status.QUESTION or index != quiz.index or now > deadline(quiz) + GRACE:
        return None
    if not LiveQuizPlayer.objects.filter(quiz=quiz, user=user).exists():
        return None
    q = question(quiz)
    given = given.strip()[:200]
    right = is_right(q, given)
    elapsed = max(0.0, (now - quiz.question_started_at).total_seconds())
    points = BASE + round(SPEED * max(0.0, 1 - elapsed / quiz.seconds)) if right else 0
    try:
        with transaction.atomic():
            a = LiveQuizAnswer.objects.create(quiz=quiz, user=user, index=index, answer=given, correct=right,
                                              points=points, ms=int(elapsed * 1000))
            LiveQuizPlayer.objects.filter(quiz=quiz, user=user).update(score=F("score") + points)
    except IntegrityError:
        return LiveQuizAnswer.objects.get(quiz=quiz, user=user, index=index)
    return a


def board(quiz: LiveQuiz, limit: int | None = None) -> list[dict]:
    rows = [{"user": p.user, "score": p.score} for p in quiz.players.select_related("user").order_by("-score", "joined")]
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows[:limit] if limit else rows


def counts(quiz: LiveQuiz, q) -> list[dict]:
    """How many chose each option of the current question (for the host's results)."""
    given = list(LiveQuizAnswer.objects.filter(quiz=quiz, index=quiz.index).values_list("answer", flat=True))
    opts = q.options or []
    return [{"option": o, "n": given.count(o), "right": o == q.answer} for o in opts]
