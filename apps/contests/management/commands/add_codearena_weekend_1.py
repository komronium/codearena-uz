"""CodeArena Weekend #1 (Codeforces rules): seven hidden problems, 3 Beginner, 3 Easy, 1 Medium, on
input/output, if, for and arithmetic, attached to the existing contest as A..G with CF-scale points.
None repeats a problem already on the portal.

Every expected output comes from a reference solution here, never typed by hand. Safe to re-run:
problems that already exist (by slug) are reused, not duplicated.

    python manage.py add_codearena_weekend_1 [--contest "CodeArena Weekend #1"] [--author admin] [--dry-run]
"""
from django.contrib.auth import get_user_model
from django.core.management.base import CommandError
from django.db import transaction
from django.utils import timezone

from apps.contests.management.commands.add_weekend_contest_1 import Command as WeekendCommand, _lines
from apps.contests.models import Contest


def _uniq(inputs):
    return list(dict.fromkeys(inputs))


# ---- A. Beginner: metro kartasi ----------------------------------------------------------
def metro_solve(inp):
    b, p, n = map(int, inp.split())
    return _lines(max(0, n * p - b))


def metro_tests(rng):
    tests = ["5000 1700 4", "10000 1700 5", "8500 1700 5", "0 1 1", "1000000 10000 100", "0 10000 100",
             "1700 1700 1", "1699 1700 1"]
    tests += [f"{rng.randint(0, 10**6)} {rng.randint(1, 10**4)} {rng.randint(1, 100)}" for _ in range(14)]
    return _uniq(tests)


# ---- B. Beginner: stadion ----------------------------------------------------------------
def stadion_solve(inp):
    lap, d = map(int, inp.split())
    return _lines(f"{d // lap} {d % lap}")


def stadion_tests(rng):
    tests = ["400 1000", "400 1200", "400 0", "400 399", "1 1000000000", "1000 1000000000", "1000 999", "7 50"]
    tests += [f"{rng.randint(1, 1000)} {rng.randint(0, rng.choice([1000, 10**6, 10**9]))}" for _ in range(14)]
    return _uniq(tests)


# ---- C. Beginner: batareya ---------------------------------------------------------------
def batareya_solve(inp):
    x = int(inp)
    return _lines("Qizil" if x < 20 else "Sariq" if x < 80 else "Yashil")


def batareya_tests(rng):
    return _uniq(["15", "80", "0", "19", "20", "50", "79", "100", "1", "99", "81", "21"]
                 + [str(rng.randint(0, 100)) for _ in range(12)])


# ---- D. Easy: issiq kunlar ---------------------------------------------------------------
def issiq_solve(inp):
    temps = list(map(int, inp.split()[1:]))
    best = run = 0
    for t in temps:
        run = run + 1 if t > 25 else 0
        best = max(best, run)
    return _lines(best)


def issiq_tests(rng):
    def case(arr):
        return f"{len(arr)}\n{' '.join(map(str, arr))}"
    tests = [case([26, 30, 25, 27, 28, 29, 20]), case([10, 20, 25]), case([26]), case([25]), case([50] * 1000),
             case([-50] * 1000), case([26, 25] * 500), case([20] * 999 + [30]), case([30] + [20] * 999)]
    for _ in range(13):
        n = rng.randint(1, 1000)
        lo = rng.choice([-50, 0, 15, 20])
        tests.append(case([rng.randint(lo, 40) for _ in range(n)]))
    return _uniq(tests)


# ---- E. Easy: mukammal son ---------------------------------------------------------------
def mukammal_solve(inp):
    n = int(inp)
    s = sum(d for d in range(1, n // 2 + 1) if n % d == 0)
    return _lines("Mukammal" if s == n else "Ortiqcha" if s > n else "Kam")


def mukammal_tests(rng):
    tests = ["6", "12", "1", "2", "28", "496", "8128", "945", "999983", "1000000", "720720", "16", "18", "997"]
    tests += [str(rng.randint(1, 10**6)) for _ in range(10)]
    return _uniq(tests)


# ---- F. Easy: soat millari ---------------------------------------------------------------
def soat_solve(inp):
    h, m = map(int, inp.split())
    twice = abs(60 * (h % 12) - 11 * m)  # twice the angle, so it stays an integer
    twice = min(twice, 720 - twice)
    return _lines(twice // 2 if twice % 2 == 0 else f"{twice // 2}.5")


def soat_tests(rng):
    tests = ["3 0", "9 45", "0 0", "12 0", "6 0", "15 30", "23 59", "12 30", "1 5", "11 59", "0 1", "18 0"]
    tests += [f"{rng.randint(0, 23)} {rng.randint(0, 59)}" for _ in range(12)]
    return _uniq(tests)


# ---- G. Medium: baxtli chiptalar ---------------------------------------------------------
def chipta_solve(inp):
    a, b = map(int, inp.split())
    digits = [x // 100 + x // 10 % 10 + x % 10 for x in range(1000)]
    return _lines(sum(1 for x in range(a, b + 1) if digits[x // 1000] == digits[x % 1000]))


def chipta_tests(rng):
    tests = ["0 999999", "123321 123330", "0 0", "1 1", "1001 1001", "999999 999999", "0 1000", "500000 999999",
             "100000 199999"]
    for _ in range(13):
        a = rng.randint(0, 999999)
        tests.append(f"{a} {rng.randint(a, min(999999, a + rng.choice([100, 10**4, 10**6])))}")
    return _uniq(tests)


PROBLEMS = [
    {
        "slug": "caw1-metro-kartasi", "title": "Metro kartasi", "difficulty": "beginner", "points": 500,
        "tags": ["input-output", "arithmetic"], "solve": metro_solve, "tests": metro_tests, "samples": 2,
        "statement": ("Metro kartasida $b$ so‘m bor. Bir safar $p$ so‘m turadi. Bu hafta metroda $n$ marta yurish "
                      "kerak. Kartaga kamida qancha pul solish kerak? Pul yetsa, hech narsa solish shart emas."),
        "input": ("Bitta qatorda uchta butun son: $b$, $p$, $n$ "
                  "($0 \\le b \\le 10^6$, $1 \\le p \\le 10^4$, $1 \\le n \\le 100$)."),
        "output": "Solinishi kerak bo‘lgan eng kam summa (pul yetsa, `0`).",
    },
    {
        "slug": "caw1-stadion", "title": "Stadion aylanasi", "difficulty": "beginner", "points": 500,
        "tags": ["input-output", "arithmetic"], "solve": stadion_solve, "tests": stadion_tests, "samples": 2,
        "statement": ("Stadion yugurish yo‘lagining bir aylanasi $L$ metr. Sportchi startdan $d$ metr yugurdi. "
                      "U nechta to‘liq aylana yugurdi va oxirgi chala aylanada necha metr yugurdi?"),
        "input": "Bitta qatorda ikkita butun son: $L$ va $d$ ($1 \\le L \\le 1000$, $0 \\le d \\le 10^9$).",
        "output": "Bitta qatorda probel bilan ikkita son: to‘liq aylanalar soni va qolgan metrlar.",
    },
    {
        "slug": "caw1-batareya", "title": "Batareya", "difficulty": "beginner", "points": 500,
        "tags": ["conditionals"], "solve": batareya_solve, "tests": batareya_tests, "samples": 2,
        "statement": ("Telefon batareyasi $x$ foiz zaryadlangan. Ekrandagi belgi rangi:\n\n"
                      "- $0 \\le x \\le 19$ — `Qizil`\n- $20 \\le x \\le 79$ — `Sariq`\n"
                      "- $80 \\le x \\le 100$ — `Yashil`"),
        "input": "Bitta butun son $x$ ($0 \\le x \\le 100$).",
        "output": "Rang nomi: `Qizil`, `Sariq` yoki `Yashil`.",
    },
    {
        "slug": "caw1-issiq-kunlar", "title": "Issiq kunlar", "difficulty": "easy", "points": 750,
        "tags": ["for-loop", "conditionals"], "solve": issiq_solve, "tests": issiq_tests, "samples": 2,
        "statement": ("$n$ kunlik havo harorati berilgan. Harorat $25$ darajadan yuqori bo‘lgan kun issiq kun "
                      "hisoblanadi. Eng uzun issiq davr necha kun davom etgan, ya’ni ketma-ket kelgan issiq "
                      "kunlar soni eng ko‘pi bilan nechta?"),
        "input": ("Birinchi qatorda $n$ ($1 \\le n \\le 1000$). Ikkinchi qatorda $n$ ta butun son — haroratlar "
                  "($-50 \\le t_i \\le 50$)."),
        "output": "Eng uzun issiq davr uzunligi (issiq kun bo‘lmasa, `0`).",
    },
    {
        "slug": "caw1-mukammal-son", "title": "Mukammal son", "difficulty": "easy", "points": 1000,
        "tags": ["for-loop", "number-basics"], "solve": mukammal_solve, "tests": mukammal_tests, "samples": 2,
        "statement": ("Sonning o‘zidan kichik barcha musbat bo‘luvchilarini qo‘shamiz. Masalan, $12$ uchun: "
                      "$1 + 2 + 3 + 4 + 6 = 16$.\n\n"
                      "- Yig‘indi songa teng bo‘lsa, son `Mukammal` ($6 = 1 + 2 + 3$).\n"
                      "- Yig‘indi sondan katta bo‘lsa — `Ortiqcha`.\n"
                      "- Yig‘indi sondan kichik bo‘lsa — `Kam`."),
        "input": "Bitta butun son $n$ ($1 \\le n \\le 10^6$).",
        "output": "`Mukammal`, `Ortiqcha` yoki `Kam`.",
    },
    {
        "slug": "caw1-soat-millari", "title": "Soat millari", "difficulty": "easy", "points": 1000,
        "tags": ["arithmetic", "conditionals"], "solve": soat_solve, "tests": soat_tests, "samples": 2,
        "statement": ("Devordagi soat $h$:$m$ ni ko‘rsatmoqda. Soat mili ham bir tekis yuradi: masalan, 3:30 da u "
                      "3 bilan 4 ning o‘rtasida turadi. Soat va minut millari orasidagi kichik burchakni toping "
                      "(gradusda, $0$ dan $180$ gacha)."),
        "input": "Bitta qatorda ikkita butun son: $h$ va $m$ ($0 \\le h \\le 23$, $0 \\le m \\le 59$).",
        "output": ("Burchak. Butun bo‘lsa, butun son chiqaring (`90`). Butun bo‘lmasa, u doim `.5` bilan tugaydi: "
                   "shunday chiqaring (`22.5`)."),
    },
    {
        "slug": "caw1-baxtli-chiptalar", "title": "Baxtli chiptalar", "difficulty": "medium", "points": 1250,
        "tl_ms": 2000, "tags": ["for-loop", "number-basics"], "solve": chipta_solve, "tests": chipta_tests,
        "samples": 2,
        "statement": ("Avtobus chiptasining raqami olti xonali: $000000$ dan $999999$ gacha (kichik raqam "
                      "oldiga nollar yoziladi: $1001$ — bu $001001$). Birinchi uchta raqam yig‘indisi oxirgi uchta "
                      "raqam yig‘indisiga teng bo‘lsa, chipta baxtli. Masalan, $123321$: $1 + 2 + 3 = 3 + 2 + 1$.\n\n"
                      "$a$ dan $b$ gacha (ikkalasi ham kiradi) nechta baxtli chipta bor?"),
        "input": "Bitta qatorda ikkita butun son $a$ va $b$ ($0 \\le a \\le b \\le 999999$).",
        "output": "Baxtli chiptalar soni.",
    },
]


class Command(WeekendCommand):
    help = "Adds the 7 CodeArena Weekend #1 problems (hidden) and attaches them to the contest as A..G."
    ml_mb = 64

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.set_defaults(contest="CodeArena Weekend #1")

    def handle(self, *args, **opts):
        title = opts["contest"]
        contest = Contest.objects.filter(title__iexact=title).first()
        if contest is None:
            raise CommandError(f"«{title}» musobaqasi topilmadi. Avval Boshqaruv → Musobaqalar'da yarating.")
        if contest.start <= timezone.now() and not opts["force"]:
            raise CommandError("Musobaqa allaqachon boshlangan. Baribir ulash uchun --force qo'shing.")

        User = get_user_model()
        author = (User.objects.filter(username=opts["author"]).first() if opts["author"]
                  else User.objects.filter(is_superuser=True).order_by("pk").first())
        if author is None:
            raise CommandError("Muallif topilmadi — --author bilan mavjud login bering.")

        with transaction.atomic():
            taken = set(contest.contest_problems.values_list("label", flat=True))
            for i, spec in enumerate(PROBLEMS):
                self._add(contest, spec, "ABCDEFG"[i], i, author, taken)
            if opts["dry_run"]:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("Dry run — hech narsa saqlanmadi."))
                return
        self.stdout.write(self.style.SUCCESS(
            f"Tayyor: «{contest.title}» da {contest.contest_problems.count()} ta masala. "
            "Masalalar yashirin; musobaqa tugagach Boshqaruv → Musobaqalar → «Masalalarni ochish»."))
