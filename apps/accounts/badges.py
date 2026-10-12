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


def sync(user, values: dict[str, int] | None = None) -> None:
    """Store every level the user has reached and hasn't got yet (each new one unseen, for the toast)."""
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
            best[r.family] = {"title": f"{f.name} {ROMAN[r.tier]}", "icon": f.icon, "tier": r.tier, "roman": ROMAN[r.tier],
                              "metal": METALS[r.tier], "sub": f.unit.format(n=f.levels[r.tier - 1])}
    return sorted(best.values(), key=lambda b: -b["tier"])
