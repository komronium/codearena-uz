from django.utils import timezone

from .models import ContestProblem, Participation
from django.utils.translation import gettext as _t
from django.utils.translation import gettext as _t


def active_contest_for(user, problem):
    """The running contest `user` is registered for that includes `problem`,
    or None. Used to gate access to not-yet-public contest problems and to
    tag a Submission with its contest for scoring."""
    if not user.is_authenticated:
        return None
    now = timezone.now()
    cps = (
        ContestProblem.objects.filter(
            problem=problem,
            contest__start__lte=now,
            contest__end__gt=now,
            contest__participations__user=user,
        )
        .select_related("contest")
        .order_by("contest_id")
    )
    for cp in cps:
        if not cp.contest.personal_minutes:
            return cp.contest
        # a personal-clock round counts only between "Boshlash" and the end of the person's own time
        mine = Participation.objects.filter(user=user, contest=cp.contest).select_related("contest").first()
        if mine is not None and mine.can_submit_now():
            return cp.contest
    return None


def in_upcoming_contest(problem) -> bool:
    """Problems of a not-yet-started contest are secret regardless of is_public:
    no statement, no submit, not in the list. Staff and the author still see them."""
    return ContestProblem.objects.filter(problem=problem, contest__start__gt=timezone.now()).exists()


def in_running_contest(problem) -> bool:
    """While a contest with this problem runs, other people's solutions (and who is fastest) stay hidden."""
    now = timezone.now()
    return ContestProblem.objects.filter(problem=problem, contest__start__lte=now, contest__end__gt=now).exists()


def access_allowed(user, contest, remote_addr: str) -> bool:
    """Supervised-mode gate (spec §3/§4.4): checked on register and on each
    submit, since the client IP can change mid-contest."""
    if contest.allowed_ip_prefix and not (remote_addr or "").startswith(contest.allowed_ip_prefix):
        return False
    return True


def reuse_reason(problem, contest) -> str:
    """Why participants of `contest` may already know `problem`; "" when it is fresh."""
    if problem.is_public:
        return _t("Ochiq masala — reytingli musobaqaga faqat yashirin, yangi masala qo‘shiladi.")
    if ContestProblem.objects.filter(problem=problem).exclude(contest_id=contest.pk).exists():
        return _t("Bu masala boshqa musobaqada ishlatilgan.")
    return ""
