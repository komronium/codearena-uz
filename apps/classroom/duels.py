"""1v1 quiz duels, played on two clocks. Opening a duel starts the challenger's run at once on QUESTIONS
questions in one language and level, so nobody has to wait for anyone; the opponent gets the same
questions and their own run when they join. Each question has PER_QUESTION from the moment it is first
shown; a run left half-way ends RUN_LIMIT after its start, unseen questions counting as wrong. More right
answers wins; equal, the less time spent; both with none right is a draw. Duel Elo moves once both runs
are over, by each player's own K (k_factor), as in chess: high for a newcomer, low at the top.

A duel names its opponent (a friend, who has WAIT_FOR to accept) or leaves the seat open: find_opponent
puts the next player who asks in that language and level into the open duel whose owner's duel rating is
closest to theirs, or opens a new one for them. Duels before the quiz were coding races (mode "code");
they are history only."""
import random
from datetime import datetime, timedelta
from typing import NamedTuple

from django.db import IntegrityError, transaction
from django.db.models import Count, F, Q
from django.db.models.functions import Abs
from django.utils import timezone

from apps.accounts.models import User

from .models import Duel, DuelAnswer, DuelQuestion
from .quiz_check import norm

QUESTIONS = 5
PER_QUESTION = timedelta(seconds=20)
GRACE = timedelta(seconds=2)  # an answer's trip to the server at the last second
RUN_LIMIT = timedelta(minutes=5)
WAIT_FOR = timedelta(days=3)  # for someone to join an open duel, or for a friend to accept
START_RATING = 1200
OPEN = (Duel.Status.PENDING, Duel.Status.ACTIVE)
LANGUAGES = DuelQuestion.Lang.choices
LEVELS = DuelQuestion.Level.choices
BUSY = "Avval boshlagan duelingizni tugating."


def k_factor(rating: int, played: int) -> int:
    """Chess-style K: 40 for the first 30 finished duels, so a new rating finds its place fast; then 20;
    10 from 2000 up, where a rating should be steady."""
    if played < 30:
        return 40
    return 10 if rating >= 2000 else 20


def elo(a: int, b: int, score: float, ka: int, kb: int) -> tuple[int, int]:
    """Rating changes of a and b for a's score (1 win, 0.5 draw, 0 loss)."""
    expected = 1 / (1 + 10 ** ((b - a) / 400))
    return round(ka * (score - expected)), round(kb * ((1 - score) - (1 - expected)))


# ---- one player's run ----------------------------------------------------------------------------------
class Run(NamedTuple):
    start: datetime
    end: datetime
    answers: list  # DuelAnswer rows by index: the questions shown so far

    def closed(self, a, now) -> bool:
        """Answered, or its time is up."""
        return a.answered_at is not None or now > a.shown_at + PER_QUESTION + GRACE

    def over(self, now) -> bool:
        return now >= self.end or (len(self.answers) == QUESTIONS and all(self.closed(a, now) for a in self.answers))

    @property
    def right(self) -> int:
        return sum(1 for a in self.answers if a.correct)

    def spent(self, now) -> timedelta:
        """Time on the questions: an answered one as taken, any other its full PER_QUESTION."""
        total = timedelta()
        for a in self.answers:
            took = a.answered_at - a.shown_at if a.answered_at else PER_QUESTION
            total += min(took, PER_QUESTION)
        return total + PER_QUESTION * (QUESTIONS - len(self.answers))


def run(duel, user_id) -> Run | None:
    """None until that player's clock starts (an opponent who hasn't joined yet)."""
    clock = duel.clock(user_id)
    if clock is None:
        return None
    answers = list(DuelAnswer.objects.filter(duel=duel, user_id=user_id).select_related("question").order_by("index"))
    return Run(clock[0], clock[1], answers)


def _winner(duel, now) -> int | None:
    """The winner's id, 0 for a draw, None while a run still goes on."""
    a, b = run(duel, duel.challenger_id), run(duel, duel.opponent_id)
    if a is None or b is None or not a.over(now) or not b.over(now):
        return None
    if a.right != b.right:
        return duel.challenger_id if a.right > b.right else duel.opponent_id
    if a.right == 0:
        return 0
    ta, tb = a.spent(now), b.spent(now)
    if ta == tb:
        return 0
    return duel.challenger_id if ta < tb else duel.opponent_id


def is_right(question, given: str) -> bool:
    if question.options:
        return given == question.answer
    return norm(given) != "" and norm(given) in {norm(question.answer), *map(norm, question.accept)}


def current(duel, user, now=None):
    """The question `user` is on, shown from now if it wasn't yet: the last one shown while its time
    runs, else the next one. None when the run is over."""
    now = now or timezone.now()
    r = run(duel, user.pk)
    if r is None or r.over(now):
        return None
    if r.answers and not r.closed(r.answers[-1], now):
        return r.answers[-1]
    index = len(r.answers)
    try:
        with transaction.atomic():
            return DuelAnswer.objects.create(duel=duel, user=user, index=index, question_id=duel.questions[index],
                                             shown_at=now)
    except IntegrityError:  # a second tab got there first
        return DuelAnswer.objects.select_related("question").get(duel=duel, user=user, index=index)


def answer(duel, user, index: int, given: str, now=None) -> DuelAnswer | None:
    """Record an answer to question `index`; one too late counts as wrong. The first answer stays."""
    now = now or timezone.now()
    a = DuelAnswer.objects.select_related("question").filter(duel=duel, user=user, index=index).first()
    if a is None or a.answered_at is not None:
        return a
    a.answered_at, a.answer = now, given.strip()[:200]
    a.correct = now <= a.shown_at + PER_QUESTION + GRACE and is_right(a.question, a.answer)
    a.save(update_fields=["answered_at", "answer", "correct"])
    settle(duel)
    return a


# ---- starting duels --------------------------------------------------------------------------------------
def _lock(user) -> None:
    """One duel start per user at a time, so a double click can't open two."""
    User.objects.select_for_update().filter(pk=user.pk).first()


def _busy(user, now) -> bool:
    """A run of yours still goes on."""
    for duel in Duel.objects.filter(Q(challenger=user) | Q(opponent=user), status__in=OPEN, mode=Duel.Mode.QUIZ):
        r = run(duel, user.pk)
        if r is not None and not r.over(now):
            return True
    return False


def _seen(users) -> set[int]:
    return set(DuelAnswer.objects.filter(user__in=users).values_list("question_id", flat=True))


def _pick(users, language: str, level: str) -> list[int] | None:
    """QUESTIONS questions none of `users` has seen, topped up with seen ones when the bank runs short."""
    pool = list(DuelQuestion.objects.filter(language=language, level=level, is_active=True).values_list("pk", flat=True))
    if len(pool) < QUESTIONS:
        return None
    seen = _seen(users)
    fresh = [q for q in pool if q not in seen]
    random.shuffle(fresh)
    picked = fresh[:QUESTIONS]
    if len(picked) < QUESTIONS:
        old = [q for q in pool if q in seen]
        picked += random.sample(old, QUESTIONS - len(picked))
    random.shuffle(picked)
    return picked


def _valid(language: str, level: str) -> str:
    if language not in dict(LANGUAGES):
        return "Tilni tanlang."
    if level not in dict(LEVELS):
        return "Darajani tanlang."
    return ""


def _open(challenger, language: str, level: str, questions: list[int], opponent=None) -> Duel:
    now = timezone.now()
    return Duel.objects.create(challenger=challenger, opponent=opponent, language=language, difficulty=level,
                               questions=questions, started_at=now, ends_at=now + RUN_LIMIT)


def _join(duel, user) -> None:
    now = timezone.now()
    duel.opponent = user
    duel.opponent_started_at, duel.opponent_ends_at = now, now + RUN_LIMIT
    duel.status = Duel.Status.ACTIVE
    duel.save(update_fields=["opponent", "opponent_started_at", "opponent_ends_at", "status"])


def joinable(user):
    """Open duels `user` could be put into: someone else's, still waiting."""
    return (Duel.objects.filter(mode=Duel.Mode.QUIZ, status=Duel.Status.PENDING, opponent__isnull=True,
                                created__gt=timezone.now() - WAIT_FOR)
            .exclude(challenger=user))


def joinable_counts(user) -> dict[str, int]:
    """How many open duels wait in each "language:level", for the picker."""
    return {f"{lang}:{lvl}": n for lang, lvl, n in
            joinable(user).order_by().values("language", "difficulty").annotate(n=Count("id"))
            .values_list("language", "difficulty", "n")}


def find_opponent(user, language: str, level: str) -> tuple[Duel | None, str]:
    """Join the open duel in this language and level whose owner's duel rating is closest to yours (then
    the longest-waiting), preferring questions you haven't seen; or open one: your run starts now, and
    whoever asks next gets your questions."""
    error = _valid(language, level)
    if error:
        return None, error
    with transaction.atomic():
        _lock(user)
        if _busy(user, timezone.now()):
            return None, BUSY
        candidates = list(joinable(user).filter(language=language, difficulty=level)
                          .annotate(gap=Abs(F("challenger__duel_rating") - user.duel_rating))
                          .order_by("gap", "created", "pk").values_list("pk", "questions")[:10])
        seen = _seen([user])
        candidates.sort(key=lambda c: len(seen.intersection(c[1])))  # stable: closest rating among the freshest
        for pk, _ in candidates:
            # skip_locked: someone else is joining it right now; don't queue behind them
            duel = (Duel.objects.select_for_update(skip_locked=True)
                    .filter(pk=pk, status=Duel.Status.PENDING, opponent__isnull=True).first())
            if duel is not None:
                _join(duel, user)
                return duel, ""
        questions = _pick([user], language, level)
        if questions is None:
            return None, "Bu til va darajada savollar hali yetarli emas — boshqasini tanlang."
        return _open(user, language, level, questions), ""


def challenge(challenger, opponent_username: str, language: str, level: str) -> tuple[Duel | None, str]:
    """Open a duel reserved for one opponent; the challenger's run starts now."""
    opponent = User.objects.filter(username=opponent_username.strip(), is_active=True).first()
    if opponent is None:
        return None, "Bunday foydalanuvchi yo‘q."
    if opponent.pk == challenger.pk:
        return None, "O‘zingizni chaqira olmaysiz."
    error = _valid(language, level)
    if error:
        return None, error
    with transaction.atomic():
        _lock(challenger)
        if _busy(challenger, timezone.now()):
            return None, BUSY
        pair = [challenger.pk, opponent.pk]
        if Duel.objects.filter(status__in=OPEN, challenger_id__in=pair, opponent_id__in=pair).exists():
            return None, "Bu raqib bilan ochiq duel bor."
        questions = _pick(pair, language, level)
        if questions is None:
            return None, "Bu til va darajada savollar hali yetarli emas — boshqasini tanlang."
        return _open(challenger, language, level, questions, opponent=opponent), ""


def accept(duel, user) -> str:
    """Start the invited opponent's run; "" on success, else why not."""
    with transaction.atomic():
        _lock(user)
        duel = Duel.objects.select_for_update().get(pk=duel.pk)
        if duel.opponent_id != user.pk or duel.status != Duel.Status.PENDING:
            return "Bu chaqiriq endi ochiq emas."
        if timezone.now() - duel.created > WAIT_FOR:
            duel.status = Duel.Status.EXPIRED
            duel.save(update_fields=["status"])
            return "Chaqiriq muddati o‘tgan."
        if _busy(user, timezone.now()):
            return BUSY
        _join(duel, user)
    return ""


def decline(duel, user) -> None:
    """The invited opponent turns a challenge down. The challenger can't take one back: their run
    started when they made it."""
    Duel.objects.filter(pk=duel.pk, status=Duel.Status.PENDING, opponent=user).update(status=Duel.Status.DECLINED)


# ---- the result ---------------------------------------------------------------------------------------
def _played(user_id) -> int:
    """Finished duels behind a player, for their K."""
    return Duel.objects.filter(Q(challenger_id=user_id) | Q(opponent_id=user_id), status=Duel.Status.FINISHED).count()


def settle(duel) -> None:
    """Finish a duel whose two runs are over; expire one nobody joined in time."""
    now = timezone.now()
    with transaction.atomic():
        duel = Duel.objects.select_for_update().get(pk=duel.pk)
        if duel.status == Duel.Status.PENDING and now - duel.created > WAIT_FOR:
            duel.status = Duel.Status.EXPIRED
            duel.save(update_fields=["status"])
            return
        if duel.status != Duel.Status.ACTIVE or duel.mode != Duel.Mode.QUIZ:
            return
        winner = _winner(duel, now)
        if winner is None:
            return
        a, b = User.objects.get(pk=duel.challenger_id), User.objects.get(pk=duel.opponent_id)
        score = 0.5 if winner == 0 else (1.0 if winner == a.pk else 0.0)
        da, db = elo(a.duel_rating, b.duel_rating, score, k_factor(a.duel_rating, _played(a.pk)),
                     k_factor(b.duel_rating, _played(b.pk)))
        duel.status, duel.winner_id = Duel.Status.FINISHED, winner or None
        duel.challenger_delta, duel.opponent_delta = da, db
        duel.save(update_fields=["status", "winner", "challenger_delta", "opponent_delta"])
        User.objects.filter(pk=a.pk).update(duel_rating=F("duel_rating") + da)
        User.objects.filter(pk=b.pk).update(duel_rating=F("duel_rating") + db)
    from apps.accounts.badges import award  # a finished duel can lift both players' duel badges
    for player in (a, b):
        award(player, {"duels"})


def settle_open(user) -> None:
    for duel in Duel.objects.filter(Q(challenger=user) | Q(opponent=user), status__in=OPEN):
        settle(duel)


def replay(duels, users) -> None:
    """Rebuild duel ratings from START_RATING over finished duels, oldest first, with k_factor: each
    keeps its result, the deltas are worked out again. `duels`/`users` are querysets (also historical
    models, so a migration can call it)."""
    rating, played = {}, {}
    for d in duels.filter(status="finished").order_by("created", "pk"):
        a, b = d.challenger_id, d.opponent_id
        ra, rb = rating.get(a, START_RATING), rating.get(b, START_RATING)
        score = 0.5 if d.winner_id is None else (1.0 if d.winner_id == a else 0.0)
        da, db = elo(ra, rb, score, k_factor(ra, played.get(a, 0)), k_factor(rb, played.get(b, 0)))
        duels.filter(pk=d.pk).update(challenger_delta=da, opponent_delta=db)
        rating[a], rating[b] = ra + da, rb + db
        played[a], played[b] = played.get(a, 0) + 1, played.get(b, 0) + 1
    users.exclude(pk__in=rating).exclude(duel_rating=START_RATING).update(duel_rating=START_RATING)
    for pk, r in rating.items():
        users.filter(pk=pk).update(duel_rating=r)
