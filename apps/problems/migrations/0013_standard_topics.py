"""Topics were free text: the AI generator and staff added Uzbek and English variants of
the same idea ("sikl", "cikl", "loop", "for") and level words ("beginner", "asosiy").
Merge them into one standard English set; tags that match nothing are dropped and
listed in the migration output. Frozen here on purpose: later edits to the topic list
happen on the staff "Mavzular" page, not by changing this file."""
import re

from django.db import migrations

TOPICS = [
    "input-output", "math", "conditionals", "loops", "strings", "arrays", "hash-table",
    "sorting", "implementation", "number-theory", "greedy", "brute-force", "binary-search",
    "two-pointers", "prefix-sums", "recursion", "dynamic-programming", "graphs", "geometry",
    "bit-manipulation", "combinatorics", "data-structures", "sql",
]

_VARIANTS = {
    "input-output": "io i-o input output print stdin kirish-chiqish kiritish-chiqarish kirish chiqish "
                    "variables ozgaruvchi ozgaruvchilar",
    "math": "matematika arifmetika arithmetic mathematics maths sum yigindi hisoblash formula formulas "
            "big-numbers big-integer bignum katta-sonlar percent percentage foiz digits raqam raqamlar "
            "sonlar numbers operators operatorlar division bolish modulo average ortacha",
    "conditionals": "if-else if else elif shart shartlar shartli-operator condition conditions branching "
                    "tarmoqlanish logic mantiq boolean switch",
    "loops": "loop for while for-loop while-loop sikl sikllar cikl tsikl tsikllar iteration takrorlash "
             "counting sanash range",
    "strings": "string satr satrlar matn text palindrome palindrom characters belgilar",
    "arrays": "array list lists royxat royxatlar massiv massivlar matrix matritsa 2d-array tuple tuples",
    "hash-table": "dict dicts dictionary dictionaries lugat lugatlar hash hashing hashmap hash-map map set "
                  "sets toplam toplamlar counter",
    "sorting": "sort saralash tartiblash sorted",
    "implementation": "real-life life hayotiy hayot bozor simulation simulyatsiya modeling amaliy practical "
                      "story word-problems matnli",
    "number-theory": "divisor divisors boluvchi boluvchilar prime primes tub tub-son tub-sonlar gcd lcm ekub "
                     "ekuk modular modular-arithmetic",
    "greedy": "ochkoz greedy-algorithm",
    "brute-force": "bruteforce brute search qidiruv complete-search full-search",
    "binary-search": "binary bin-search ikkilik-qidiruv binar-qidiruv",
    "two-pointers": "two-pointer ikki-korsatkich sliding-window",
    "prefix-sums": "prefix prefix-sum prefiks prefiks-yigindi cumulative-sum",
    "recursion": "recursive rekursiya backtracking",
    "dynamic-programming": "dp dinamik dinamik-dasturlash memoization knapsack",
    "graphs": "graph graf graflar bfs dfs shortest-path shortest-paths tree trees daraxt daraxtlar dsu "
              "union-find",
    "geometry": "geom geometric geometriya",
    "bit-manipulation": "bit bits bitmask bitmasks bitwise",
    "combinatorics": "kombinatorika permutations combinations probability ehtimollik",
    "data-structures": "data-structure stack stacks stek queue queues navbat deque heap priority-queue "
                       "linked-list segment-tree fenwick malumotlar-tuzilmasi",
    "sql": "database databases select join joins query queries malumotlar-bazasi",
}
SYNONYMS = {variant: topic for topic, variants in _VARIANTS.items() for variant in variants.split()}


def _key(name: str) -> str:
    """"Yig‘indi " -> "yigindi", "Binary Search" -> "binary-search"."""
    name = re.sub(r"[’‘ʻʼ`']", "", name.strip().lower())
    return re.sub(r"[\s_/]+", "-", name).strip("-")


def standardize(apps, schema_editor):
    Tag = apps.get_model("problems", "Tag")
    standard = {name: Tag.objects.get_or_create(name=name)[0] for name in TOPICS}
    dropped = []
    for tag in Tag.objects.exclude(name__in=TOPICS):
        key = _key(tag.name)
        target = key if key in standard else SYNONYMS.get(key)
        if target:
            standard[target].problem_set.add(*tag.problem_set.all())
        else:
            dropped.append(tag.name)
        tag.delete()
    if dropped:
        print(f"\n  Dropped topics (no standard match): {', '.join(sorted(dropped))}")


class Migration(migrations.Migration):
    dependencies = [("problems", "0012_daily_problem")]

    operations = [migrations.RunPython(standardize, migrations.RunPython.noop)]
