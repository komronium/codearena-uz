"""Badges, one system for the whole site, the way games do it: a badge family (Duelchi, Yechuvchi, ...) has
levels I-V at rising thresholds, and reaching the next one upgrades the same badge. Levels share their
colours everywhere: I bronze, II silver, III gold, IV platinum, V diamond.

What a family counts is worked out from the data (metrics); a level reached is stored as a UserBadge row and
kept for good (sync), which also dates it and drives the "new badge" toast. board() is what pages draw:
each family at its level, with how far the next one is."""
from dataclasses import dataclass

from django.db import IntegrityError
from django.db.models import Q

ROMAN = ["", "I", "II", "III", "IV", "V"]
METALS = ["", "bronza", "kumush", "oltin", "platina", "olmos"]


@dataclass(frozen=True)
class Family:
    key: str
    name: str
    icon: str
    group: str
    unit: str  # what a level asks for, with {n}
    levels: tuple[int, ...]
    base: int = 0  # where the progress to level I starts (a rating starts at 1200, not 0)


GROUPS = {"problems": "Masalalar", "learn": "Kurslar", "contests": "Musobaqalar", "duels": "Duellar"}
FAMILIES = [
    Family("yechuvchi", "Yechuvchi", "circle-check-big", "problems", "{n} ta masala yechildi", (10, 25, 50, 100, 250)),
    Family("choqqi", "Cho‘qqi", "mountain", "problems", "{n} ta Hard masala", (1, 5, 10, 25, 50)),
    Family("olov", "Olov", "flame", "problems", "{n} kun ketma-ket", (3, 7, 30, 100, 365)),
    Family("bilimdon", "Bilimdon", "graduation-cap", "learn", "{n} ta kurs tugatildi", (1, 3, 5, 10, 20)),
    Family("musobaqachi", "Musobaqachi", "flag", "contests", "{n} ta reytingli musobaqa", (1, 5, 10, 25, 50)),
    Family("sovrindor", "Sovrindor", "medal", "contests", "{n} marta top-3", (1, 3, 5, 10, 25)),
    Family("duelchi", "Duelchi", "swords", "duels", "{n} ta g‘alaba", (5, 10, 50, 100, 250)),
    Family("yengilmas", "Yengilmas", "shield-check", "duels", "{n} ta g‘alaba ketma-ket", (3, 5, 7, 10, 15)),
    Family("duel_ustasi", "Duel ustasi", "trophy", "duels", "Duel reytingi {n}", (1300, 1400, 1500, 1700, 2000), base=1200),
    Family("mukammal", "Mukammal", "target", "duels", "{n} marta 5/5", (1, 5, 10, 25, 50)),
    Family("chaqmoq", "Chaqmoq", "zap", "duels", "{n} marta 5/5, 30 soniyadan tez", (1, 3, 10, 25, 50)),
    Family("poliglot", "Poliglot", "languages", "duels", "{n} ta tilda g‘alaba", (2, 3, 4)),
]
BY_KEY = {f.key: f for f in FAMILIES}
# the metric each family counts, by key
METRIC = {"yechuvchi": "solved", "choqqi": "hard", "olov": "streak", "bilimdon": "courses", "musobaqachi": "rated",
          "sovrindor": "podium", "duelchi": "wins", "yengilmas": "win_run", "duel_ustasi": "duel_peak",
          "mukammal": "perfect", "chaqmoq": "lightning", "poliglot": "languages"}


def metrics(user, only: set[str] | None = None) -> dict[str, int]:
    """What each family counts for `user` right now; `only` limits it to some groups."""
    from apps.classroom.duel_badges import duel_stats
    from apps.contests.models import Participation
    from apps.learn.models import StudyPlan
    from apps.learn.progress import plan_progress
    from apps.problems.daily import streaks
    from apps.problems.models import Problem

    want = only or set(GROUPS)
    out = {}
    if "problems" in want:
        solved = Problem.objects.filter(userproblemsolved__user=user, is_public=True)
        out.update(solved=solved.count(), hard=solved.filter(difficulty=Problem.Difficulty.HARD).count(),
                   streak=streaks(user)[1])
    if "learn" in want:
        plans = list(StudyPlan.objects.filter(is_public=True))
        out["courses"] = sum(1 for p in plan_progress(user, plans).values() if p["completed"])
    if "contests" in want:
        rated = Participation.objects.filter(user=user, rating_after__isnull=False, disqualified=False)
        out.update(rated=rated.count(), podium=rated.filter(rank__lte=3).count())
    if "duels" in want:
        out.update(duel_stats(user))
    return out


def level(family: Family, value: int) -> int:
    return sum(1 for at in family.levels if value >= at)


def sync(user, values: dict[str, int] | None = None) -> list[tuple[str, int]]:
    """Store every level the user has reached and hasn't got yet (each new one unseen, for the award);
    returns the (family, level) pairs it added."""
    from .models import UserBadge

    values = values if values is not None else metrics(user)
    have = set(UserBadge.objects.filter(user=user).values_list("family", "tier"))
    new = [UserBadge(user=user, family=f.key, tier=t) for f in FAMILIES if METRIC[f.key] in values
           for t in range(1, level(f, values[METRIC[f.key]]) + 1) if (f.key, t) not in have]
    if new:
        try:
            UserBadge.objects.bulk_create(new, ignore_conflicts=True)
        except IntegrityError:
            pass
    return [(b.family, b.tier) for b in new]


def board(user, groups: set[str] | None = None, store: bool = True) -> list[dict]:
    """Each family (of `groups`) as a page draws it: its level (the stored one, or higher if just reached),
    title ("Duelchi III"), what the level took, pips for the levels, the date it was earned and the next
    level's progress. A family not reached yet is level 0, shown locked to its owner only."""
    from .models import UserBadge

    values = metrics(user, groups)
    if store:
        sync(user, values)
    stored = {}
    for fam, tier, at in UserBadge.objects.filter(user=user).values_list("family", "tier", "earned_at"):
        if tier >= stored.get(fam, (0, None))[0]:
            stored[fam] = (tier, at)
    out = []
    for f in FAMILIES:
        if groups and f.group not in groups:
            continue
        value = values.get(METRIC[f.key], 0)
        tier = max(level(f, value), stored.get(f.key, (0, None))[0])
        nxt = None
        if tier < len(f.levels):
            at = f.levels[tier]
            start = f.levels[tier - 1] if tier else f.base
            nxt = {"roman": ROMAN[tier + 1], "at": at, "done": max(0, value - start), "total": at - start,
                   "shown": f"{value} / {at}"}
        out.append({
            "key": f.key, "name": f.name, "icon": f.icon, "group": f.group, "group_label": GROUPS[f.group],
            "tier": tier, "roman": ROMAN[tier], "metal": METALS[tier], "max": len(f.levels),
            "title": f"{f.name} {ROMAN[tier]}" if tier else f.name,
            "sub": f.unit.format(n=f.levels[max(tier, 1) - 1]),
            "pips": [i < tier for i in range(len(f.levels))],
            "earned_at": stored.get(f.key, (0, None))[1], "next": nxt, "value": value,
        })
    return out


def next_streak(current: int, best: int) -> dict | None:
    """The next Olov level for the daily card: it needs that many days in a row from the current run."""
    f = BY_KEY["olov"]
    tier = level(f, best)
    if tier >= len(f.levels):
        return None
    at = f.levels[tier]
    return {"name": f"{f.name} {ROMAN[tier + 1]}", "icon": f.icon, "days": at, "left": at - current}


def unseen(user) -> list[dict]:
    """New levels not shown yet, the highest per family, marked seen as they are handed out (once, even with
    two tabs): for the toast."""
    from .models import UserBadge

    rows = list(UserBadge.objects.filter(user=user, seen=False).order_by("-tier"))
    if not rows:
        return []
    claimed = UserBadge.objects.filter(pk__in=[r.pk for r in rows], seen=False).update(seen=True)
    if not claimed:
        return []
    best = {}
    for r in rows:
        if r.family in BY_KEY and r.family not in best:
            f = BY_KEY[r.family]
            best[r.family] = {"key": r.family, "title": f"{f.name} {ROMAN[r.tier]}", "icon": f.icon, "tier": r.tier,
                              "roman": ROMAN[r.tier], "metal": METALS[r.tier], "sub": f.unit.format(n=f.levels[r.tier - 1]),
                              "next": (f"{f.name} {ROMAN[r.tier + 1]}: {f.unit.format(n=f.levels[r.tier])}"
                                       if r.tier < len(f.levels) else "")}
    out = sorted(best.values(), key=lambda b: -b["tier"])
    rare = rarity([(b["key"], b["tier"]) for b in out])
    for b in out:
        b["pct"] = rare[(b["key"], b["tier"])]
    return out


def award(user, groups: set[str]) -> None:
    """Store the levels of some groups right after what can change them (an accept, a finished duel, a rated
    round), so the award shows on the very next page. Never lets a badge error break the caller."""
    try:
        added = sync(user, metrics(user, groups))
        if added:  # and say so on Telegram too, for whoever turned that on
            from django.db import transaction

            from .telegram import notify_badges
            transaction.on_commit(lambda: notify_badges(user.pk, added))
    except Exception:  # noqa: BLE001 - a badge is a nicety; judging, duels and ratings must go on
        import logging
        logging.getLogger(__name__).exception("badge award failed for user %s", getattr(user, "pk", user))


def rarity(pairs=None) -> dict[tuple[str, int], int]:
    """(family, level) -> the percent of active players (anyone who sent code or holds a badge) holding it,
    at least 1 when anyone does."""
    from django.db.models import Count

    from .models import User, UserBadge

    players = max(1, User.objects.filter(is_active=True).filter(Q(submissions__isnull=False) | Q(badges__isnull=False))
                  .distinct().count())
    rows = UserBadge.objects.filter(user__is_active=True).values("family", "tier").annotate(n=Count("user", distinct=True))
    out = {(r["family"], r["tier"]): max(1, round(100 * r["n"] / players)) for r in rows}
    return {p: out.get(p, 0) for p in pairs} if pairs is not None else out


def summaries(user_ids) -> dict[int, dict]:
    """For lists of users: per user the badges held (each family at its best level, highest first), how many
    and the levels in all."""
    from .models import UserBadge

    best: dict[int, dict[str, int]] = {}
    for uid, fam, tier in UserBadge.objects.filter(user_id__in=list(user_ids)).values_list("user_id", "family", "tier"):
        if fam in BY_KEY and tier > best.setdefault(uid, {}).get(fam, 0):
            best[uid][fam] = tier
    out = {}
    for uid, fams in best.items():
        held = sorted(({"key": f, "icon": BY_KEY[f].icon, "tier": t, "roman": ROMAN[t],
                        "title": f"{BY_KEY[f].name} {ROMAN[t]}"} for f, t in fams.items()),
                      key=lambda b: (-b["tier"], [x.key for x in FAMILIES].index(b["key"])))
        out[uid] = {"badges": held, "count": len(held), "levels": sum(fams.values())}
    return out


def ladders(user=None) -> list[dict]:
    """The badges page: every family with all its levels (what each takes, how rare it is, reached or not),
    and for a signed-in user where they stand."""
    mine = {b["key"]: b for b in board(user)} if user is not None and user.is_authenticated else {}
    rare = rarity()
    out = []
    for f in FAMILIES:
        b = mine.get(f.key)
        tier = b["tier"] if b else 0
        out.append({"key": f.key, "name": f.name, "icon": f.icon, "group_label": GROUPS[f.group], "tier": tier,
                    "title": f"{f.name} {ROMAN[tier]}" if tier else f.name, "roman": ROMAN[tier], "mine": b,
                    "levels": [{"tier": i, "roman": ROMAN[i], "metal": METALS[i], "at": at, "sub": f.unit.format(n=at),
                                "pct": rare.get((f.key, i), 0), "done": i <= tier}
                               for i, at in enumerate(f.levels, start=1)]})
    return out
