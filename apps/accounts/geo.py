"""The boards' place filters: country, then city, then school, each offering only what people on the board
have (with how many), so no choice leads to an empty table."""

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
    cities = Counter(city for _, city, _ in in_country if city)
    city = request.GET.get("city", "")
    city = city if city in cities else ""
    in_city = [r for r in in_country if r[1] == city] if city else in_country
    schools = Counter(s for _, _, s in in_city if s)
    school = request.GET.get("school", "")
    school = school if school in schools else ""

    def ranked(counter):
        return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))

    cond = {k: v for k, v in (("country", country), ("location", city), ("school", school)) if v}
    return cond, {
        "geo": {"countries": [(c, COUNTRIES[c], n) for c, n in ranked(countries)], "cities": ranked(cities),
                "schools": ranked(schools), "country": country, "city": city, "school": school,
                "country_name": COUNTRIES.get(country, ""), "active": bool(cond)},
        "geo_keep": [(k, request.GET[k]) for k in KEEP if request.GET.get(k)],
    }
