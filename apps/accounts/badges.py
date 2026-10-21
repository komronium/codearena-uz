"""Badges, one system for the whole site, the way games do it: a badge family (Duelchi, Yechuvchi, ...) has
levels I-V at rising thresholds, and reaching the next one upgrades the same badge. Levels share their
colours everywhere: I bronze, II silver, III gold, IV platinum, V diamond.

What a family counts is worked out from the data (metrics); a level reached is stored as a UserBadge row and
kept for good (sync), which also dates it and drives the "new badge" toast. board() is what pages draw:
each family at its level, with how far the next one is."""
from dataclasses import dataclass

from django.db import IntegrityError
from django.db.models import Count, Q
from django.utils.translation import gettext_lazy as _tl

ROMAN = ["", "I", "II", "III", "IV", "V"]
METALS = ["", _tl("bronza"), _tl("kumush"), _tl("oltin"), _tl("platina"), _tl("olmos")]


def titled(name: str, tier: int) -> str:
    """A badge at a level, as people read it: "Duelchi · Kumush" (the level by its metal, not a numeral)."""
    return f"{name} · {METALS[tier].capitalize()}" if tier else name


@dataclass(frozen=True)
class Family:
    key: str
    name: str
    icon: str
    group: str
    unit: str  # what a level asks for, with {n}
    levels: tuple[int, ...]
    base: int = 0  # where the progress to level I starts (a rating starts at 1200, not 0)
    hint: str = ""  # the rule in full, when the unit line has to stay short


GROUPS = {"problems": _tl("Masalalar"), "learn": _tl("Kurslar"), "contests": _tl("Musobaqalar"), "duels": _tl("Duellar")}
# where each group is earned (the badge page's link on a tile), and the two sections the page draws: 4 and 8 tiles, so a
# row of 4 (or 2 on a narrow screen) never ends with a lone tile
GROUP_URL = {"problems": "problems:list", "learn": "learn:hub", "contests": "contests:list", "duels": "classroom:duels"}
GROUP_CTA = {"problems": _tl("Masalalarga o‘tish"), "learn": _tl("Kurslarga o‘tish"), "contests": _tl("Musobaqalarga o‘tish"),
             "duels": _tl("Duelga o‘tish")}
SECTION_OF = {"problems": 0, "learn": 0, "contests": 1, "duels": 1}
SECTIONS = [_tl("Masalalar va kurslar"), _tl("Musobaqalar va duellar")]
FAMILIES = [
    Family("yechuvchi", _tl("Yechuvchi"), "circle-check-big", "problems", _tl("{n} ta masala yechildi"), (10, 25, 50, 100, 250)),
    Family("choqqi", _tl("Cho‘qqi"), "mountain", "problems", _tl("{n} ta Hard masala"), (1, 5, 10, 25, 50)),
    Family("olov", _tl("Olov"), "flame", "problems", _tl("{n} kun ketma-ket"), (3, 7, 30, 100, 365)),
    # (named "Bilimdon" before; that is also the Expert rating tier's name, so the badge is called O‘rganuvchi now)
    Family("bilimdon", _tl("O‘rganuvchi"), "graduation-cap", "learn", _tl("{n} ta kurs tugatildi"), (1, 3, 5, 10, 20)),
    Family("musobaqachi", _tl("Musobaqachi"), "flag", "contests", _tl("{n} ta reytingli musobaqa"), (1, 5, 10, 25, 50)),
    Family("sovrindor", _tl("Sovrindor"), "medal", "contests", _tl("{n} marta top-3 (kamida 10 ishtirokchida)"), (1, 3, 5, 10, 25)),
    Family("duelchi", _tl("Duelchi"), "swords", "duels", _tl("{n} ta g‘alaba"), (5, 10, 50, 100, 250)),
    Family("yengilmas", _tl("Yengilmas"), "shield-check", "duels", _tl("{n} ta g‘alaba ketma-ket"), (3, 5, 7, 10, 15)),
    Family("duel_ustasi", _tl("Duel ustasi"), "trophy", "duels", _tl("Duel reytingi {n}"), (1300, 1400, 1500, 1700, 2000), base=1200),
    Family("mukammal", _tl("Mukammal"), "target", "duels", _tl("{n} marta xatosiz duel"), (1, 5, 10, 25, 50)),
    Family("chaqmoq", _tl("Chaqmoq"), "zap", "duels", _tl("{n} marta xatosiz va tez"), (1, 3, 10, 25, 50), hint=_tl("Duelda hamma savolga to‘g‘ri javob va o‘rtacha 6 soniyadan kam.")),
    Family("poliglot", _tl("Poliglot"), "languages", "duels", _tl("{n} ta tilda g‘alaba"), (2, 3, 4)),
]
BY_KEY = {f.key: f for f in FAMILIES}
# the metric each family counts, by key
METRIC = {"yechuvchi": "solved", "choqqi": "hard", "olov": "streak", "bilimdon": "courses", "musobaqachi": "rated",
          "sovrindor": "podium", "duelchi": "wins", "yengilmas": "win_run", "duel_ustasi": "duel_peak",
          "mukammal": "perfect", "chaqmoq": "lightning", "poliglot": "languages"}


PODIUM_MIN = 10  # a top-3 counts in a round with at least this many rated entrants (two entrants all place top 3)


def metrics(user, only: set[str] | None = None, record: bool = False) -> dict[str, int]:
    """What each family counts for `user` right now; `only` limits it to some groups. `record` keeps the courses
    finished now finished for good (learn.PlanDone), for the award paths."""
    from apps.classroom.duel_badges import duel_stats
    from apps.contests.models import Participation
    from apps.learn.models import PlanDone, StudyPlan
    from apps.learn.progress import plan_progress, record_done
    from apps.problems.daily import streaks
    from apps.problems.models import Problem

    want = only or set(GROUPS)
    out = {}
    if "problems" in want:
        solved = Problem.objects.filter(userproblemsolved__user=user, is_public=True)
        out.update(solved=solved.count(), hard=solved.filter(difficulty=Problem.Difficulty.HARD).count(),
                   streak=streaks(user)[1])
    if "learn" in want:
        # a theory-only course is finished by one click ("Tushundim"), so it doesn't count towards the badge
        plans = list(StudyPlan.objects.filter(is_public=True))
        done = {pid for pid, p in plan_progress(user, plans).items() if p["completed"] and not p["theory_only"]}
        if record:
            record_done(user, done)
        kept = set(PlanDone.objects.filter(user=user, plan__in=plans).values_list("plan_id", flat=True))
        out["courses"] = len(done | kept)
    if "contests" in want:
        rated = Participation.objects.filter(user=user, rating_after__isnull=False, disqualified=False, score__gt=0)
        big = (Participation.objects.filter(rating_after__isnull=False, disqualified=False).values("contest")
               .annotate(n=Count("id")).filter(n__gte=PODIUM_MIN).values("contest"))
        out.update(rated=rated.count(), podium=rated.filter(rank__lte=3, contest__in=big).count())
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


def board(user, groups: set[str] | None = None, store: bool = False) -> list[dict]:
    """Each family (of `groups`) as a page draws it: its level (the stored one, or higher if just reached),
    title ("Duelchi III"), what the level took, pips for the levels, the date it was earned and the next
    level's progress. A family not reached yet is level 0, shown locked to its owner only. Reading a page stores
    nothing (`store` is for callers that mean to): levels are stored where they are earned (award) and by the
    recount in the context processor."""
    from django.urls import reverse

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
                   "shown": f"{value} / {at}",
                   # "Kumush: 4 / 5 ta Hard masala": the next level's metal and the count towards it
                   "text": f"{METALS[tier + 1].capitalize()}: {f.unit.format(n=f'{min(value, at)} / {at}')}"}
        out.append({
            "key": f.key, "name": f.name, "hint": f.hint, "url": reverse(GROUP_URL[f.group]), "cta": GROUP_CTA[f.group], "icon": f.icon, "group": f.group, "group_label": GROUPS[f.group],
            "tier": tier, "roman": ROMAN[tier], "metal": METALS[tier], "max": len(f.levels),
            "title": titled(f.name, tier),
            "sub": f.unit.format(n=f.levels[max(tier, 1) - 1]),
            "pips": [i < tier for i in range(len(f.levels))],
            "segs": segments(f, tier, value), "level_name": METALS[tier].capitalize() if tier else "",
            "earned_at": stored.get(f.key, (0, None))[1], "next": nxt, "value": value,
        })
    return out


def segments(family: Family, tier: int, value: int) -> list[int]:
    """The badge's bar, one segment per level: 100 for each level held, the share of the way through the
    next one, 0 after it. One bar says both the level and how far the next is."""
    out = []
    for i, at in enumerate(family.levels):
        if i < tier:
            out.append(100)
        elif i == tier:
            start = family.levels[i - 1] if i else family.base
            out.append(max(0, min(99, round(100 * (value - start) / (at - start)))))
        else:
            out.append(0)
    return out


def next_streak(current: int, best: int) -> dict | None:
    """The next Olov level for the daily card: it needs that many days in a row from the current run."""
    f = BY_KEY["olov"]
    tier = level(f, best)
    if tier >= len(f.levels):
        return None
    at = f.levels[tier]
    return {"name": titled(f.name, tier + 1), "icon": f.icon, "days": at, "left": at - current}


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
            best[r.family] = {"key": r.family, "title": titled(f.name, r.tier), "icon": f.icon, "tier": r.tier,
                              "roman": ROMAN[r.tier], "metal": METALS[r.tier], "sub": f.unit.format(n=f.levels[r.tier - 1]),
                              "next": (f"{METALS[r.tier + 1].capitalize()}: {f.unit.format(n=f.levels[r.tier])}"
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
        added = sync(user, metrics(user, groups, record=True))
        if added:  # and say so in the bell and on Telegram too, for whoever turned that on
            from django.db import transaction

            from .notifications import notify_t
            from .telegram import notify_badges
            best = {}
            for fam, tier in added:
                best[fam] = max(tier, best.get(fam, 0))
            for fam, tier in best.items():
                notify_t(user.pk, "badge", f"badge:{fam}:{tier}", _tl("Yangi nishon: {title}"), "/accounts/badges/",
                         title=lambda fam=fam, tier=tier: titled(BY_KEY[fam].name, tier))
            transaction.on_commit(lambda: notify_badges(user.pk, added))
    except Exception:  # noqa: BLE001 - a badge is a nicety; judging, duels and ratings must go on
        import logging
        logging.getLogger(__name__).exception("badge award failed for user %s", getattr(user, "pk", user))


ACTIVE_DAYS = 90  # the rating board's rule too: someone who did nothing for this long is not a player
RARITY_CACHE = 600


def rarity(pairs=None) -> dict[tuple[str, int], int]:
    """(family, level) -> the percent of active players (sent code or earned a badge in the last ACTIVE_DAYS days)
    holding it, at least 1 when anyone does. Kept for ten minutes."""
    from django.core.cache import cache
    from django.utils import timezone

    from .models import User, UserBadge

    out = cache.get("badge-rarity")
    if out is None:
        since = timezone.now() - timezone.timedelta(days=ACTIVE_DAYS)
        active = User.objects.filter(is_active=True).filter(Q(submissions__created__gte=since) | Q(badges__earned_at__gte=since))
        players = max(1, active.distinct().count())
        rows = (UserBadge.objects.filter(user__in=active.values("pk")).values("family", "tier")
                .annotate(n=Count("user", distinct=True)))
        out = {(r["family"], r["tier"]): max(1, min(100, round(100 * r["n"] / players))) for r in rows}
        cache.set("badge-rarity", out, RARITY_CACHE)
    return {p: out.get(p, 0) for p in pairs} if pairs is not None else out


def backfill() -> int:
    """Store the levels everyone has reached without a word: no award window, no bell, no Telegram. For after a
    recalculation (rating, duel rating) that moves what a badge counts. Returns how many levels it stored."""
    from .models import User, UserBadge

    stored = 0
    for user in User.objects.filter(is_active=True).iterator():
        added = sync(user)
        if added:
            cond = Q()
            for fam, tier in added:
                cond |= Q(family=fam, tier=tier)
            UserBadge.objects.filter(user=user, seen=False).filter(cond).update(seen=True)
            stored += len(added)
    return stored


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
                        "title": titled(BY_KEY[f].name, t)} for f, t in fams.items()),
                      key=lambda b: (-b["tier"], [x.key for x in FAMILIES].index(b["key"])))
        out[uid] = {"badges": held, "count": len(held), "levels": sum(fams.values())}
    return out


def ladders(user=None) -> list[dict]:
    """The badges page: every family with all its levels (what each takes, how rare it is, reached or not),
    and for a signed-in user where they stand."""
    from django.urls import reverse

    mine = {b["key"]: b for b in board(user)} if user is not None and user.is_authenticated else {}
    rare = rarity()
    out = []
    for f in FAMILIES:
        # the same entry board() makes (for a guest, the family at level 0), plus each level's threshold and rarity
        b = mine.get(f.key) or {
            "key": f.key, "name": f.name, "icon": f.icon, "tier": 0, "max": len(f.levels), "level_name": "",
            "segs": [0] * len(f.levels), "sub": f.unit.format(n=f.levels[0]), "earned_at": None,
            "next": {"text": f"{METALS[1].capitalize()}: {f.unit.format(n=f.levels[0])}"}}
        out.append({**b, "group_label": GROUPS[f.group], "mine": mine.get(f.key), "section": SECTION_OF[f.group],
                    "hint": f.hint, "url": reverse(GROUP_URL[f.group]), "cta": GROUP_CTA[f.group],
                    "pips": b.get("pips") or [False] * len(f.levels),
                    "levels": [{"tier": i, "metal": METALS[i], "at": at, "pct": rare.get((f.key, i), 0)}
                               for i, at in enumerate(f.levels, start=1)]})
    return out
