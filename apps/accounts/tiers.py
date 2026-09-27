"""Rating tiers and everything that hangs off them: colours, the profile picture per tier,
the progress to the next tier, and the daily-streak badges. Views, template tags and context
processors all import from here."""

# (floor, ceiling, name, color) — floor None = -inf, ceiling None = +inf.
RATING_TIERS = [
    (None, 1300, "Newbie", "#6B7280"),
    (1300, 1500, "Pupil", "#16A34A"),
    (1500, 1700, "Specialist", "#06B6D4"),
    (1700, 1900, "Expert", "#3B82F6"),
    (1900, 2100, "Candidate Master", "#8B5CF6"),
    (2100, 2300, "Master", "#D97706"),
    (2300, 2400, "International Master", "#EA580C"),
    (2400, None, "Grandmaster", "#DC2626"),
]
TIER_ORDER = {name: i for i, (_floor, _ceiling, name, _color) in enumerate(RATING_TIERS)}

# Profile banner per tier: (CSS modifier, the picture's name). Styles live in app.css
# (.ca-banner-<slug> for the banner, .ca-art-<slug> for letter avatars).
TIER_BANNERS = {
    "Newbie": ("newbie", "Yulduzli tun"), "Pupil": ("pupil", "Islimiy naqsh"), "Specialist": ("specialist", "Daryo"),
    "Expert": ("expert", "Rishton koshini"), "Candidate Master": ("candidate-master", "Registon girihi"),
    "Master": ("master", "Quyosh"), "International Master": ("international-master", "Olov"),
    "Grandmaster": ("grandmaster", "Toj"),
}

# Daily-problem streak badges: (days, name, icon). Earned by the best run ever, kept for good.
STREAK_BADGES = [(7, "Chiroq", "lamp"), (30, "Mash’al", "flame"), (100, "Quyosh", "sun")]


def _band(rating: int) -> tuple:
    for band in RATING_TIERS:
        floor, ceiling = band[0], band[1]
        if (floor is None or rating >= floor) and (ceiling is None or rating < ceiling):
            return band
    return RATING_TIERS[-1]


def rating_tier(rating: int) -> str:
    return _band(rating)[2]


def tier_color(rating: int) -> str:
    return _band(rating)[3]


def tier_banner(rating: int) -> tuple[str, str]:
    """(css slug, picture name) of the rating's tier."""
    return TIER_BANNERS[rating_tier(rating)]


def next_tier(rating: int) -> dict | None:
    """The tier above `rating`: its name, colour, the points still needed and the percent
    of the way through the current tier (the bottom tier counts from 0). None at the top."""
    for i, (floor, ceiling, _name, _color) in enumerate(RATING_TIERS):
        if ceiling is not None and rating < ceiling and (floor is None or rating >= floor):
            _floor, _ceiling, name, color = RATING_TIERS[i + 1]
            floor = floor or 0
            pct = max(0, round(100 * (rating - floor) / (ceiling - floor)))
            return {"name": name, "color": color, "need": ceiling - rating, "pct": pct}
    return None


def streak_badges(current: int, best: int) -> dict:
    """Badges earned by the best run ever; the next one counts from the current run, since
    it needs that many days in a row from now on."""
    earned = [{"days": d, "name": n, "icon": i} for d, n, i in STREAK_BADGES if best >= d]
    nxt = next(({"days": d, "name": n, "icon": i, "left": d - current}
                for d, n, i in STREAK_BADGES if best < d), None)
    return {"best": best, "earned": earned, "next": nxt}
