from django.utils import timezone

from .models import ContestProblem, Participation


def active_contest_for(user, problem):
    """The running contest `user` is registered for that includes `problem`,
    or None. Used to gate access to not-yet-public contest problems and to
    tag a Submission with its contest for scoring."""
    if not user.is_authenticated:
        return None
    now = timezone.now()
    cp = (
        ContestProblem.objects.filter(problem=problem, contest__start__lte=now, contest__end__gt=now)
        .select_related("contest")
        .first()
    )
    if cp is None:
        return None
    if not Participation.objects.filter(user=user, contest=cp.contest).exists():
        return None
    return cp.contest


def access_allowed(user, contest, remote_addr: str) -> bool:
    """Supervised-mode gate (spec §3/§4.4): checked on register and on each
    submit, since group membership or client IP can change mid-contest."""
    if contest.require_group_id and not contest.require_group.members.filter(pk=user.pk).exists():
        return False
    if contest.allowed_ip_prefix and not (remote_addr or "").startswith(contest.allowed_ip_prefix):
        return False
    return True
