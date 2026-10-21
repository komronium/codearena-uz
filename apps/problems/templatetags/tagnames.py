"""Uzbek names for the topic tags. The tag's own name (an English slug) stays in the database and in URLs
(?tag=math); the pages show the Uzbek name, so a student sees "matematika", not "math"."""
from django import template
from django.utils.translation import get_language, gettext_lazy as _tl

register = template.Library()

TAG_UZ = {
    "aggregation": "agregatsiya", "arithmetic": "arifmetika", "arrays": "massivlar", "backtracking": "qaytish usuli",
    "bfs": _tl("kenglik bo‘yicha qidiruv"), "binary-search": "ikkilik qidiruv", "bit-manipulation": "bit amallari",
    "brute-force": _tl("to‘liq saralash"), "case-when": "case-when", "combinatorics": "kombinatorika", "conditionals": "shartlar",
    "data-structures": _tl("ma’lumotlar tuzilmalari"), "date-functions": "sana funksiyalari", "dfs": _tl("chuqurlik bo‘yicha qidiruv"),
    "distinct": "distinct", "divide-and-conquer": _tl("bo‘l va hukm qil"), "dynamic-programming": "dinamik dasturlash",
    "for-loop": "for sikli", "geometry": "geometriya", "graphs": "graflar", "greedy": _tl("ochko‘z algoritm"), "group-by": "group by",
    "hash-table": "xesh jadval", "having": "having", "heap": "uyum (heap)", "implementation": "simulyatsiya",
    "input-output": _tl("kiritish va chiqarish"), "join": "join", "left-join": "left join", "like": "like", "limit": "limit",
    "loops": "sikllar", "math": "matematika", "matrices": "matritsalar", "nested-loops": "ichma-ich sikllar",
    "null-values": "null qiymatlar", "number-basics": _tl("sonlar bilan ishlash"), "number-theory": "sonlar nazariyasi",
    "order-by": "order by", "prefix-sums": _tl("prefiks yig‘indilar"), "queue": "navbat", "recursion": "rekursiya",
    "segment-tree": "kesmalar daraxti", "select": "select", "shortest-paths": _tl("eng qisqa yo‘llar"),
    "sliding-window": "sirpanuvchi oyna", "sorting": "saralash", "sql": "sql", "stack": "stek",
    "string-algorithms": "satr algoritmlari", "string-functions": "satr funksiyalari", "strings": "satrlar",
    "subquery": _tl("ichki so‘rov"), "trees": "daraxtlar", "two-pointers": _tl("ikki ko‘rsatkich"), "union-find": "dsu",
    "where": "where", "while-loop": "while sikli", "window-functions": "oyna funksiyalari",
}


@register.filter
def tag_uz(name: str) -> str:
    """The tag as the page language names it: the Uzbek name, or in English the tag's own name ("binary search")."""
    if get_language() == "en":
        return name.replace("-", " ")
    return str(TAG_UZ.get(name, name))
