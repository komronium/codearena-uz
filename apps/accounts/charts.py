"""The rating histogram drawn by accounts/_rating_chart.html: how many people hold each band of the rating, a column per
band in its tier's colour, tier boundaries on the scale, a grid with round numbers, the viewer's own band marked and the
median shown. One definition for the public rating page and the staff statistics."""
import statistics
from collections import Counter

from .tiers import RATING_TIERS, rating_tier, tier_color, tier_label


def _step(top: int) -> int:
    """A round grid step that gives at most four lines over the tallest column."""
    for s in (1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000):
        if top / s <= 4:
            return s
    return top


def _auto_size(ratings: list[int]) -> int:
    """A band width that gives about 8 to 20 columns over what is there: 100 for a wide spread, finer for a narrow one."""
    span = max(ratings) - min(ratings)
    for s in (100, 50, 25, 10, 5):
        if span / s >= 7:
            return s
    return 5


def rating_histogram(ratings: list[int], me: int | None = None, size: int | None = 100, tiers: bool = True,
                     floor: int | None = None, ceiling: int | None = None) -> dict | None:
    """Columns for `ratings` in bands of `size`. `tiers`: colour each column by the tier of its middle and put the tier
    boundaries on the scale (the contest rating); off: one colour and an even scale (the duel rating). `floor`/`ceiling`
    widen the scale (the rating page shows at least up to 2000 so the tiers above everyone still show)."""
    if not ratings:
        return None
    if size is None:
        size = _auto_size(ratings)
    lo = min(min(ratings), me if me is not None else min(ratings), floor if floor is not None else min(ratings)) // size * size
    hi = max(max(ratings), me if me is not None else 0, ceiling if ceiling is not None else 0) // size * size
    counts = Counter(r // size * size for r in ratings)
    top = max(counts.values())
    step = _step(top)
    top_axis = -(-top // step) * step
    mine = None if me is None else me // size * size
    cols = []
    for x in range(lo, hi + size, size):
        n = counts.get(x, 0)
        mid = x + size // 2
        cols.append({"from": x, "to": x + size - 1, "n": n, "pct": round(100 * n / top_axis, 2),
                     "color": tier_color(mid) if tiers else "", "tier": tier_label(rating_tier(mid)) if tiers else "",
                     "me": x == mine})
    span = (hi + size) - lo
    xticks = []
    if tiers:
        for floor_, _ceil, name, color in RATING_TIERS:
            if floor_ is not None and lo <= floor_ < hi + size:
                xticks.append({"left": round(100 * (floor_ - lo) / span, 2), "value": floor_, "color": color})
    else:
        every = max(1, round(len(cols) / 6))
        for i in range(0, len(cols), every):
            xticks.append({"left": round(100 * i / len(cols), 2), "value": cols[i]["from"], "color": ""})
    yticks = [{"value": v, "bottom": round(100 * v / top_axis, 2)} for v in range(0, top_axis + 1, step)]
    median = statistics.median(ratings)
    present, empty = [], []
    if tiers:
        seen = Counter(rating_tier(r) for r in ratings)
        present = [{"name": tier_label(n), "color": c, "n": seen[n]} for _f, _c, n, c in RATING_TIERS if seen.get(n)]
        empty = [{"name": tier_label(n), "color": c, "from": f} for f, _c, n, c in RATING_TIERS if f is not None and not seen.get(n)]
    return {"cols": cols, "xticks": xticks, "yticks": yticks, "n": len(ratings), "median": round(median),
            "median_left": round(100 * (median - lo) / span, 2), "present": present, "empty": empty, "size": size, "tiers": tiers,
            "mine": me}
