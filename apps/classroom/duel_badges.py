"""Duel badges, worked out from finished duels each time (nothing stored), so a rejudge or a rating replay
flows through: ladders of wins, of wins in a row and of the best duel rating reached, plus three one-offs
for a quiz run (all five right; all five right in under LIGHTNING; a win in every language). A badge once
earned stays: the ladders count the best ever, not the current state."""
from datetime import timedelta

from django.db.models import Q

from .models import Duel, DuelAnswer, DuelQuestion

START = 1200
LIGHTNING = timedelta(seconds=30)
WINS = [(1, "Birinchi g‘alaba", "swords"), (10, "Duelchi", "sword"), (25, "Gladiator", "shield"),
        (50, "Arena chempioni", "crown")]
STREAKS = [(3, "Zanjir", "link"), (7, "Yengilmas", "shield-check")]
PEAKS = [(1300, "Tajribali", "trending-up"), (1500, "Duel ustasi", "trophy")]
LANGUAGES = len(DuelQuestion.Lang.choices)


def _ladder(value: int, steps, sub: str, base: int = 0) -> tuple[list, dict | None]:
    """The steps reached, and the next one with how far along it is from `base` (for a locked badge)."""
    earned = [{"name": n, "icon": i, "sub": sub % at} for at, n, i in steps if value >= at]
    nxt = next(({"name": n, "icon": i, "sub": sub % at, "done": value - base, "total": at - base,
                 "shown": f"{value} / {at}"}
                for at, n, i in steps if value < at), None)
    return earned, nxt


def duel_badges(user) -> dict:
    """{"earned": [...], "next": [...], "total": n}: each badge a dict of name, icon, sub; a next one also done/total."""
    duels = list(Duel.objects.filter(Q(challenger=user) | Q(opponent=user), status=Duel.Status.FINISHED)
                 .order_by("created", "pk"))
    wins = [d for d in duels if d.winner_id == user.pk]
    best_run = run = 0
    rating = peak = START
    for d in duels:
        run = run + 1 if d.winner_id == user.pk else 0
        best_run = max(best_run, run)
        rating += (d.challenger_delta if d.challenger_id == user.pk else d.opponent_delta) or 0
        peak = max(peak, rating)

    # quiz runs: right answers and time spent per duel
    runs = {}
    for duel_id, correct, shown, answered in (DuelAnswer.objects.filter(user=user, duel__in=[d.pk for d in duels])
                                              .values_list("duel_id", "correct", "shown_at", "answered_at")):
        right, spent = runs.get(duel_id, (0, timedelta()))
        runs[duel_id] = (right + correct, spent + (answered - shown if answered else timedelta(days=1)))
    perfect = [pk for pk, (right, _) in runs.items() if right == 5]
    lightning = [pk for pk, (right, spent) in runs.items() if right == 5 and spent < LIGHTNING]
    languages = {d.language for d in wins if d.mode == Duel.Mode.QUIZ and d.language}

    earned, nxt = [], []
    for value, steps, sub, base in ((len(wins), WINS, "%d ta g‘alaba", 0),
                                    (best_run, STREAKS, "%d ta g‘alaba ketma-ket", 0),
                                    (peak, PEAKS, "Duel reytingi %d", START)):
        e, n = _ladder(value, steps, sub, base)
        earned += e
        if n:
            nxt.append(n)
    one_offs = [
        (bool(perfect), {"name": "Mukammal", "icon": "target", "sub": "Duelda 5/5 to‘g‘ri"}, None),
        (bool(lightning), {"name": "Chaqmoq", "icon": "zap", "sub": "5/5, hammasi 30 soniyadan kam"}, None),
        (len(languages) >= LANGUAGES, {"name": "Poliglot", "icon": "languages", "sub": "Har bir tilda g‘alaba"},
         (len(languages), LANGUAGES)),
    ]
    for got, badge, progress in one_offs:
        if got:
            earned.append(badge)
        else:
            nxt.append({**badge, "done": progress[0] if progress else None, "total": progress[1] if progress else None})
    return {"earned": earned, "next": nxt, "total": len(WINS) + len(STREAKS) + len(PEAKS) + len(one_offs)}
