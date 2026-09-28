"""Solves and practice points are derived data. A user has solved a problem iff they have
an eligible AC for it: a practice AC, or a contest AC once staff published the ended
contest and the user was not disqualified from it. practice_points is the live price of
the solved problems the user did not author. Everything that can change either goes
through here."""
from collections.abc import Iterable

from django.db import transaction
from django.db.models import Count, Exists, F, IntegerField, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce

from apps.accounts.models import User
from apps.contests.models import Participation
from apps.problems.daily import DAILY_BONUS, refresh_daily
from apps.problems.models import MAX_HINT_PCT, DailySolve, HintUnlock

from .models import Submission, UserProblemSolved


def _eligible_acs(problem_id: int):
    disqualified = Participation.objects.filter(user_id=OuterRef("user_id"), contest_id=OuterRef("contest_id"),
                                                disqualified=True)
    return (Submission.objects
            .filter(Q(contest__isnull=True) | Q(contest__published_at__isnull=False), ~Exists(disqualified),
                    problem_id=problem_id, verdict=Submission.Verdict.AC)
            .order_by("created", "id"))


def refresh_solves(problem_id: int, user_ids: Iterable[int] | None = None) -> None:
    """Make the UserProblemSolved rows of `problem_id` follow the rule for `user_ids`
    (None = everyone with a row or an eligible AC), then resync those users' points."""
    acs, rows = _eligible_acs(problem_id), UserProblemSolved.objects.filter(problem_id=problem_id)
    if user_ids is not None:
        user_ids = set(user_ids)
        acs, rows = acs.filter(user_id__in=user_ids), rows.filter(user_id__in=user_ids)
    wanted = {}  # user -> (their earliest eligible AC, its hint share)
    ac_at = {}
    for sub_id, user_id, created in acs.values_list("id", "user_id", "created"):
        if user_id not in wanted:
            wanted[user_id], ac_at[user_id] = sub_id, created
    paid = {}
    for user_id, at, cost in (HintUnlock.objects.filter(hint__problem_id=problem_id, user_id__in=wanted.keys())
                              .values_list("user_id", "at", "hint__cost_pct")):
        if at < ac_at[user_id]:
            paid[user_id] = paid.get(user_id, 0) + cost
    wanted = {u: (sub_id, min(paid.get(u, 0), MAX_HINT_PCT)) for u, sub_id in wanted.items()}
    # ponytail: no per-user lock; a rejudge or disqualification racing a fresh AC of the
    # same user+problem can leave one stale row until that pair is refreshed again. Lock
    # the user row here if that is ever seen.
    with transaction.atomic():
        current = {u: (sub_id, pct) for u, sub_id, pct in
                   rows.values_list("user_id", "first_ac_submission_id", "hint_pct")}
        users = user_ids if user_ids is not None else current.keys() | wanted.keys()
        new = [u for u in users if wanted.get(u) and u not in current]
        for user_id in users:
            want = wanted.get(user_id)
            if want == current.get(user_id):
                continue
            if want is None:
                UserProblemSolved.objects.filter(user_id=user_id, problem_id=problem_id).delete()
            else:
                UserProblemSolved.objects.update_or_create(
                    user_id=user_id, problem_id=problem_id,
                    defaults={"first_ac_submission_id": want[0], "hint_pct": want[1]})
    if new:  # a fresh practice solve that looks copied earns nothing until a teacher clears it
        from apps.integrity.practice import auto_hold

        auto_hold(problem_id, new)
    refresh_daily(problem_id, None if user_ids is None else users)
    sync_practice_points(users)


def sync_practice_points(user_ids: Iterable[int] | None = None) -> None:
    """practice_points = current price of each solved problem the user did not author,
    less the share paid for hints. A solve a teacher confirmed as not the student's own work
    (integrity.PracticeReview) earns nothing, daily bonus included. One UPDATE; None = every user."""
    from apps.integrity.models import PracticeReview

    voided = PracticeReview.objects.filter(user_id=OuterRef("user_id"), confirmed=True)
    bonus = (DailySolve.objects.filter(user_id=OuterRef("pk")).exclude(daily__problem__author_id=OuterRef("pk"))
             .exclude(Exists(voided.filter(problem_id=OuterRef("daily__problem_id"))))
             .values("user_id").annotate(n=Count("pk")).values("n"))
    total = (UserProblemSolved.objects.filter(user_id=OuterRef("pk"))
             .exclude(problem__author_id=OuterRef("pk"))
             .exclude(Exists(voided.filter(problem_id=OuterRef("problem_id"))))
             .values("user_id")
             .annotate(total=Sum(F("problem__points") * (100 - F("hint_pct")) / 100)).values("total"))
    users = User.objects.all() if user_ids is None else User.objects.filter(pk__in=list(user_ids))
    # ponytail: rewrites every row of `users`, changed or not; filter to changed rows if
    # the 5-minute sweep over all users ever shows up in DB load.
    users.update(practice_points=Coalesce(Subquery(total, output_field=IntegerField()), 0)
                 + DAILY_BONUS * Coalesce(Subquery(bonus, output_field=IntegerField()), 0))
