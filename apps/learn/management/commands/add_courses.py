"""The O‘rganish path: one course per topic, in path order. A course holds every open problem that
carries any of its tags, so it fills up as problems are tagged; a course whose problems don't exist
yet still shows its theory.

Courses are matched by slug. A new course is created in full; an existing one only gets its missing
tags added and its theory filled in if empty, so staff edits survive a re-run. Missing tags are
created. The first study plans (learn.views.OLD_PLANS) are removed: their addresses redirect here.

    python manage.py add_courses [--dry-run]
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.learn.models import RESERVED_SLUGS, StudyPlan
from apps.learn.views import OLD_PLANS
from apps.problems.models import Problem, Tag
from apps.problems.skills import open_problems

from ._theory import TEXTS

S, D = StudyPlan.Stage, Problem.Difficulty


def theory(*parts: str | tuple[str, str]) -> str:
    """One topic's text as is; several, each under its own heading with theirs one level down."""
    if len(parts) == 1:
        return TEXTS[parts[0]]
    out = []
    for title, name in parts:
        lines, code = [], False
        for line in TEXTS[name].strip().splitlines():
            if line.startswith("```"):
                code = not code
            elif line.startswith("#") and not code:
                line = "#" + line
            lines.append(line)
        out.append(f"## {title}\n\n" + "\n".join(lines))
    return "\n\n".join(out) + "\n"


# slug, title, stage, level, icon, tags (space-separated), summary, theory
COURSES = [
    ("input-output", "Kiritish va chiqarish", S.BASICS, D.BEGINNER, "terminal", "input-output",
     "Kirish ma’lumotini o‘qish va javobni aniq formatda chiqarish", theory("input-output")),
    ("arithmetic", "Arifmetika", S.BASICS, D.BEGINNER, "calculator", "arithmetic",
     "Butun bo‘lish, qoldiq, formulalar va kasr sonlar", theory("arithmetic")),
    ("conditionals", "Shartlar", S.BASICS, D.BEGINNER, "git-branch", "conditionals",
     "if, elif, else: dastur qaysi yo‘ldan borishini tanlash", theory("conditionals")),
    ("for-loop", "for sikli", S.BASICS, D.BEGINNER, "repeat", "for-loop",
     "Ishni ma’lum marta takrorlash: yig‘indi, sanash, eng kattasi", theory("for-loop")),
    ("while-loop", "while sikli", S.BASICS, D.EASY, "rotate-cw", "while-loop",
     "Shart bajarilguncha takrorlash: raqamlar, «necha yilda?»", theory("while-loop")),
    ("nested-loops", "Ichma-ich sikllar", S.BASICS, D.EASY, "repeat-2", "nested-loops",
     "Sikl ichida sikl: jadvallar, juftliklar, naqshlar", theory("nested-loops")),
    ("number-basics", "Sonlar bilan ishlash", S.BASICS, D.EASY, "hash", "number-basics",
     "Bo‘luvchilar, tub sonlar, EKUB/EKUK va sanoq sistemalari", theory("number-basics")),

    ("arrays", "Ro‘yxatlar", S.PYTHON, D.EASY, "brackets", "arrays",
     "Ro‘yxatni bir o‘tishda aylanib, kerakli qiymatni topish", theory("arrays")),
    ("strings", "Satrlar", S.PYTHON, D.EASY, "type", "strings",
     "Belgilar va so‘zlar: kesish, teskari o‘qish, join", theory("strings")),
    ("matrices", "Matritsalar", S.PYTHON, D.EASY, "grid-3x3", "matrices",
     "Ikki o‘lchamli jadval: qatorlar, ustunlar, qo‘shni kataklar", theory("matrices")),
    ("dictionaries", "Lug‘at va to‘plam", S.PYTHON, D.EASY, "book-key", "hash-table",
     "dict, set va kortej: tez qidirish va sanash",
     theory(("Lug‘at va to‘plam", "hash-table"), ("Kortej va to‘plam amallari", "tuples-sets"))),
    ("functions", "Funksiyalar va rekursiya", S.PYTHON, D.MEDIUM, "square-function", "recursion",
     "Kodni funksiyalarga bo‘lish; funksiya o‘zini chaqirganda",
     theory(("Funksiyalar", "functions"), ("Rekursiya", "recursion"))),

    ("complexity", "Murakkablik", S.ALGORITHMS, D.MEDIUM, "gauge", "",
     "Yechim vaqtga sig‘adimi? Kirish hajmiga qarab algoritm tanlash",
     theory(("Murakkablik", "complexity"), ("Ehtiyotkor bajarish", "implementation"))),
    ("sorting", "Saralash", S.ALGORITHMS, D.MEDIUM, "arrow-down-up", "sorting divide-and-conquer",
     "sort, kalit bo‘yicha saralash va «bo‘l va hukmronlik qil»",
     theory(("Saralash", "sorting"), ("Bo‘l va hukmronlik qil", "divide-and-conquer"))),
    ("binary-search", "Ikkilik qidiruv", S.ALGORITHMS, D.MEDIUM, "search", "binary-search",
     "Saralangan ma’lumotda va javob bo‘yicha ikkilik qidiruv", theory("binary-search")),

    ("prefix-sums", "Prefiks yig‘indilar", S.TECHNIQUES, D.MEDIUM, "sigma", "prefix-sums",
     "Istalgan oraliq yig‘indisini O(1) da topish", theory("prefix-sums")),
    ("two-pointers", "Ikki ko‘rsatkich", S.TECHNIQUES, D.MEDIUM, "arrow-left-right", "two-pointers",
     "Ikki indeksni bir-biriga qarab yoki bir tomonga yuritish", theory("two-pointers")),
    ("sliding-window", "Sirpanuvchi oyna", S.TECHNIQUES, D.MEDIUM, "move-horizontal", "sliding-window",
     "Ketma-ket oraliqni bir o‘tishda tekshirish", theory("sliding-window")),
    ("greedy", "Ochko‘z algoritmlar", S.TECHNIQUES, D.MEDIUM, "coins", "greedy",
     "Har qadamda eng yaxshi tanlov va u qachon to‘g‘ri bo‘lishi", theory("greedy")),
    ("bit-manipulation", "Bit amallari", S.TECHNIQUES, D.MEDIUM, "binary", "bit-manipulation",
     "&, |, ^, siljitish va XOR xossalari", theory("bit-manipulation")),
    ("backtracking", "To‘liq qidiruv va backtracking", S.TECHNIQUES, D.HARD, "undo-2", "backtracking brute-force",
     "Barcha variantlarni tekshirish va keraksiz shoxlarni kesish",
     theory(("To‘liq qidiruv", "brute-force"), ("Backtracking", "backtracking"))),

    ("stack-queue", "Stek va navbat", S.STRUCTURES, D.MEDIUM, "layers", "stack queue",
     "Stek, navbat va deque: qavslar, monoton stek, BFS",
     theory(("Stek", "stack"), ("Navbat", "queue"), ("Bog‘langan ro‘yxat", "linked-list"))),
    ("heap", "Ustuvor navbat", S.STRUCTURES, D.MEDIUM, "pyramid", "heap",
     "heapq: eng kichik elementni tez olish", theory("heap")),

    ("number-theory", "Sonlar nazariyasi", S.MATH, D.HARD, "percent", "number-theory",
     "Eratosfen g‘alviri, modul bo‘yicha arifmetika, tez daraja", theory("number-theory")),
    ("combinatorics", "Kombinatorika", S.MATH, D.HARD, "dices", "combinatorics",
     "Nechta usul bor? Kombinatsiyalar, o‘rin almashtirishlar, juftliklar", theory("combinatorics")),

    ("dp-intro", "Dinamik dasturlash", S.DP, D.HARD, "brain", "dynamic-programming",
     "Katta masalani kichik masalalar javobidan yig‘ish", theory("dynamic-programming")),

    ("graph-traversal", "Graflar: DFS va BFS", S.GRAPHS, D.HARD, "network", "bfs dfs",
     "Grafni aylanib chiqish: BFS, DFS va topologik saralash",
     theory(("Graf", "graphs"), ("BFS", "bfs"), ("DFS", "dfs"), ("Topologik saralash", "topological-sort"))),
    ("shortest-paths", "Eng qisqa yo‘llar", S.GRAPHS, D.HARD, "route", "shortest-paths",
     "Dijkstra, Bellman–Ford va Floyd–Warshall", theory("shortest-paths")),
    ("dsu-mst", "DSU va karkas daraxt", S.GRAPHS, D.HARD, "git-merge", "union-find",
     "Birlashtiriladigan to‘plamlar va minimal karkas daraxt", theory("union-find")),
    ("trees", "Daraxtlar", S.GRAPHS, D.HARD, "list-tree", "trees",
     "Ildiz, chuqurlik, qism daraxt va diametr", theory("trees")),

    ("range-queries", "Oraliq so‘rovlar", S.ADVANCED, D.HARD, "ruler", "segment-tree",
     "Segmentlar daraxti: oraliqda so‘rov va o‘zgartirish", theory("segment-tree")),
    ("string-algorithms", "Satr algoritmlari", S.ADVANCED, D.HARD, "text-search", "string-algorithms",
     "Prefiks-funksiya, Z-funksiya va satr hashi", theory("string-algorithms")),
    ("geometry", "Geometriya", S.ADVANCED, D.HARD, "shapes", "geometry",
     "Masofa, yuza, vektor ko‘paytma va aniqlik", theory("geometry")),

    ("sql-select", "SELECT va WHERE", S.SQL, D.BEGINNER, "database", "select where distinct like null-values",
     "Kerakli ustun va qatorlarni olish: SELECT, WHERE, DISTINCT, LIKE, NULL",
     theory(("SQL so‘rovi", "sql"), ("SELECT", "select"), ("WHERE", "where"), ("DISTINCT", "distinct"),
            ("LIKE", "like"), ("NULL", "null-values"))),
    ("sql-sorting", "Saralash va ifodalar", S.SQL, D.BEGINNER, "arrow-down-a-z",
     "order-by limit case-when string-functions",
     "ORDER BY, LIMIT, CASE va satr funksiyalari",
     theory(("ORDER BY", "order-by"), ("LIMIT", "limit"), ("CASE", "case-when"),
            ("Satr funksiyalari", "string-functions"))),
    ("sql-grouping", "Guruhlash", S.SQL, D.EASY, "group", "aggregation group-by having date-functions",
     "COUNT, SUM, GROUP BY, HAVING va sanalar",
     theory(("Agregat funksiyalar", "aggregation"), ("GROUP BY", "group-by"), ("HAVING", "having"),
            ("Sanalar", "date-functions"))),
    ("sql-join", "JOIN", S.SQL, D.MEDIUM, "combine", "join left-join",
     "Jadvallarni JOIN va LEFT JOIN bilan bog‘lash",
     theory(("JOIN", "join"), ("LEFT JOIN", "left-join"))),
    ("sql-advanced", "Ichki so‘rov va oyna funksiyalari", S.SQL, D.HARD, "table", "subquery window-functions",
     "So‘rov ichida so‘rov, ROW_NUMBER va RANK",
     theory(("Ichki so‘rov", "subquery"), ("Oyna funksiyalari", "window-functions"))),
]


class Command(BaseCommand):
    help = "Create the O‘rganish courses (one per topic) and remove the first study plans."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show what would change, write nothing.")

    def handle(self, *args, dry_run=False, **options):
        with transaction.atomic():
            created = 0
            for order, (slug, title, stage, level, icon, tag_names, summary, text) in enumerate(COURSES, 1):
                if slug in RESERVED_SLUGS:
                    raise CommandError(f"{slug}: bu slug band")
                kind = Tag.Kind.SQL if stage == S.SQL else Tag.Kind.CODE
                tags = [Tag.objects.get_or_create(name=n, defaults={"kind": kind})[0] for n in tag_names.split()]
                course, new = StudyPlan.objects.get_or_create(slug=slug, defaults={
                    "title": title, "stage": stage, "level": level, "icon": icon, "summary": summary,
                    "theory_md": text, "order": order, "is_public": True})
                if not new and not course.theory_md.strip():
                    course.theory_md = text
                    course.save(update_fields=["theory_md"])
                course.tags.add(*tags)
                created += new
            removed = StudyPlan.objects.filter(slug__in=OLD_PLANS).delete()[1].get("learn.StudyPlan", 0)
            self.stdout.write(f"kurslar: {created} ta yangi, {len(COURSES) - created} ta bor edi; "
                              f"eski rejalar o‘chirildi: {removed}")
            course_tags = Tag.objects.filter(courses__isnull=False)
            orphans = open_problems().exclude(tags__in=course_tags).order_by("kind", "slug")
            if orphans:
                self.stdout.write(f"hech bir kursda yo‘q masalalar ({len(orphans)}): "
                                  + ", ".join(p.slug for p in orphans))
            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write("dry-run: hech narsa saqlanmadi")
