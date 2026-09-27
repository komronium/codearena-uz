"""Weekend Contest #1: ten hidden problems (3 Beginner, 3 Easy, 3 Medium, 1 Hard) on input/output,
conditions and loops, attached to the existing contest as A..J. None repeats a problem already on
the portal (the seed_problems / seed_story_problems sets).

Every expected output is computed here by a reference solution, never typed by hand, so a test
can't be wrong. Safe to re-run: problems that already exist (by slug) are reused, not duplicated.

    python manage.py add_weekend_contest_1 [--contest "Weekend Contest #1"] [--author admin] [--dry-run]
"""
import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.contests.models import Contest, ContestProblem
from apps.problems.models import Problem, Tag, TestCase

POINTS = {"beginner": 100, "easy": 200, "medium": 300, "hard": 500}


def _lines(*rows) -> str:
    return "\n".join(str(r) for r in rows) + "\n"


# ---- A. Beginner: yotoqxona to'lovi ------------------------------------------------------
def a_solve(inp):
    n, p = map(int, inp.split())
    return _lines(n * p)


def a_tests(rng):
    tests = ["3 450000", "12 1000000", "1 1", "1 1000000", "12 1"]
    tests += [f"{rng.randint(1, 12)} {rng.randint(1, 1_000_000)}" for _ in range(17)]
    return tests


# ---- B. Beginner: avtobuslar -------------------------------------------------------------
def b_solve(inp):
    n, k = map(int, inp.split())
    return _lines((n + k - 1) // k)


def b_tests(rng):
    tests = ["100 45", "90 45", "1 1", "1 50", "50 50", "51 50", "1000000000 1", "1000000000 1000000000", "7 3"]
    tests += [f"{rng.randint(1, 10**9)} {rng.randint(1, rng.choice([10, 1000, 10**9]))}" for _ in range(13)]
    return tests


# ---- C. Beginner: fasl -------------------------------------------------------------------
def c_solve(inp):
    m = int(inp)
    return _lines("Qish" if m in (12, 1, 2) else "Bahor" if m <= 5 else "Yoz" if m <= 8 else "Kuz")


def c_tests(rng):
    return ["4", "12"] + [str(m) for m in range(1, 13)] + [str(rng.randint(1, 12)) for _ in range(8)]


# ---- D. Easy: ko'paytirish jadvali -------------------------------------------------------
def d_solve(inp):
    n = int(inp)
    return _lines(*(f"{n} x {i} = {n * i}" for i in range(1, 11)))


def d_tests(rng):
    return ["7", "1"] + [str(x) for x in (2, 9, 10, 100, 12345, 1000000)] + \
        [str(rng.randint(1, 10**6)) for _ in range(14)]


# ---- E. Easy: omonat ---------------------------------------------------------------------
def e_solve(inp):
    s, p, t = map(int, inp.split())
    years = 0
    while s < t:
        s += s * p // 100
        years += 1
    return _lines(years)


def e_tests(rng):
    tests = ["1000 10 1500", "5000 20 5000", "100 1 1000000000", "100 100 1000000000", "1000000000 50 1000000000",
             "100 1 101", "999 1 1000", "100 50 151"]
    for _ in range(14):
        s = rng.randint(100, 10**6)
        tests.append(f"{s} {rng.randint(1, 100)} {rng.randint(s, 10**9)}")
    return tests


# ---- F. Easy: sport rejimi ---------------------------------------------------------------
def f_solve(inp):
    a, d, n = map(int, inp.split())
    return _lines(sum(a + d * i for i in range(n)))


def f_tests(rng):
    tests = ["10 5 3", "20 0 7", "1 1 1", "1 0 1", "100 100 1000", "1 1 1000", "50 0 1000"]
    tests += [f"{rng.randint(1, 100)} {rng.randint(0, 100)} {rng.randint(1, 1000)}" for _ in range(15)]
    return tests


# ---- G. Medium: ikkilik sanoq tizimi -----------------------------------------------------
def g_solve(inp):
    return _lines(format(int(inp), "b"))


def g_tests(rng):
    tests = ["13", "8", "0", "1", "2", "1023", "1024", "1000000000"]
    tests += [str(rng.randint(0, 10**9)) for _ in range(14)]
    return tests


# ---- H. Medium: palindrom sonlar ---------------------------------------------------------
def h_solve(inp):
    a, b = map(int, inp.split())
    return _lines(sum(1 for x in range(a, b + 1) if str(x) == str(x)[::-1]))


def h_tests(rng):
    tests = ["1 20", "100 200", "1 1", "10 10", "11 11", "1 1000000", "999990 1000000", "123 123"]
    for _ in range(14):
        a = rng.randint(1, 1_000_000)
        tests.append(f"{a} {rng.randint(a, min(1_000_000, a + rng.choice([10, 1000, 500_000])))}")
    return tests


# ---- I. Medium: eng ko'p olingan baho ---------------------------------------------------
def i_solve(inp):
    parts = inp.split()
    n = int(parts[0])
    grades = list(map(int, parts[1:1 + n]))
    best = max((2, 3, 4, 5), key=lambda g: (grades.count(g), g))
    return _lines(f"{best} {grades.count(best)}")


def i_tests(rng):
    def case(arr):
        return f"{len(arr)}\n{' '.join(map(str, arr))}"
    tests = [case([5, 4, 4, 3, 5, 4]), case([3, 5, 3, 5]), case([2]), case([5] * 10), case([2, 3, 4, 5]),
             case([2, 2, 3, 3, 4, 4, 5, 5]), case([4] * 1000)]
    for _ in range(15):
        n = rng.randint(1, 1000)
        tests.append(case([rng.choice((2, 3, 4, 5)) for _ in range(n)]))
    return tests


# ---- J. Hard: tub ko'paytuvchilar --------------------------------------------------------
def j_solve(inp):
    n, out, d = int(inp), [], 2
    while d * d <= n:
        while n % d == 0:
            out.append(d)
            n //= d
        d += 1
    if n > 1:
        out.append(n)
    return _lines(" ".join(map(str, out)))


def j_tests(rng):
    tests = ["60", "13", "2", "4", "1024", "999999937", "999999938", "1000000000", "735134400",
             "999962000357", "600851475143", "1000000007"]
    tests = [t for t in tests if 2 <= int(t) <= 10**12]
    tests += [str(rng.randint(2, 10**12)) for _ in range(22 - len(tests))]
    return tests


PROBLEMS = [
    {
        "slug": "wc1-yotoqxona-tolovi", "title": "Yotoqxona to‘lovi", "difficulty": "beginner",
        "tags": ["input-output"], "solve": a_solve, "tests": a_tests, "samples": 2,
        "statement": "Talaba yotoqxonada $n$ oy yashaydi. Bir oylik to‘lov $p$ so‘m. Jami qancha to‘lashini hisoblang.",
        "input": "Bitta qatorda ikkita butun son: $n$ va $p$ ($1 \\le n \\le 12$, $1 \\le p \\le 10^6$).",
        "output": "Jami to‘lov summasini chiqaring.",
    },
    {
        "slug": "wc1-avtobuslar", "title": "Ekskursiya avtobuslari", "difficulty": "beginner",
        "tags": ["input-output", "conditionals"], "solve": b_solve, "tests": b_tests, "samples": 2,
        "statement": ("Ekskursiyaga $n$ ta talaba boradi. Har bir avtobusga $k$ ta odam sig‘adi. "
                      "Hamma talabani olib ketish uchun kamida nechta avtobus kerak?"),
        "input": "Bitta qatorda ikkita butun son: $n$ va $k$ ($1 \\le n, k \\le 10^9$).",
        "output": "Kerakli avtobuslar sonini chiqaring.",
    },
    {
        "slug": "wc1-fasl", "title": "Qaysi fasl?", "difficulty": "beginner",
        "tags": ["conditionals"], "solve": c_solve, "tests": c_tests, "samples": 2,
        "statement": ("Oy raqami $m$ berilgan (1 — yanvar, 12 — dekabr). Qaysi fasl ekanini aniqlang:\n\n"
                      "- 12, 1, 2 — `Qish`\n- 3, 4, 5 — `Bahor`\n- 6, 7, 8 — `Yoz`\n- 9, 10, 11 — `Kuz`"),
        "input": "Bitta butun son $m$ ($1 \\le m \\le 12$).",
        "output": "Fasl nomini chiqaring: `Qish`, `Bahor`, `Yoz` yoki `Kuz`.",
    },
    {
        "slug": "wc1-kopaytirish-jadvali", "title": "Ko‘paytirish jadvali", "difficulty": "easy",
        "tags": ["loops"], "solve": d_solve, "tests": d_tests, "samples": 2,
        "statement": "Son $n$ berilgan. Uning 1 dan 10 gacha ko‘paytirish jadvalini chiqaring.",
        "input": "Bitta butun son $n$ ($1 \\le n \\le 10^6$).",
        "output": ("10 ta qator: $i$-qatorda `n x i = natija` ko‘rinishida (belgilar orasida bittadan probel). "
                   "Masalan: `7 x 3 = 21`."),
    },
    {
        "slug": "wc1-omonat", "title": "Omonat", "difficulty": "easy",
        "tags": ["loops"], "solve": e_solve, "tests": e_tests, "samples": 2,
        "statement": ("Bankka $s$ so‘m qo‘yildi. Har yil oxirida omonatga uning $p$ foizi qo‘shiladi; "
                      "qo‘shiladigan summa butun so‘mgacha pastga yaxlitlanadi ($s \\cdot p$ ni 100 ga butun bo‘lish). "
                      "Necha yildan keyin omonat kamida $t$ so‘m bo‘ladi?"),
        "input": ("Bitta qatorda uchta butun son: $s$, $p$, $t$ "
                  "($100 \\le s \\le t \\le 10^9$, $1 \\le p \\le 100$)."),
        "output": "Yillar sonini chiqaring (boshidanoq $s \\ge t$ bo‘lsa — 0).",
    },
    {
        "slug": "wc1-sport-rejimi", "title": "Sport rejimi", "difficulty": "easy",
        "tags": ["loops"], "solve": f_solve, "tests": f_tests, "samples": 2,
        "statement": ("Talaba birinchi kuni $a$ marta turnikka tortildi. Har keyingi kun oldingisidan $d$ marta "
                      "ko‘proq tortiladi. $n$ kunda jami necha marta tortiladi?"),
        "input": ("Bitta qatorda uchta butun son: $a$, $d$, $n$ "
                  "($1 \\le a \\le 100$, $0 \\le d \\le 100$, $1 \\le n \\le 1000$)."),
        "output": "Jami sonni chiqaring.",
    },
    {
        "slug": "wc1-ikkilik-son", "title": "Ikkilik sanoq tizimi", "difficulty": "medium",
        "tags": ["loops"], "solve": g_solve, "tests": g_tests, "samples": 2,
        "statement": ("Kompyuter sonlarni ikkilik tizimda saqlaydi: masalan, $13 = 1101_2$ "
                      "($1 \\cdot 8 + 1 \\cdot 4 + 0 \\cdot 2 + 1 \\cdot 1$). "
                      "Berilgan $n$ sonni ikkilik tizimda yozing.\n\n"
                      "Maslahat: sonni 2 ga bo‘lib, qoldiqlarni yig‘ing — ular teskari tartibda javobni beradi."),
        "input": "Bitta butun son $n$ ($0 \\le n \\le 10^9$).",
        "output": "$n$ ning ikkilik yozuvini boshida ortiqcha nolsiz chiqaring ($n = 0$ uchun `0`).",
    },
    {
        "slug": "wc1-palindrom-sonlar", "title": "Palindrom sonlar", "difficulty": "medium", "tl_ms": 2000,
        "tags": ["loops", "conditionals"], "solve": h_solve, "tests": h_tests, "samples": 2,
        "statement": ("Palindrom son — chapdan ham, o‘ngdan ham bir xil o‘qiladigan son (7, 44, 121, 1331). "
                      "$[a, b]$ oralig‘ida (ikkala chegara ham kiradi) nechta palindrom son bor?"),
        "input": "Bitta qatorda ikkita butun son $a$ va $b$ ($1 \\le a \\le b \\le 10^6$).",
        "output": "Palindrom sonlar sonini chiqaring.",
    },
    {
        "slug": "wc1-kop-olingan-baho", "title": "Eng ko‘p olingan baho", "difficulty": "medium",
        "tags": ["loops", "conditionals"], "solve": i_solve, "tests": i_tests, "samples": 2,
        "statement": ("Guruhdagi $n$ ta talabaning imtihon baholari berilgan (2, 3, 4 yoki 5). "
                      "Qaysi baho eng ko‘p olingan va necha marta? Bir nechta baho teng bo‘lsa, kattasini tanlang."),
        "input": ("Birinchi qatorda $n$ ($1 \\le n \\le 1000$). Ikkinchi qatorda $n$ ta baho "
                  "(har biri 2, 3, 4 yoki 5)."),
        "output": "Bitta qatorda probel bilan: baho va u necha marta olingani.",
    },
    {
        "slug": "wc1-tub-kopaytuvchilar", "title": "Tub ko‘paytuvchilar", "difficulty": "hard", "tl_ms": 2000,
        "tags": ["loops"], "solve": j_solve, "tests": j_tests, "samples": 2,
        "statement": ("Har bir sonni tub sonlar ko‘paytmasi ko‘rinishida yozish mumkin: "
                      "$60 = 2 \\cdot 2 \\cdot 3 \\cdot 5$. Berilgan $n$ sonni tub ko‘paytuvchilarga ajrating.\n\n"
                      "Diqqat: $n$ katta bo‘lishi mumkin — $n$ gacha sikl vaqtga sig‘maydi."),
        "input": "Bitta butun son $n$ ($2 \\le n \\le 10^{12}$).",
        "output": "Tub ko‘paytuvchilarni o‘sish tartibida, probel bilan ajratib chiqaring (takrorlanganlari ham).",
    },
]


class Command(BaseCommand):
    help = "Adds the 10 Weekend Contest #1 problems (hidden) and attaches them to the contest as A..J."

    def add_arguments(self, parser):
        parser.add_argument("--contest", default="Weekend Contest #1", help="Existing contest title")
        parser.add_argument("--author", default=None, help="Author username (default: first superuser)")
        parser.add_argument("--dry-run", action="store_true", help="Check everything, change nothing")
        parser.add_argument("--force", action="store_true", help="Attach even if the contest has started")

    def handle(self, *args, **opts):
        contest = Contest.objects.filter(title__iexact=opts["contest"]).first()
        if contest is None:
            titles = ", ".join(f"«{t}»" for t in Contest.objects.order_by("-start").values_list("title", flat=True)[:10])
            raise CommandError(f"«{opts['contest']}» musobaqasi topilmadi. Bor musobaqalar: {titles or '—'}. "
                               "Avval Boshqaruv → Musobaqalar'da yarating yoki --contest bilan nomini bering.")
        if contest.start <= timezone.now() and not opts["force"]:
            raise CommandError("Musobaqa allaqachon boshlangan. Baribir ulash uchun --force qo'shing.")

        User = get_user_model()
        author = (User.objects.filter(username=opts["author"]).first() if opts["author"]
                  else User.objects.filter(is_superuser=True).order_by("pk").first())
        if author is None:
            raise CommandError("Muallif topilmadi — --author bilan mavjud login bering.")

        with transaction.atomic():
            self._drop_old(contest)
            taken = set(contest.contest_problems.values_list("label", flat=True))
            for i, spec in enumerate(PROBLEMS):
                label = "ABCDEFGHIJ"[i]
                self._add(contest, spec, label, i, author, taken)
            if opts["dry_run"]:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("Dry run — hech narsa saqlanmadi."))
                return
        self.stdout.write(self.style.SUCCESS(
            f"Tayyor: «{contest.title}» da {contest.contest_problems.count()} ta masala. "
            "Masalalar yashirin; musobaqa tugagach Boshqaruv → Musobaqalar → «Masalalarni ochish»."))

    def _drop_old(self, contest):
        """An earlier version of this set may be attached already: take off the wc1-* problems that
        are no longer in it, and delete them when nobody has submitted to them."""
        keep = {spec["slug"] for spec in PROBLEMS}
        old = Problem.objects.filter(slug__startswith="wc1-", is_public=False).exclude(slug__in=keep)
        for problem in old:
            ContestProblem.objects.filter(contest=contest, problem=problem).delete()
            if problem.submissions.exists():
                self.stdout.write(f"  − {problem.title}: musobaqadan olindi (yechimlari bor — o'chirilmadi)")
            else:
                problem.delete()
                self.stdout.write(f"  − {problem.title}: eski versiya o'chirildi")

    def _add(self, contest, spec, label, order, author, taken):
        rng = random.Random(spec["slug"])  # same tests on every run
        problem = Problem.objects.filter(slug=spec["slug"]).first()
        if problem is None:
            problem = Problem.objects.create(
                slug=spec["slug"], title=spec["title"], statement_md=spec["statement"],
                input_md=spec["input"], output_md=spec["output"], difficulty=spec["difficulty"],
                tl_ms=spec.get("tl_ms", 1000), ml_mb=256, points=POINTS[spec["difficulty"]],
                is_public=False, status=Problem.Status.APPROVED, author=author,
            )
            for name in spec["tags"]:
                problem.tags.add(Tag.objects.get_or_create(name=name)[0])
            inputs = spec["tests"](rng)
            assert len(inputs) >= 20, spec["slug"]
            TestCase.objects.bulk_create(
                TestCase(problem=problem, input=inp.rstrip("\n") + "\n", expected=spec["solve"](inp),
                         is_sample=k < spec["samples"], order=k)
                for k, inp in enumerate(inputs))
            note = f"yaratildi, {len(inputs)} ta test"
        else:
            note = "avvaldan bor — qayta ishlatildi"

        if contest.contest_problems.filter(problem=problem).exists():
            self.stdout.write(f"  {label}. {problem.title}: {note}; musobaqada allaqachon bor")
            return
        if label in taken:
            raise CommandError(f"Musobaqada {label} yorlig'i band. Avval musobaqadagi masalalarni tozalang.")
        ContestProblem.objects.create(contest=contest, problem=problem, label=label, order=order,
                                      points=POINTS[spec["difficulty"]])
        self.stdout.write(f"  {label}. {problem.title} ({problem.get_difficulty_display()}, "
                          f"{POINTS[spec['difficulty']]} ball): {note}")
