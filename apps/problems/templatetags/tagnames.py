"""Uzbek names for the topic tags. The tag's own name (an English slug) stays in the database and in URLs
(?tag=math); the pages show the Uzbek name, so a student sees "matematika", not "math"."""
from django import template
from django.utils.translation import get_language, gettext_lazy as _tl

register = template.Library()

TAG_UZ = {
    "aggregation": _tl("agregatsiya"), "arithmetic": _tl("arifmetika"), "arrays": _tl("massivlar"), "backtracking": _tl("qaytish usuli"),
    "bfs": _tl("kenglik bo‘yicha qidiruv"), "binary-search": _tl("ikkilik qidiruv"), "bit-manipulation": _tl("bit amallari"),
    "brute-force": _tl("to‘liq saralash"), "case-when": _tl("case-when"), "combinatorics": _tl("kombinatorika"), "conditionals": _tl("shartlar"),
    "data-structures": _tl("ma’lumotlar tuzilmalari"), "date-functions": _tl("sana funksiyalari"), "dfs": _tl("chuqurlik bo‘yicha qidiruv"),
    "distinct": _tl("distinct"), "divide-and-conquer": _tl("bo‘l va hukm qil"), "dynamic-programming": _tl("dinamik dasturlash"),
    "for-loop": _tl("for sikli"), "geometry": _tl("geometriya"), "graphs": _tl("graflar"), "greedy": _tl("ochko‘z algoritm"), "group-by": _tl("group by"),
    "hash-table": _tl("xesh jadval"), "having": _tl("having"), "heap": _tl("uyum (heap)"), "implementation": _tl("simulyatsiya"),
    "input-output": _tl("kiritish va chiqarish"), "join": _tl("join"), "left-join": _tl("left join"), "like": _tl("like"), "limit": _tl("limit"),
    "loops": _tl("sikllar"), "math": _tl("matematika"), "matrices": _tl("matritsalar"), "nested-loops": _tl("ichma-ich sikllar"),
    "null-values": _tl("null qiymatlar"), "number-basics": _tl("sonlar bilan ishlash"), "number-theory": _tl("sonlar nazariyasi"),
    "order-by": _tl("order by"), "prefix-sums": _tl("prefiks yig‘indilar"), "queue": _tl("navbat"), "recursion": _tl("rekursiya"),
    "segment-tree": _tl("kesmalar daraxti"), "select": _tl("select"), "shortest-paths": _tl("eng qisqa yo‘llar"),
    "sliding-window": _tl("sirpanuvchi oyna"), "sorting": _tl("saralash"), "sql": _tl("sql"), "stack": _tl("stek"),
    "string-algorithms": _tl("satr algoritmlari"), "string-functions": _tl("satr funksiyalari"), "strings": _tl("satrlar"),
    "subquery": _tl("ichki so‘rov"), "trees": _tl("daraxtlar"), "two-pointers": _tl("ikki ko‘rsatkich"), "union-find": _tl("dsu"),
    "where": _tl("where"), "while-loop": _tl("while sikli"), "window-functions": _tl("oyna funksiyalari"),
}


@register.filter
def tag_uz(name: str) -> str:
    """The tag as the page language names it: the Uzbek name, or in English the tag's own name ("binary search")."""
    if get_language() == "en":
        return name.replace("-", " ")
    return str(TAG_UZ.get(name, name))
