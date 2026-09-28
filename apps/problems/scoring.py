"""Dynamic per-problem points: a difficulty band, discounted by how many of the
people who tried it actually solved it — the easier a problem turns out to be
in practice, the less it's worth. Codeforces-style continuous decay, tuned for
a small classroom pool (few attempts shouldn't swing the value).

The four levels, as the problem setters should read them:
- beginner: one formula or one condition; reading input and printing the answer (~5 min).
- easy: a few conditions or one simple loop, with edge cases to think about (~10-15 min).
- medium: loops and conditions combined, nested loops, lists, strings — an idea is needed (~20-40 min).
- hard: an efficient algorithm (sqrt, sorting + greedy, prefix sums, DP) and careful limits."""

BANDS = {
    "beginner": (10, 50),
    "easy": (30, 100),
    "medium": (100, 250),
    "hard": (250, 500),
}
MIN_ATTEMPTS = 5  # fewer distinct attempters than this: not enough signal, keep band max


def compute_points(difficulty: str, solvers: int, attempts: int) -> int:
    band_min, band_max = BANDS[difficulty]
    if attempts < MIN_ATTEMPTS:
        return band_max
    success_rate = min(solvers / attempts, 1.0)
    raw = band_max - (band_max - band_min) * success_rate
    return round(raw / 5) * 5


def price(problem) -> int:
    """The problem's points now: band maximum until enough people have tried it."""
    if problem.pk is None:
        return BANDS[problem.difficulty][1]
    from django.db.models import Count

    from .models import Problem

    n = Problem.objects.filter(pk=problem.pk).aggregate(
        attempts=Count("submissions__user", distinct=True), solvers=Count("userproblemsolved", distinct=True))
    return compute_points(problem.difficulty, n["solvers"], n["attempts"])


# Solve rate (solvers / people who tried) that fits each level, for students of this portal.
SOLVE_RATE_FLOOR = [("beginner", 0.80), ("easy", 0.55), ("medium", 0.30), ("hard", 0.0)]


def level_for_rate(rate: float) -> str:
    return next(level for level, floor in SOLVE_RATE_FLOOR if rate >= floor)
