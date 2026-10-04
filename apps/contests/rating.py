"""Contest rating, the Codeforces way: Mirzayanov's open rating algorithm (2015) with its
newcomer ramp (2020). Apply, replay from scratch, and roll back for a recompute after a late DQ."""
import math

from django.db import transaction
from django.db.models import Count, F

from apps.accounts.models import User

from .models import Contest, Participation
from .standings import compute_standings

# Newcomers: the maths starts everyone at START, but the shown rating starts at 0 and each
# of the first len(RAMP) rated contests adds a bonus on top of the change, so the shown
# rating climbs to the real one and a beginner never sees an early loss. Codeforces uses
# 1400 with +500, 350, 250, 150, 100, 50; this is the same ramp for a 1000 centre.
START = 1000
RAMP = (360, 250, 180, 110, 70, 30)
assert sum(RAMP) == START


def hidden(shown: int, rated: int) -> int:
    """The rating the maths uses for a shown rating after `rated` rated contests."""
    return shown + sum(RAMP[rated:])


def bonus(rated: int) -> int:
    """What the next rated contest adds to the shown rating on top of the change."""
    return RAMP[rated] if rated < len(RAMP) else 0


def _beats(a: float, b: float) -> float:
    """Elo probability that rating `a` beats rating `b`."""
    return 1 / (1 + 10 ** ((b - a) / 400))


def deltas(ratings: list[int], places: list[int]) -> list[int]:
    """Rating changes for one contest from each contestant's (hidden) rating and place.

    The seed is the expected place: 1 + the chance of losing to each other contestant. Each
    contestant is aimed at the rating whose seed is the geometric mean of their seed and their
    actual place, and moves half of the way there. Then the anti-inflation step: everyone pays
    the same small amount so the changes sum to just below zero, and the top 4·√n by rating
    pay up to 10 more so that their changes sum to zero."""
    n = len(ratings)
    if not n:
        return []

    def seed(r: float, skip: int) -> float:
        return 1 + sum(_beats(o, r) for j, o in enumerate(ratings) if j != skip)

    # ponytail: O(n² log R) — about a second at 400 contestants; Codeforces' FFT trick if it grows
    out = []
    for i, (r, place) in enumerate(zip(ratings, places)):
        target = math.sqrt(place * seed(r, i))
        lo, hi = -4000, 8000  # the highest rating still seeded at `target` or below
        while hi - lo > 1:
            mid = (lo + hi) // 2
            lo, hi = (lo, mid) if seed(mid, i) < target else (mid, hi)
        out.append(math.trunc((lo - r) / 2))
    fee = math.trunc(-sum(out) / n) - 1
    out = [d + fee for d in out]
    top = sorted(range(n), key=lambda i: -ratings[i])[:min(4 * round(math.sqrt(n)), n)]
    fee = min(max(math.trunc(-sum(out[i] for i in top) / len(top)), -10), 0)
    return [d + fee for d in out]


def _rated_rows(contest) -> list:
    # Registered but never submitted = didn't take part; rated only if you played
    # (Codeforces/AtCoder rule). Disqualified stays in: ranking last is the penalty.
    # Out of the division: on the board, not rated.
    return [r for r in compute_standings(contest) if (r["attempted"] or r["disqualified"]) and not r["out"]]


def _new_ratings(rows, shown: list[int], rated: list[int]) -> list[int]:
    """Shown ratings after the contest for `rows` (standings order), from each one's shown
    rating before and the number of rated contests behind it."""
    # Places are recounted inside `rows`, which may be a subset of the standings (official
    # rating skips unverified users); a tie group all take its last place, as on Codeforces.
    last = {}
    for i, row in enumerate(rows, start=1):
        last[row["rank"]] = i
    changes = deltas([hidden(s, n) for s, n in zip(shown, rated)], [last[row["rank"]] for row in rows])
    return [s + d + bonus(n) for s, d, n in zip(shown, changes, rated)]


def _rated_counts(user_ids) -> dict[int, int]:
    return dict(Participation.objects.filter(user__in=user_ids, rating_after__isnull=False)
                .values("user").annotate(n=Count("pk")).values_list("user", "n"))


def apply_rating(contest) -> bool:
    """Rate a finished contest once; False if it was already applied."""
    if contest.rating_applied:
        return False
    rows = _rated_rows(contest)
    ids = [r["user"].pk for r in rows]
    shown = dict(User.objects.filter(pk__in=ids).values_list("pk", "rating"))  # standings may be an older read
    rated = _rated_counts(ids)
    before = [shown[pk] for pk in ids]
    after = _new_ratings(rows, before, [rated.get(pk, 0) for pk in ids])

    with transaction.atomic():
        for row, old, new in zip(rows, before, after):
            p = row["participation"]
            p.rank, p.score, p.penalty = row["rank"], row["score"], row["penalty"]
            p.rating_before, p.rating_after = old, new
            p.save(update_fields=["rank", "score", "penalty", "rating_before", "rating_after"])
            User.objects.filter(pk=p.user_id).update(rating=new)

        contest.rating_applied = True
        contest.save(update_fields=["rating_applied"])
    return True


def replay() -> int:
    """Rebuild every rating from zero by re-applying the applied contests in end order; returns
    how many. For a change to the rating maths — it also undoes manual rating edits."""
    with transaction.atomic():
        contests = list(Contest.objects.filter(rating_applied=True).order_by("end", "pk"))
        Participation.objects.filter(rating_after__isnull=False).update(rating_before=None, rating_after=None)
        User.objects.update(rating=0)
        Contest.objects.filter(rating_applied=True).update(rating_applied=False)
        for contest in contests:
            contest.rating_applied = False
            apply_rating(contest)
    return len(contests)


def review_queue(contest) -> list:
    """Standings rows an online official contest must check before its official rating applies:
    the top `review_top_n` verified, not disqualified finishers. A DQ pulls the next one in."""
    if contest.allowed_ip_prefix or not contest.review_top_n:
        return []
    rows = [r for r in _rated_rows(contest) if r["user"].verified_at and not r["disqualified"]]
    return rows[:contest.review_top_n]


def recalc_official() -> None:
    """Rebuild every official rating from scratch: applied official contests in end order,
    verified users only, the same maths and newcomer ramp as the open rating. A full replay,
    so a late DQ, a late verification or un-marking a contest all come out right with no
    rollback bookkeeping."""
    current: dict[int, int] = {}
    played: dict[int, int] = {}
    with transaction.atomic():
        Participation.objects.filter(official_after__isnull=False).update(official_before=None, official_after=None)
        contests = Contest.objects.filter(is_official=True, official_applied_at__isnull=False).order_by("end", "pk")
        for contest in contests:
            rows = [r for r in _rated_rows(contest) if r["user"].verified_at]
            ids = [r["user"].pk for r in rows]
            before = [current.get(pk, 0) for pk in ids]
            after = _new_ratings(rows, before, [played.get(pk, 0) for pk in ids])
            for row, old, new in zip(rows, before, after):
                p = row["participation"]
                p.official_before, p.official_after = old, new
                p.save(update_fields=["official_before", "official_after"])
                current[p.user_id] = new
                played[p.user_id] = played.get(p.user_id, 0) + 1
        User.objects.exclude(pk__in=current).filter(official_rating__isnull=False).update(official_rating=None)
        User.objects.bulk_update([User(pk=pk, official_rating=r) for pk, r in current.items()], ["official_rating"])


def is_latest(contest) -> bool:
    """True when none of the contest's rated participants was rated in a later contest,
    so undoing this contest's deltas can't break anyone's rating chain."""
    rated = Participation.objects.filter(contest=contest, rating_after__isnull=False).values("user_id")
    return not (Participation.objects.filter(user_id__in=rated, rating_after__isnull=False,
                                             contest__end__gt=contest.end)
                .exclude(contest=contest).exists())


def rollback(contest) -> None:
    """Undo the contest's rating. Each user loses exactly this contest's change (newcomer bonus
    included), so a manual rating edit made since is kept."""
    with transaction.atomic():
        for p in Participation.objects.select_for_update().filter(contest=contest, rating_after__isnull=False):
            User.objects.filter(pk=p.user_id).update(rating=F("rating") - (p.rating_after - p.rating_before))
            p.rating_before = p.rating_after = None
            p.save(update_fields=["rating_before", "rating_after"])
        contest.rating_applied = False
        contest.save(update_fields=["rating_applied"])


def recompute(contest) -> None:
    with transaction.atomic():
        rollback(contest)
        apply_rating(contest)
