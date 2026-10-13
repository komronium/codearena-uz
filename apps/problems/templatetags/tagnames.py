"""Uzbek names for the topic tags. The tag's own name (an English slug) stays in the database and in URLs
(?tag=math); the pages show the Uzbek name, so a student sees "matematika", not "math"."""
from django import template

register = template.Library()

TAG_UZ = {
    "aggregation": "agregatsiya", "arithmetic": "arifmetika", "arrays": "massivlar", "backtracking": "qaytish usuli",
    "bfs": "kenglik bo‘yicha qidiruv", "binary-search": "ikkilik qidiruv", "bit-manipulation": "bit amallari",
    "brute-force": "to‘liq saralash", "case-when": "case-when", "combinatorics": "kombinatorika", "conditionals": "shartlar",
    "data-structures": "ma’lumotlar tuzilmalari", "date-functions": "sana funksiyalari", "dfs": "chuqurlik bo‘yicha qidiruv",
    "distinct": "distinct", "divide-and-conquer": "bo‘l va hukm qil", "dynamic-programming": "dinamik dasturlash",
    "for-loop": "for sikli", "geometry": "geometriya", "graphs": "graflar", "greedy": "ochko‘z algoritm", "group-by": "group by",
    "hash-table": "xesh jadval", "having": "having", "heap": "uyum (heap)", "implementation": "simulyatsiya",
    "input-output": "kiritish va chiqarish", "join": "join", "left-join": "left join", "like": "like", "limit": "limit",
    "loops": "sikllar", "math": "matematika", "matrices": "matritsalar", "nested-loops": "ichma-ich sikllar",
    "null-values": "null qiymatlar", "number-basics": "sonlar bilan ishlash", "number-theory": "sonlar nazariyasi",
    "order-by": "order by", "prefix-sums": "prefiks yig‘indilar", "queue": "navbat", "recursion": "rekursiya",
    "segment-tree": "kesmalar daraxti", "select": "select", "shortest-paths": "eng qisqa yo‘llar",
    "sliding-window": "sirpanuvchi oyna", "sorting": "saralash", "sql": "sql", "stack": "stek",
    "string-algorithms": "satr algoritmlari", "string-functions": "satr funksiyalari", "strings": "satrlar",
    "subquery": "ichki so‘rov", "trees": "daraxtlar", "two-pointers": "ikki ko‘rsatkich", "union-find": "dsu",
    "where": "where", "while-loop": "while sikli", "window-functions": "oyna funksiyalari",
}


@register.filter
def tag_uz(name: str) -> str:
    return TAG_UZ.get(name, name)
