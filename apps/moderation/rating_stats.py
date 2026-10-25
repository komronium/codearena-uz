"""The staff page "Reyting statistikasi": how the contest rating and the duel rating look today, what is about to happen
and where it heads at the present pace, with a few facts. Everything is read from the stored rounds and duels."""
import statistics
from collections import Counter, defaultdict
from datetime import timedelta

from django.utils import timezone
from django.utils.translation import gettext_lazy as _tl

from apps.accounts.models import User
from apps.accounts.tiers import RATING_TIERS, rating_tier, tier_label
from apps.classroom.models import Duel
from apps.accounts.charts import rating_histogram
from apps.contests import rating as rating_system
from apps.contests.models import Contest, Participation

NEAR_UP = 40  # points below the next tier
NEAR_DOWN = 25  # points above the tier's floor
FADING_FROM = 65  # days since the last rated round: off the open board at INACTIVE_DAYS (90)


def _spread(values: list[int]) -> dict:
    if not values:
        return {"n": 0, "avg": 0, "median": 0, "sd": 0, "lo": 0, "hi": 0}
    return {"n": len(values), "avg": round(statistics.fmean(values)), "median": round(statistics.median(values)),
            "sd": round(statistics.pstdev(values)) if len(values) > 1 else 0, "lo": min(values), "hi": max(values)}


def _buckets(values: list[int], size: int = 100) -> list[dict]:
    if not values:
        return []
    lo, hi = min(values) // size * size, max(values) // size * size
    counts = Counter(v // size * size for v in values)
    top = max(counts.values())
    return [{"from": x, "n": counts.get(x, 0), "pct": round(100 * counts.get(x, 0) / top)} for x in range(lo, hi + size, size)]


def _tiers(ratings: list[int]) -> list[dict]:
    counts = Counter(rating_tier(r) for r in ratings)
    total = max(1, len(ratings))
    return [{"name": name, "uz": tier_label(name), "color": color, "n": counts.get(name, 0),
             "pct": round(100 * counts.get(name, 0) / total), "floor": floor, "ceiling": ceiling}
            for floor, ceiling, name, color in RATING_TIERS]


def contest_rating() -> dict:
    now = timezone.now()
    pool = list(rating_system.pool().values("pk", "username", "rating"))
    ratings = [u["rating"] for u in pool]
    by_user = {u["pk"]: u for u in pool}
    rows = list(Participation.objects.filter(rating_after__isnull=False, disqualified=False)
                .select_related("contest", "user").order_by("contest__end", "pk"))
    played, last_end, first_end = Counter(), {}, {}
    per_contest = defaultdict(list)
    lost = set()
    for p in rows:
        p.before = played[p.user_id]  # the rated rounds behind this one
        played[p.user_id] += 1
        if p.rating_after < p.rating_before:
            lost.add(p.user_id)
        last_end[p.user_id] = p.contest.end
        first_end.setdefault(p.user_id, p.contest.end)
        per_contest[p.contest_id].append(p)

    out = {"pool": _spread(ratings), "tiers": _tiers(ratings), "chart": rating_histogram(ratings, floor=0, ceiling=2000),
           "ever_rated": len({p.user_id for p in rows}), "rated_rounds": len(per_contest)}
    ordered = sorted(pool, key=lambda u: -u["rating"])
    out["top"] = ordered[:3]
    out["gap_1_2"] = ordered[0]["rating"] - ordered[1]["rating"] if len(ordered) > 1 else None

    # the rounds, newest first: field, the average change (the system's drift) and the biggest moves
    rounds = []
    for cid, ps in per_contest.items():
        c = ps[0].contest
        deltas = [p.rating_after - p.rating_before for p in ps]
        newcomers = sum(1 for p in ps if p.before == 0)
        rounds.append({"contest": c, "n": len(ps), "avg_delta": round(statistics.fmean(deltas), 1), "newcomers": newcomers,
                       "avg_before": round(statistics.fmean(p.rating_before for p in ps)),
                       "up_pct": round(100 * sum(1 for d in deltas if d > 0) / len(deltas))})
    rounds.sort(key=lambda r: r["contest"].end, reverse=True)
    out["rounds"] = rounds[:8]
    out["field_avg"] = round(statistics.fmean(r["n"] for r in rounds), 1) if rounds else 0
    out["drift"] = round(statistics.fmean(r["avg_delta"] for r in rounds), 1) if rounds else 0

    # by month: contests, rated entries, first-time rated players
    months = defaultdict(lambda: {"rounds": 0, "entries": 0, "new": 0})
    for r in rounds:
        m = r["contest"].end.strftime("%Y-%m")
        months[m]["rounds"] += 1
        months[m]["entries"] += r["n"]
    for uid, end in first_end.items():
        months[end.strftime("%Y-%m")]["new"] += 1
    out["months"] = [{"month": m, **v} for m, v in sorted(months.items())][-6:]
    top = max((m["entries"] for m in out["months"]), default=1) or 1
    for m in out["months"]:
        m["pct"] = round(100 * m["entries"] / top)

    # what is about to happen
    near_up, near_down, fading = [], [], []
    for u in pool:
        for floor, ceiling, name, _c in RATING_TIERS:
            if ceiling is not None and (floor is None or u["rating"] >= floor) and u["rating"] < ceiling:
                if ceiling - u["rating"] <= NEAR_UP:
                    near_up.append({**u, "need": ceiling - u["rating"], "to": tier_label(RATING_TIERS[[t[2] for t in RATING_TIERS].index(name) + 1][2])})
                if floor is not None and u["rating"] - floor <= NEAR_DOWN:
                    near_down.append({**u, "room": u["rating"] - floor, "tier": tier_label(name)})
        days = (now - last_end[u["pk"]]).days if u["pk"] in last_end else None
        if days is not None and days >= FADING_FROM:
            fading.append({**u, "days": days, "left": rating_system.INACTIVE_DAYS - days})
    out["near_up"] = sorted(near_up, key=lambda u: u["need"])[:6]
    out["near_down"] = sorted(near_down, key=lambda u: u["room"])[:6]
    out["fading"] = sorted(fading, key=lambda u: u["left"])[:6]
    out["n_fading"] = len(fading)
    upcoming = Contest.objects.filter(is_rated=True, start__gt=now).order_by("start")
    out["upcoming"] = {"n": upcoming.count(), "next": upcoming.first()}
    ramp = rating_system.RAMP
    out["ramping"] = sum(1 for u in pool if played[u["pk"]] < len(ramp))

    # at this pace
    recent = [m for m in out["months"][:-1]][-3:]  # the last full months
    pace = round(statistics.fmean(m["new"] for m in recent), 1) if recent else 0
    veterans = [u["rating"] for u in pool if played[u["pk"]] >= len(ramp)]
    settle = round(statistics.fmean(veterans)) if veterans else out["pool"]["avg"]
    leaving = len(fading)
    pool_in_3 = max(0, round(len(pool) + 3 * pace - leaving))
    # newcomers climb to about the veterans' level (the ramp lifts them there); the average moves towards it
    avg_in_3 = round((sum(ratings) + 3 * pace * settle - sum(u["rating"] for u in fading)) / pool_in_3) if pool_in_3 else 0
    out["forecast"] = {"pace": pace, "leaving": leaving, "pool_in_3": pool_in_3, "avg_in_3": avg_in_3, "settle": settle,
                       "drift_10": round(out["drift"] * 10)}

    # facts
    facts = []
    if rows:
        gain = max(rows, key=lambda p: p.rating_after - p.rating_before)
        loss = min(rows, key=lambda p: p.rating_after - p.rating_before)
        peak = max(rows, key=lambda p: p.rating_after)
        facts.append({"icon": "trending-up", "title": _tl("Eng katta o‘sish"), "value": f"+{gain.rating_after - gain.rating_before}",
                      "who": gain.user, "note": gain.contest.title})
        facts.append({"icon": "trending-down", "title": _tl("Eng katta tushish"), "value": str(loss.rating_after - loss.rating_before),
                      "who": loss.user, "note": loss.contest.title})
        facts.append({"icon": "mountain", "title": _tl("Hamma vaqtdagi eng yuqori"), "value": str(peak.rating_after),
                      "who": peak.user, "note": peak.contest.title})
        most = played.most_common(1)[0]
        facts.append({"icon": "flag", "title": _tl("Eng ko‘p reytingli raund"), "value": most[1], "unit": _tl("ta"),
                      "who": User.objects.filter(pk=most[0]).first(), "note": ""})
        biggest = max(rounds, key=lambda r: r["n"])
        facts.append({"icon": "users", "title": _tl("Eng gavjum raund"), "value": biggest["n"], "unit": _tl("kishi"), "who": None,
                      "note": biggest["contest"].title})
        never_lost = len(set(played) - lost)
        facts.append({"icon": "shield-check", "title": _tl("Hech qachon tushmaganlar"), "value": never_lost, "unit": f"/ {len(played)}",
                      "who": None, "note": _tl("reytingi bir marta ham kamaymagan")})
    out["facts"] = facts
    return out


def duel_rating() -> dict:
    now = timezone.now()
    finished = Duel.objects.filter(status=Duel.Status.FINISHED, mode=Duel.Mode.QUIZ)
    ids = {i for pair in finished.values_list("challenger_id", "opponent_id") for i in pair}
    players = list(User.objects.filter(pk__in=ids, is_active=True).values("pk", "username", "duel_rating"))
    ratings = [u["duel_rating"] for u in players]
    n = finished.count()
    draws = finished.filter(winner__isnull=True).count()
    week = finished.filter(finished_at__gte=now - timedelta(days=7)).count()

    names = dict(User.objects.filter(pk__in=ids).values_list("pk", "username"))
    pairs = defaultdict(lambda: Counter())  # (a, b) sorted -> wins of each, draws
    games, wins, draw_of, streak, best = Counter(), Counter(), Counter(), Counter(), (0, None)
    biggest = (0, None)  # the largest single rating gain
    for d in finished.order_by("finished_at", "pk").values("challenger_id", "opponent_id", "winner_id", "challenger_delta", "opponent_delta"):
        c, o, w = d["challenger_id"], d["opponent_id"], d["winner_id"]
        key = tuple(sorted((c, o)))
        pairs[key]["n"] += 1
        for uid, delta, other in ((c, d["challenger_delta"], o), (o, d["opponent_delta"], c)):
            games[uid] += 1
            if delta is not None and delta > biggest[0]:
                biggest = (delta, (uid, other))
            if w == uid:
                wins[uid] += 1
                pairs[key][uid] += 1
                streak[uid] += 1
                if streak[uid] > best[0]:
                    best = (streak[uid], uid)
            else:
                streak[uid] = 0
            if w is None:
                draw_of[uid] += 1
        if w is None:
            pairs[key]["draws"] += 1

    def pair_row(key, rec):
        a, b = key
        wa, wb = rec[a], rec[b]
        return {"a": names.get(a), "b": names.get(b), "wa": wa, "wb": wb, "draws": rec["draws"], "n": rec["n"],
                "share": round(100 * wa / (wa + wb)) if wa + wb else 50, "gap": abs(wa - wb)}

    rows = [pair_row(k, r) for k, r in pairs.items()]
    # a head-to-head means something only after a few games: the lists take pairs with at least this many
    many = [r for r in rows if r["n"] >= 10] or [r for r in rows if r["n"] >= 3]
    busiest = sorted(rows, key=lambda r: -r["n"])[:3]
    closest = sorted((r for r in many if r["wa"] + r["wb"]), key=lambda r: (r["gap"] / (r["wa"] + r["wb"]), -r["n"]))[:3]
    lopsided = sorted((r for r in many if r["wa"] + r["wb"]), key=lambda r: (-(max(r["wa"], r["wb"]) / (r["wa"] + r["wb"])), -r["n"]))[:3]
    for r in lopsided:  # the stronger side first, so the long bar is always on the left
        if r["wb"] > r["wa"]:
            r.update(a=r["b"], b=r["a"], wa=r["wb"], wb=r["wa"], share=100 - r["share"])

    facts = []

    def fact(icon, title, value, who="", note="", unit=""):
        facts.append({"icon": icon, "title": title, "value": value, "who": who, "note": note, "unit": unit})

    if best[1]:
        fact("flame", _tl("Eng uzun g‘alaba seriyasi"), best[0], names.get(best[1]), unit=_tl("ketma-ket"))
    if games:
        busy = games.most_common(1)[0]
        fact("swords", _tl("Eng faol o‘yinchi"), busy[1], names.get(busy[0]), unit=_tl("duel"))
        rate = [(wins[u] / g, u, g) for u, g in games.items() if g >= 20]
        if rate:
            r, u, g = max(rate)
            fact("percent", _tl("Eng yuqori g‘alaba ulushi"), round(100 * r), names.get(u), note=_tl("{g} duelda").format(g=g), unit="%")
        if draw_of:
            u, dn = draw_of.most_common(1)[0]
            fact("scale", _tl("Eng ko‘p durang qilgan"), dn, names.get(u), unit=_tl("durang"))
    if biggest[1]:
        fact("trending-up", _tl("Bir duelda eng katta o‘sish"), f"+{biggest[0]}", names.get(biggest[1][0]),
             note=_tl("{other} ga qarshi").format(other=names.get(biggest[1][1])))
    fact("calendar-days", _tl("So‘nggi 7 kun"), week, "", unit=_tl("duel"))
    return {"n": n, "players": len(players), "draw_pct": round(100 * draws / n) if n else 0, "week": week,
            "spread": _spread(ratings), "tiers": _tiers(ratings), "chart": rating_histogram(ratings, size=None, tiers=False),
            "per_player": round(2 * n / len(players), 1) if players else 0,
            "top": sorted(players, key=lambda u: -u["duel_rating"])[:3], "facts": facts,
            "rivalries": [{"title": _tl("Eng ko‘p o‘ynalgan"), "icon": "repeat", "rows": busiest},
                          {"title": _tl("Eng qizg‘in: deyarli teng hisob"), "icon": "equal", "rows": closest},
                          {"title": _tl("Eng bir tomonlama"), "icon": "chevrons-right", "rows": lopsided}]}
