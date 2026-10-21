"""What the duel badges (apps.accounts.badges) count, worked out from finished duels: wins, the longest run
of wins, the best duel rating reached, quiz runs with every question right (and those at under LIGHTNING a question), and the
languages won in."""
from datetime import timedelta

from django.db.models import Q

from .models import Duel, DuelAnswer

START = 1200
LIGHTNING = timedelta(seconds=6)  # per question: a flawless run faster than this on average
MIN_LOSER_ANSWERS = 3  # a win over somebody who barely played (or idled) is a walkover: no badge, no quest


def walkovers(duels, user) -> set[int]:
    """Ids of `duels` the other player answered fewer than MIN_LOSER_ANSWERS questions in."""
    ids = [d.pk for d in duels]
    answered = {}
    for duel_id, uid in (DuelAnswer.objects.filter(duel_id__in=ids, answered_at__isnull=False)
                         .exclude(user=user).values_list("duel_id", "user_id")):
        answered[duel_id] = answered.get(duel_id, 0) + 1
    # only quiz duels have answers to count; the old coding races stay as they were
    return {d.pk for d in duels if d.mode == Duel.Mode.QUIZ and d.opponent_id and answered.get(d.pk, 0) < MIN_LOSER_ANSWERS}


def duel_stats(user) -> dict[str, int]:
    duels = list(Duel.objects.filter(Q(challenger=user) | Q(opponent=user), status=Duel.Status.FINISHED)
                 .order_by("created", "pk"))
    walk = walkovers([d for d in duels if d.winner_id == user.pk], user)
    wins = [d for d in duels if d.winner_id == user.pk and d.pk not in walk]
    best_run = run = 0
    rating = peak = START
    for d in duels:
        if d.pk not in walk:  # a walkover is neither a win nor a loss for the run (its Elo change still counts)
            run = run + 1 if d.winner_id == user.pk else 0
            best_run = max(best_run, run)
        rating += (d.challenger_delta if d.challenger_id == user.pk else d.opponent_delta) or 0
        peak = max(peak, rating)
    total = {d.pk: len(d.questions) or 5 for d in duels}  # a duel's own question count (5 before the seven-question ones)
    runs = {}
    for duel_id, correct, shown, answered in (DuelAnswer.objects.filter(user=user, duel__in=[d.pk for d in duels])
                                              .values_list("duel_id", "correct", "shown_at", "answered_at")):
        right, spent = runs.get(duel_id, (0, timedelta()))
        runs[duel_id] = (right + correct, spent + (answered - shown if answered else timedelta(days=1)))
    return {
        "wins": len(wins), "win_run": best_run, "duel_peak": peak,
        "perfect": sum(1 for duel_id, (right, _) in runs.items() if right == total[duel_id]),
        "lightning": sum(1 for duel_id, (right, spent) in runs.items()
                         if right == total[duel_id] and spent < LIGHTNING * total[duel_id]),
        "languages": len({d.language for d in wins if d.mode == Duel.Mode.QUIZ and d.language}),
    }
