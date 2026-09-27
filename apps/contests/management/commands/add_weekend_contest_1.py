"""Weekend Contest #1: ten hidden problems (3 Beginner, 3 Easy, 3 Medium, 1 Hard) on input/output,
conditions and loops, attached to the existing contest as A..J.

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


# ---- B. Beginner: juftmi yoki toqmi ------------------------------------------------------
def b_solve(inp):
    return _lines("JUFT" if int(inp) % 2 == 0 else "TOQ")


def b_tests(rng):
    tests = ["14", "7", "0", "1", "2", "1000000000", "999999999"]
    tests += [str(rng.randint(0, 10**9)) for _ in range(15)]
    return tests


# ---- C. Beginner: imtihon bahosi ---------------------------------------------------------
def c_solve(inp):
    s = int(inp)
    return _lines(5 if s >= 86 else 4 if s >= 71 else 3 if s >= 56 else 2)


def c_tests(rng):
    tests = ["92", "60", "0", "100", "86", "85", "71", "70", "56", "55", "1", "99"]
    tests += [str(rng.randint(0, 100)) for _ in range(10)]
    return tests


# ---- D. Easy: juft sonlar yig'indisi ------------------------------------------------------
def d_solve(inp):
    n = int(inp)
    return _lines(sum(range(2, n + 1, 2)))


def d_tests(rng):
    tests = ["10", "7", "1", "2", "3", "10000", "9999"]
    tests += [str(rng.randint(1, 10_000)) for _ in range(15)]
    return tests


# ---- E. Easy: eng katta va eng kichik harorat -------------------------------------------
def e_solve(inp):
    parts = inp.split()
    n = int(parts[0])
    a = list(map(int, parts[1:1 + n]))
    return _lines(f"{max(a)} {min(a)}")


def e_tests(rng):
    def case(arr):
        return f"{len(arr)}\n{' '.join(map(str, arr))}"
    tests = [case([3, -5, 12, 0, 7]), case([-2, -8, -1]), case([42]), case([5, 5, 5, 5]),
             case([-100, 100]), case([100] * 3 + [-100])]
    for _ in range(16):
        n = rng.randint(1, 1000)
        tests.append(case([rng.randint(-100, 100) for _ in range(n)]))
    return tests


# ---- F. Easy: raqamlar yig'indisi ---------------------------------------------------------
def f_solve(inp):
    return _lines(sum(int(ch) for ch in inp.strip()))


def f_tests(rng):
    tests = ["2026", "9", "0", "10", "999999999999999999", "1000000000000000000", "123456789"]
    tests += [str(rng.randint(0, 10**18)) for _ in range(15)]
    return tests


# ---- G. Medium: tub sonlar ---------------------------------------------------------------
_SIEVE = None


def _primes_upto(limit=1_000_000):
    global _SIEVE
    if _SIEVE is None:
        s = bytearray([1]) * (limit + 1)
        s[0] = s[1] = 0
        for i in range(2, int(limit ** 0.5) + 1):
            if s[i]:
                s[i * i::i] = bytearray(len(s[i * i::i]))
        prefix, c = [0] * (limit + 1), 0
        for i in range(limit + 1):
            c += s[i]
            prefix[i] = c
        _SIEVE = prefix
    return _SIEVE


def g_solve(inp):
    return _lines(_primes_upto()[int(inp)])


def g_tests(rng):
    tests = ["10", "30", "1", "2", "3", "100", "1000000", "999983", "999982"]
    tests += [str(rng.randint(1, 1_000_000)) for _ in range(13)]
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


# ---- I. Medium: eng uzun o'sish ----------------------------------------------------------
def i_solve(inp):
    parts = inp.split()
    n = int(parts[0])
    a = list(map(int, parts[1:1 + n]))
    best = cur = 1
    for i in range(1, n):
        cur = cur + 1 if a[i] > a[i - 1] else 1
        best = max(best, cur)
    return _lines(best)


def i_tests(rng):
    def case(arr):
        return f"{len(arr)}\n{' '.join(map(str, arr))}"
    tests = [case([3, 5, 7, 2, 4, 6, 8, 1]), case([5, 5, 5]), case([7]), case([1, 2]), case([2, 1]),
             case(list(range(1, 200_001))), case(list(range(200_000, 0, -1))), case([1, 2, 2, 3, 4])]
    for _ in range(14):
        n = rng.randint(1, 200_000)
        hi = rng.choice([3, 100, 10**9])
        tests.append(case([rng.randint(1, hi) for _ in range(n)]))
    return tests


# ---- J. Hard: bo'luvchilar soni yig'indisi ------------------------------------------------
def j_solve(inp):
    n = int(inp)
    r = int(n ** 0.5)
    while r * r > n:
        r -= 1
    while (r + 1) * (r + 1) <= n:
        r += 1
    return _lines(2 * sum(n // i for i in range(1, r + 1)) - r * r)


def j_tests(rng):
    tests = ["5", "10", "1", "2", "3", "4", "1000000000000", "999999999999", "1000000", "999966000289"]
    tests += [str(rng.randint(1, 10**12)) for _ in range(12)]
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
        "slug": "wc1-juftmi-toqmi", "title": "Juftmi yoki toqmi?", "difficulty": "beginner",
        "tags": ["input-output", "conditionals"], "solve": b_solve, "tests": b_tests, "samples": 2,
        "statement": "Butun son $n$ berilgan. U juft bo‘lsa `JUFT`, toq bo‘lsa `TOQ` so‘zini chiqaring.",
        "input": "Bitta butun son $n$ ($0 \\le n \\le 10^9$).",
        "output": "`JUFT` yoki `TOQ` (katta harflar bilan).",
    },
    {
        "slug": "wc1-imtihon-bahosi", "title": "Imtihon bahosi", "difficulty": "beginner",
        "tags": ["conditionals"], "solve": c_solve, "tests": c_tests, "samples": 2,
        "statement": ("Talaba imtihondan $s$ ball oldi. Baho quyidagicha qo‘yiladi:\n\n"
                      "- 86–100 ball — **5**\n- 71–85 ball — **4**\n- 56–70 ball — **3**\n- 0–55 ball — **2**\n\n"
                      "Talabaning bahosini aniqlang."),
        "input": "Bitta butun son $s$ ($0 \\le s \\le 100$).",
        "output": "Bahoni (2, 3, 4 yoki 5) chiqaring.",
    },
    {
        "slug": "wc1-juft-sonlar-yigindisi", "title": "Juft sonlar yig‘indisi", "difficulty": "easy",
        "tags": ["loops"], "solve": d_solve, "tests": d_tests, "samples": 2,
        "statement": "$1$ dan $n$ gacha (ikkalasi ham kiradi) bo‘lgan barcha juft sonlar yig‘indisini toping.",
        "input": "Bitta butun son $n$ ($1 \\le n \\le 10^4$).",
        "output": "Juft sonlar yig‘indisini chiqaring. Juft son bo‘lmasa, 0 chiqaring.",
    },
    {
        "slug": "wc1-harorat", "title": "Eng issiq va eng sovuq kun", "difficulty": "easy",
        "tags": ["loops", "conditionals"], "solve": e_solve, "tests": e_tests, "samples": 2,
        "statement": "$n$ kun davomida havo harorati o‘lchandi. Eng yuqori va eng past haroratni toping.",
        "input": ("Birinchi qatorda $n$ ($1 \\le n \\le 1000$). Ikkinchi qatorda $n$ ta butun son — "
                  "haroratlar ($-100 \\le t_i \\le 100$)."),
        "output": "Bitta qatorda probel bilan: eng yuqori harorat, keyin eng past harorat.",
    },
    {
        "slug": "wc1-raqamlar-yigindisi", "title": "Raqamlar yig‘indisi", "difficulty": "easy",
        "tags": ["loops"], "solve": f_solve, "tests": f_tests, "samples": 2,
        "statement": "Butun son $n$ berilgan. Uning raqamlari yig‘indisini toping. Masalan, 2026 uchun $2+0+2+6=10$.",
        "input": "Bitta butun son $n$ ($0 \\le n \\le 10^{18}$).",
        "output": "Raqamlar yig‘indisini chiqaring.",
    },
    {
        "slug": "wc1-tub-sonlar", "title": "Tub sonlar", "difficulty": "medium", "tl_ms": 2000,
        "tags": ["loops"], "solve": g_solve, "tests": g_tests, "samples": 2,
        "statement": ("Tub son — faqat 1 ga va o‘ziga bo‘linadigan, 1 dan katta son (2, 3, 5, 7, 11, …). "
                      "$1$ dan $n$ gacha nechta tub son borligini toping."),
        "input": "Bitta butun son $n$ ($1 \\le n \\le 10^6$).",
        "output": "Tub sonlar sonini chiqaring.",
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
        "slug": "wc1-eng-uzun-osish", "title": "Eng uzun o‘sish", "difficulty": "medium",
        "tags": ["loops", "conditionals"], "solve": i_solve, "tests": i_tests, "samples": 2,
        "statement": ("Talabaning $n$ kundagi ballari berilgan. Ketma-ket kelgan kunlardan iborat eng uzun "
                      "bo‘lakni toping, unda har bir kungi ball oldingisidan **qat’iy katta** bo‘lsin. "
                      "Shu bo‘lak uzunligini chiqaring."),
        "input": ("Birinchi qatorda $n$ ($1 \\le n \\le 2 \\cdot 10^5$). Ikkinchi qatorda $n$ ta butun son "
                  "($1 \\le a_i \\le 10^9$)."),
        "output": "Eng uzun o‘sib boruvchi bo‘lak uzunligini chiqaring.",
    },
    {
        "slug": "wc1-boluvchilar-yigindisi", "title": "Bo‘luvchilar soni yig‘indisi", "difficulty": "hard",
        "tl_ms": 2000, "tags": ["loops"], "solve": j_solve, "tests": j_tests, "samples": 2,
        "statement": ("$d(k)$ — $k$ sonining bo‘luvchilari soni. Masalan, $d(6)=4$ (1, 2, 3, 6). "
                      "$d(1) + d(2) + \\dots + d(n)$ yig‘indisini toping.\n\n"
                      "Diqqat: $n$ juda katta bo‘lishi mumkin, oddiy sikl vaqtga sig‘maydi."),
        "input": "Bitta butun son $n$ ($1 \\le n \\le 10^{12}$).",
        "output": "Yig‘indini chiqaring (javob 64 bitli butun songa sig‘adi).",
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

        taken = set(contest.contest_problems.values_list("label", flat=True))
        with transaction.atomic():
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
