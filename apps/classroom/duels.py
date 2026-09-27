"""1v1 duels. A challenge waits PENDING_FOR for an answer; on accept both players get the
same problem neither of them ever submitted to, for DURATION. The first AC in that
window wins; none is a draw. Duel Elo moves once, when the duel settles."""
import random
from datetime import timedelta

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.accounts.models import User
from apps.problems.skills import open_problems
from apps.submissions.models import Submission

from .models import Duel

DURATION = timedelta(minutes=30)
PENDING_FOR = timedelta(hours=1)
K = 32
OPEN = (Duel.Status.PENDING, Duel.Status.ACTIVE)


def challenge(challenger, opponent_username: str, difficulty: str) -> tuple[Duel | None, str]:
    opponent = User.objects.filter(username=opponent_username.strip(), is_active=True).first()
    if opponent is None:
        return None, "Bunday foydalanuvchi yo‘q."
    if opponent.pk == challenger.pk:
        return None, "O‘zingizni chaqira olmaysiz."
    if difficulty not in dict(Duel._meta.get_field("difficulty").choices):
        return None, "Qiyinlikni tanlang."
    pair = [challenger.pk, opponent.pk]
    if Duel.objects.filter(status__in=OPEN, challenger_id__in=pair, opponent_id__in=pair).exists():
        return None, "Bu raqib bilan ochiq duel bor."
    return Duel.objects.create(challenger=challenger, opponent=opponent, difficulty=difficulty), ""


def accept(duel, user) -> str:
    """Start the duel; "" on success, else why not."""
    with transaction.atomic():
        duel = Duel.objects.select_for_update().get(pk=duel.pk)
        if duel.opponent_id != user.pk or duel.status != Duel.Status.PENDING:
            return "Bu chaqiriq endi ochiq emas."
        if timezone.now() - duel.created > PENDING_FOR:
            duel.status = Duel.Status.EXPIRED
            duel.save(update_fields=["status"])
            return "Chaqiriq muddati o‘tgan."
        tried = Submission.objects.filter(user_id__in=duel.players()).values("problem_id")
        ids = sorted(open_problems().filter(difficulty=duel.difficulty).exclude(pk__in=tried)
                     .values_list("pk", flat=True))
        if not ids:
            duel.status = Duel.Status.EXPIRED
            duel.save(update_fields=["status"])
            return "Ikkalangiz ham urinib ko‘rmagan mos masala qolmagan — boshqa qiyinlikni tanlang."
        now = timezone.now()
        duel.problem_id = random.choice(ids)
        duel.status, duel.started_at, duel.ends_at = Duel.Status.ACTIVE, now, now + DURATION
        duel.save(update_fields=["problem", "status", "started_at", "ends_at"])
    return ""


def decline(duel, user) -> None:
    """The opponent declines, or the challenger withdraws, a pending duel."""
    (Duel.objects.filter(pk=duel.pk, status=Duel.Status.PENDING)
     .filter(Q(challenger=user) | Q(opponent=user)).update(status=Duel.Status.DECLINED))


def settle(duel) -> None:
    """Finish an active duel that has a winner or ran out; expire a stale challenge."""
    now = timezone.now()
    with transaction.atomic():
        duel = Duel.objects.select_for_update().get(pk=duel.pk)
        if duel.status == Duel.Status.PENDING and now - duel.created > PENDING_FOR:
            duel.status = Duel.Status.EXPIRED
            duel.save(update_fields=["status"])
            return
        if duel.status != Duel.Status.ACTIVE:
            return
        first = (Submission.objects.filter(problem_id=duel.problem_id, user_id__in=duel.players(),
                                           contest__isnull=True, verdict=Submission.Verdict.AC,
                                           created__gte=duel.started_at, created__lt=duel.ends_at)
                 .order_by("created", "id").first())
        if first is None and now < duel.ends_at:
            return
        duel.status = Duel.Status.FINISHED
        duel.winner_id = first.user_id if first else None
        a, b = User.objects.get(pk=duel.challenger_id), User.objects.get(pk=duel.opponent_id)
        score = 0.5 if first is None else (1.0 if first.user_id == a.pk else 0.0)
        expected = 1 / (1 + 10 ** ((b.duel_rating - a.duel_rating) / 400))
        delta = round(K * (score - expected))
        duel.challenger_delta, duel.opponent_delta = delta, -delta
        duel.save(update_fields=["status", "winner", "challenger_delta", "opponent_delta"])
        User.objects.filter(pk=a.pk).update(duel_rating=F("duel_rating") + delta)
        User.objects.filter(pk=b.pk).update(duel_rating=F("duel_rating") - delta)


def settle_open(user) -> None:
    for duel in Duel.objects.filter(Q(challenger=user) | Q(opponent=user), status__in=OPEN):
        settle(duel)


def settle_for_submission(sub) -> None:
    """Runner hook: an AC may end a duel on its problem."""
    if sub.verdict != Submission.Verdict.AC or sub.contest_id is not None:
        return
    for duel in Duel.objects.filter(status=Duel.Status.ACTIVE, problem_id=sub.problem_id):
        if sub.user_id in duel.players():
            settle(duel)


def active_duel_for(user, problem):
    if not user.is_authenticated:
        return None
    for duel in Duel.objects.filter(status=Duel.Status.ACTIVE, problem=problem).select_related(
            "challenger", "opponent"):
        if user.pk in duel.players() and timezone.now() < duel.ends_at:
            return duel
    return None
