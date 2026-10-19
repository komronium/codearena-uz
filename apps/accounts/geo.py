"""The boards' place filters: country, then city and school, each offering only what people on the board
have (with how many)."""

from collections import Counter

from .countries import COUNTRIES

KEEP = ("q", "sort", "tier")  # the board's other filters that a place filter must not drop


def board_geo(request, rows):
    """rows: (country, city, school) of everyone on the board. Returns (conditions for a User queryset, context
    for _geo_filters.html). A value in the URL that nobody on the board has is ignored."""
    countries = Counter(c for c, _, _ in rows if c in COUNTRIES)
    country = request.GET.get("country", "")
    country = country if country in countries else ""
    in_country = [r for r in rows if r[0] == country] if country else []
    city = request.GET.get("city", "")
    city = city if any(r[1] == city for r in in_country) else ""
    school = request.GET.get("school", "")
    school = school if any(r[2] == school for r in in_country) else ""
    # city and school are separate questions (where one lives, where one studies); each list counts the people the
    # other one's choice leaves, so no pick leads to an empty table
    cities = Counter(c for _, c, s in in_country if c and (not school or s == school))
    schools = Counter(s for _, c, s in in_country if s and (not city or c == city))
    if city:
        cities.setdefault(city, 0)
    if school:
        schools.setdefault(school, 0)

    def ranked(counter):
        return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))

    cond = {k: v for k, v in (("country", country), ("location", city), ("school", school)) if v}
    return cond, {
        "geo": {"countries": [(c, COUNTRIES[c], n) for c, n in ranked(countries)], "cities": ranked(cities),
                "schools": ranked(schools), "country": country, "city": city, "school": school,
                "country_name": COUNTRIES.get(country, ""), "active": bool(cond)},
        "geo_keep": [(k, request.GET[k]) for k in KEEP if request.GET.get(k)],
    }
