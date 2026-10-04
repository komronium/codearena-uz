"""Rating tiers and everything that hangs off them: colours, the profile picture per tier,
the progress to the next tier, and the daily-streak badges. Views, template tags and context
processors all import from here."""

# (floor, ceiling, name, color) — floor None = -inf, ceiling None = +inf. The freshman scale
# (shown ratings start at 0, see apps.contests.rating) on Codeforces' own tier colours.
RATING_TIERS = [
    (None, 700, "Boshlovchi", "#888888"),
    (700, 900, "Shogird", "#008000"),
    (900, 1100, "Mutaxassis", "#03A89E"),
    (1100, 1300, "Bilimdon", "#0000FF"),
    (1300, 1500, "Master", "#AA00AA"),
    (1500, 1700, "Ustoz", "#FF8C00"),
    (1700, 1900, "Grandmaster", "#FF0000"),
    (1900, None, "Afsonaviy Grandmaster", "#FF0000"),
]
TIER_ORDER = {name: i for i, (_floor, _ceiling, name, _color) in enumerate(RATING_TIERS)}
# Legendary names are written like Codeforces' LGM: the first letter in ink (black on light), the rest red.
LEGENDARY = RATING_TIERS[-1][0]

# Profile banner per tier: (CSS modifier, the picture's name). Styles live in app.css
# (.ca-banner-<slug> for the banner, .ca-art-<slug> for letter avatars).
TIER_BANNERS = {
    "Boshlovchi": ("boshlovchi", "Yulduzli tun"), "Shogird": ("shogird", "Islimiy naqsh"),
    "Mutaxassis": ("mutaxassis", "Daryo"), "Bilimdon": ("bilimdon", "Rishton koshini"),
    "Master": ("master", "Registon girihi"), "Ustoz": ("ustoz", "Quyosh"),
    "Grandmaster": ("grandmaster", "Olov"), "Afsonaviy Grandmaster": ("afsonaviy", "Toj"),
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


def is_legendary(rating: int) -> bool:
    return rating >= LEGENDARY


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
