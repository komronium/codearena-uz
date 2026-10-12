"""What the duel badges (apps.accounts.badges) count, worked out from finished duels: wins, the longest run
of wins, the best duel rating reached, quiz runs with all five right (and those in under LIGHTNING), and the
languages won in."""
from datetime import timedelta

from django.db.models import Q

from .models import Duel, DuelAnswer

START = 1200
LIGHTNING = timedelta(seconds=30)


def duel_stats(user) -> dict[str, int]:
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
    runs = {}
    for duel_id, correct, shown, answered in (DuelAnswer.objects.filter(user=user, duel__in=[d.pk for d in duels])
                                              .values_list("duel_id", "correct", "shown_at", "answered_at")):
        right, spent = runs.get(duel_id, (0, timedelta()))
        runs[duel_id] = (right + correct, spent + (answered - shown if answered else timedelta(days=1)))
    return {
        "wins": len(wins), "win_run": best_run, "duel_peak": peak,
        "perfect": sum(1 for right, _ in runs.values() if right == 5),
        "lightning": sum(1 for right, spent in runs.values() if right == 5 and spent < LIGHTNING),
        "languages": len({d.language for d in wins if d.mode == Duel.Mode.QUIZ and d.language}),
    }
