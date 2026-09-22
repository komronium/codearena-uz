"""Dynamic per-problem points: a difficulty band, discounted by how many of the
people who tried it actually solved it — the easier a problem turns out to be
in practice, the less it's worth. Codeforces-style continuous decay, tuned for
a small classroom pool (few attempts shouldn't swing the value)."""

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
