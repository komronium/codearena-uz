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
