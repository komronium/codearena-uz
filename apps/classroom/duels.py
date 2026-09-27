"""1v1 duels, played on two clocks. Opening a duel starts the challenger's DURATION at
once, on a problem they never submitted to, so nobody has to wait for anyone; the
opponent gets the same problem and their own DURATION when they join. The faster AC,
timed from each player's own start, wins; no AC from either is a draw. Duel Elo moves
once, when the outcome can no longer change.

A duel names its opponent (a friend, who has WAIT_FOR to accept) or leaves the seat
open: find_opponent puts the next player who asks at that level into the open duel
whose owner's duel rating is closest to theirs, or opens a new one for them."""
import random
from datetime import datetime, timedelta
from typing import NamedTuple

from django.db import transaction
from django.db.models import Count, F, Q
from django.db.models.functions import Abs
from django.utils import timezone

from apps.accounts.models import User
from apps.problems.skills import open_problems
from apps.submissions.models import Submission

from .models import Duel

DURATION = timedelta(minutes=30)
WAIT_FOR = timedelta(days=3)  # for someone to join an open duel, or for a friend to accept
K = 32
OPEN = (Duel.Status.PENDING, Duel.Status.ACTIVE)
NEVER = timedelta.max  # the solve time of a run with no AC
_JUDGING = {Submission.Verdict.PENDING, Submission.Verdict.RUNNING}
BUSY = "Avval boshlagan duelingizni tugating: masalani yeching yoki vaqti tugasin."


class Run(NamedTuple):
    """One player's own attempt at the duel problem."""
    start: datetime
    end: datetime
    subs: list[tuple[timedelta, str]]  # (time from start, verdict), oldest first
    solved_in: timedelta | None  # the first AC

    @property
    def judging_from(self) -> timedelta | None:
        """The earliest submission still waiting for a verdict: it may yet be an AC."""
        return next((t for t, v in self.subs if v in _JUDGING), None)


def run(duel, user_id) -> Run | None:
    """None until that player's clock starts (an opponent who hasn't joined yet)."""
    clock = duel.clock(user_id)
    if clock is None or duel.problem_id is None:
        return None
    start, end = clock
    subs = [(created - start, verdict) for verdict, created in
            Submission.objects.filter(user_id=user_id, problem_id=duel.problem_id, contest__isnull=True,
                                      created__gte=start, created__lt=end)
            .order_by("created", "id").values_list("verdict", "created")]
    return Run(start, end, subs, next((t for t, v in subs if v == Submission.Verdict.AC), None))


def _bounds(r: Run, now) -> tuple[timedelta, timedelta]:
    """The best and the worst solve time `r` can still end with. A clock that still runs
    can post an AC from its elapsed time on; a submission being judged may be one."""
    worst = NEVER if r.solved_in is None else r.solved_in
    judging = r.judging_from
    best = min(worst, NEVER if judging is None else judging, now - r.start if now < r.end else NEVER)
    return best, worst


def _winner(duel, now) -> int | None:
    """The winner's id, 0 for a draw, None while the outcome can still change."""
    a, b = run(duel, duel.challenger_id), run(duel, duel.opponent_id)
    if a is None or b is None:
        return None
    (a_best, a_worst), (b_best, b_worst) = _bounds(a, now), _bounds(b, now)
    if a_worst < b_best:
        return duel.challenger_id
    if b_worst < a_best:
        return duel.opponent_id
    if a_best == a_worst == b_best == b_worst:  # both final and equal: no AC from either, or a dead heat
        return 0
    return None


def _levels() -> dict:
    return dict(Duel._meta.get_field("difficulty").choices)


def _lock(user) -> None:
    """One duel start per user at a time, so a double click can't open two."""
    User.objects.select_for_update().filter(pk=user.pk).first()


def _busy(user, now) -> bool:
    """A clock of yours still runs on a problem you haven't solved."""
    for duel in Duel.objects.filter(Q(challenger=user) | Q(opponent=user), status__in=OPEN):
        clock = duel.clock(user.pk)
        if clock and now < clock[1] and run(duel, user.pk).solved_in is None:
            return True
    return False


def _fresh_problem(users, difficulty: str) -> int | None:
    """A problem at `difficulty` none of `users` ever submitted to."""
    tried = Submission.objects.filter(user__in=users).values("problem_id")
    ids = sorted(open_problems().filter(difficulty=difficulty).exclude(pk__in=tried)
                 .values_list("pk", flat=True))
    return random.choice(ids) if ids else None


def _open(challenger, difficulty: str, problem_id: int, opponent=None) -> Duel:
    now = timezone.now()
    return Duel.objects.create(challenger=challenger, opponent=opponent, difficulty=difficulty,
                               problem_id=problem_id, started_at=now, ends_at=now + DURATION)


def _join(duel, user) -> None:
    now = timezone.now()
    duel.opponent = user
    duel.opponent_started_at, duel.opponent_ends_at = now, now + DURATION
    duel.status = Duel.Status.ACTIVE
    duel.save(update_fields=["opponent", "opponent_started_at", "opponent_ends_at", "status"])


def joinable(user):
    """Open duels `user` could be put into: someone else's, still waiting, on a problem
    `user` never submitted to."""
    tried = Submission.objects.filter(user=user).values("problem_id")
    return (Duel.objects.filter(status=Duel.Status.PENDING, opponent__isnull=True, problem__isnull=False,
                                created__gt=timezone.now() - WAIT_FOR)
            .exclude(challenger=user).exclude(problem_id__in=tried))


def joinable_counts(user) -> dict[str, int]:
    """How many open duels wait at each level, for the level picker."""
    return dict(joinable(user).order_by().values("difficulty").annotate(n=Count("id"))
                .values_list("difficulty", "n"))


def find_opponent(user, difficulty: str) -> tuple[Duel | None, str]:
    """Join the open duel at this level whose owner's duel rating is closest to yours
    (then the longest-waiting), or open one: your clock starts now, and whoever asks
    next gets your problem."""
    if difficulty not in _levels():
        return None, "Qiyinlikni tanlang."
    with transaction.atomic():
        _lock(user)
        if _busy(user, timezone.now()):
            return None, BUSY
        candidates = (joinable(user).filter(difficulty=difficulty)
                      .annotate(gap=Abs(F("challenger__duel_rating") - user.duel_rating))
                      .order_by("gap", "created", "pk").values_list("pk", flat=True)[:5])
        for pk in candidates:
            # skip_locked: someone else is joining it right now; don't queue behind them
            duel = (Duel.objects.select_for_update(skip_locked=True)
                    .filter(pk=pk, status=Duel.Status.PENDING, opponent__isnull=True).first())
            if duel is not None:
                _join(duel, user)
                return duel, ""
        problem = _fresh_problem([user], difficulty)
        if problem is None:
            return None, "Siz urinib ko‘rmagan mos masala qolmagan — boshqa qiyinlikni tanlang."
        return _open(user, difficulty, problem), ""


def challenge(challenger, opponent_username: str, difficulty: str) -> tuple[Duel | None, str]:
    """Open a duel reserved for one opponent; the challenger's clock starts now."""
    opponent = User.objects.filter(username=opponent_username.strip(), is_active=True).first()
    if opponent is None:
        return None, "Bunday foydalanuvchi yo‘q."
    if opponent.pk == challenger.pk:
        return None, "O‘zingizni chaqira olmaysiz."
    if difficulty not in _levels():
        return None, "Qiyinlikni tanlang."
    with transaction.atomic():
        _lock(challenger)
        if _busy(challenger, timezone.now()):
            return None, BUSY
        pair = [challenger.pk, opponent.pk]
        if Duel.objects.filter(status__in=OPEN, challenger_id__in=pair, opponent_id__in=pair).exists():
            return None, "Bu raqib bilan ochiq duel bor."
        problem = _fresh_problem(pair, difficulty)
        if problem is None:
            return None, "Ikkalangiz ham urinib ko‘rmagan mos masala qolmagan — boshqa qiyinlikni tanlang."
        return _open(challenger, difficulty, problem, opponent=opponent), ""


def accept(duel, user) -> str:
    """Start the invited opponent's clock; "" on success, else why not."""
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
        if Submission.objects.filter(user=user, problem_id=duel.problem_id).exists():
            # tried it since the challenge was made: a race on it wouldn't be fair
            duel.status = Duel.Status.EXPIRED
            duel.save(update_fields=["status"])
            return "Bu masalaga avval urinib ko‘rgansiz — duel bekor qilindi."
        _join(duel, user)
    return ""


def decline(duel, user) -> None:
    """The invited opponent turns a challenge down. The challenger can't take one back:
    their clock started when they made it."""
    Duel.objects.filter(pk=duel.pk, status=Duel.Status.PENDING, opponent=user).update(status=Duel.Status.DECLINED)


def settle(duel) -> None:
    """Finish a duel whose outcome can no longer change; expire one nobody joined in time."""
    now = timezone.now()
    with transaction.atomic():
        duel = Duel.objects.select_for_update().get(pk=duel.pk)
        if duel.status == Duel.Status.PENDING and now - duel.created > WAIT_FOR:
            duel.status = Duel.Status.EXPIRED
            duel.save(update_fields=["status"])
            return
        if duel.status != Duel.Status.ACTIVE:
            return
        winner = _winner(duel, now)
        if winner is None:
            return
        a, b = User.objects.get(pk=duel.challenger_id), User.objects.get(pk=duel.opponent_id)
        score = 0.5 if winner == 0 else (1.0 if winner == a.pk else 0.0)
        expected = 1 / (1 + 10 ** ((b.duel_rating - a.duel_rating) / 400))
        delta = round(K * (score - expected))
        duel.status, duel.winner_id = Duel.Status.FINISHED, winner or None
        duel.challenger_delta, duel.opponent_delta = delta, -delta
        duel.save(update_fields=["status", "winner", "challenger_delta", "opponent_delta"])
        User.objects.filter(pk=a.pk).update(duel_rating=F("duel_rating") + delta)
        User.objects.filter(pk=b.pk).update(duel_rating=F("duel_rating") - delta)


def settle_open(user) -> None:
    for duel in Duel.objects.filter(Q(challenger=user) | Q(opponent=user), status__in=OPEN):
        settle(duel)


def settle_for_submission(sub) -> None:
    """Runner hook: any verdict can settle a duel on its problem, an AC by deciding it and
    a WA by ending the wait for one."""
    if sub.contest_id is not None:
        return
    for duel in Duel.objects.filter(Q(challenger_id=sub.user_id) | Q(opponent_id=sub.user_id),
                                    status=Duel.Status.ACTIVE, problem_id=sub.problem_id):
        settle(duel)


def active_duel_for(user, problem):
    """The duel whose clock runs for `user` on `problem`, with that clock's end as
    `my_end`; None if there's none."""
    if not user.is_authenticated:
        return None
    now = timezone.now()
    for duel in Duel.objects.filter(Q(challenger=user) | Q(opponent=user), status__in=OPEN,
                                    problem=problem).select_related("challenger", "opponent"):
        clock = duel.clock(user.pk)
        if clock and clock[0] <= now < clock[1]:
            duel.my_end = clock[1]
            return duel
    return None
