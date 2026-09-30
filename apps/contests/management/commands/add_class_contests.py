"""CodeArena #4 (8 problems, 60 min) and Mini Contest #1 (4 problems, 40 min) for the class: hidden
problems on input/output, // and %, if/elif, for and while, attached to freshly created contests.

Every expected output comes from a reference solution here, never typed by hand; the Mini Contest's
tests are the teacher's own table and are cross-checked against it. Safe to re-run: existing
contests and problems (by title / slug) are reused, not duplicated.

    python manage.py add_class_contests [--author admin] [--dry-run]
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.management.base import CommandError
from django.db import transaction

from apps.contests.management.commands.add_weekend_contest_1 import Command as WeekendCommand, _lines
from apps.contests.models import Contest

TASHKENT = ZoneInfo("Asia/Tashkent")


def _in(*rows) -> str:
    return "\n".join(str(r) for r in rows)


def _uniq(inputs):
    return list(dict.fromkeys(inputs))


# ---- CodeArena #4 -------------------------------------------------------------------------
def kassa_solve(inp):
    s = int(inp)
    return _lines(s // 10000, s % 10000 // 1000)


def kassa_tests(rng):
    tests = ["37000", "5000", "10000", "123000", "0", "1000000", "999000", "9000", "1000", "11000", "19000", "20000"]
    tests += [str(rng.randint(0, 1000) * 1000) for _ in range(10)]
    return _uniq(tests)


def chorak_solve(inp):
    avg = sum(map(int, inp.split())) / 3
    return _lines("A'lo" if avg >= 86 else "Yaxshi" if avg >= 71 else "Qoniqarli" if avg >= 56 else "Qoniqarsiz")


def chorak_tests(rng):
    tests = [_in(90, 85, 88), _in(70, 72, 75), _in(56, 56, 56), _in(40, 60, 50), _in(86, 86, 86),
             _in(100, 100, 100), _in(0, 0, 0), _in(71, 71, 71), _in(70, 70, 70), _in(85, 85, 85), _in(55, 55, 55),
             _in(100, 0, 100), _in(90, 90, 91), _in(60, 61, 62), _in(30, 90, 100)]
    while len(tests) < 24:
        t = [rng.randint(0, 100) for _ in range(3)]
        # An average strictly between two bands (e.g. 85.5) is read differently by ">= 86" and
        # "<= 85"; the statement doesn't say, so such sums are never tested.
        if sum(t) not in (166, 167, 211, 212, 256, 257):
            tests.append(_in(*t))
    return _uniq(tests)


def uchlik_solve(inp):
    return _lines(sum(range(3, int(inp) + 1, 3)))


def uchlik_tests(rng):
    tests = ["10", "2", "3", "30", "1", "1000", "999", "6", "100", "7", "998", "4", "300"]
    tests += [str(rng.randint(1, 1000)) for _ in range(8)]
    return _uniq(tests)


def dokon_solve(inp):
    v = list(map(int, inp.split()))[1:]
    return _lines(sum(v), max(v), v.count(0))


def dokon_tests(rng):
    tests = [_in(5, 1200000, 0, 850000, 2000000, 0), _in(1, 500000), _in(3, 0, 0, 0), _in(2, 300000, 300000),
             _in(1, 0), _in(1, 10000000), _in(4, 10000000, 10000000, 10000000, 10000000), _in(3, 5, 0, 7),
             _in(2, 0, 1), _in(6, 3, 3, 3, 3, 3, 3)]
    for n in (10, 20, 50, 100, 100, 100):
        tests.append(_in(n, *(rng.choice([0, 0, rng.randint(1, 10 ** rng.randint(1, 7))]) for _ in range(n))))
    tests.append(_in(100, *([0] * 99 + [10000000])))
    tests.append(_in(100, *([10000000] * 100)))
    tests.append(_in(7, *(rng.randint(1, 10000000) for _ in range(7))))
    tests.append(_in(30, *(rng.randint(0, 3) * 1000 for _ in range(30))))
    return _uniq(tests)


def toq_solve(inp):
    n = int(inp)
    divs = [d for d in range(1, n + 1) if n % d == 0]
    odd = [d for d in divs if d % 2]
    even = len(divs) - len(odd)
    return _lines(len(odd), sum(odd), "Toq ko'p" if len(odd) > even else "Juft ko'p" if len(odd) < even else "Teng")


def toq_tests(rng):
    tests = ["12", "45", "18", "1", "16", "2", "3", "4", "6", "64", "720", "945", "840", "997", "1000", "999",
             "1024", "900", "30", "36", "100"]
    tests += [str(rng.randint(1, 1000)) for _ in range(6)]
    return _uniq(tests)


def yettilik_solve(inp):
    a, b = map(int, inp.split())
    return _lines(b // 7 - (a - 1) // 7)


def yettilik_tests(rng):
    tests = [_in(1, 50), _in(8, 13), _in(7, 7), _in(10, 100), _in(1, 1), _in(1, 10000), _in(7, 14), _in(6, 7),
             _in(8, 8), _in(1, 6), _in(9999, 10000), _in(7000, 7007), _in(9996, 9996), _in(9997, 10000), _in(14, 14)]
    for _ in range(9):
        a = rng.randint(1, 10000)
        tests.append(_in(a, rng.randint(a, min(10000, a + rng.choice([5, 50, 10000])))))
    return _uniq(tests)


def _grade(x):
    return "A" if x >= 90 else "B" if x >= 70 else "C" if x >= 60 else "F"


def harf_solve(inp):
    return _lines(*(_grade(x) for x in list(map(int, inp.split()))[1:]))


def harf_tests(rng):
    tests = [_in(4, 95, 72, 60, 45), _in(1, 100), _in(4, 59, 70, 89, 90),
             _in(10, 0, 59, 60, 69, 70, 89, 90, 100, 61, 88), _in(1, 0), _in(1, 60), _in(1, 89), _in(2, 69, 90),
             _in(3, 100, 100, 100), _in(3, 0, 0, 0)]
    for n in (5, 10, 30, 100, 100, 100):
        tests.append(_in(n, *(rng.randint(0, 100) for _ in range(n))))
    tests.append(_in(100, *(rng.choice([59, 60, 69, 70, 89, 90]) for _ in range(100))))
    tests.append(_in(8, 55, 65, 75, 85, 95, 5, 15, 25))
    tests.append(_in(6, 91, 71, 61, 51, 89, 69))
    tests.append(_in(7, 99, 98, 97, 1, 2, 3, 80))
    tests.append(_in(1, 90))
    return _uniq(tests)


def jamgarma_solve(inp):
    x, y = map(int, inp.split())
    return _lines(-(-y // x))


def jamgarma_tests(rng):
    # A plain `while` loop runs y / x times (about 0.4 s per million in the sandbox), so no test
    # needs more than 2 million iterations, even though the statement allows 10^7.
    tests = [_in(150000, 1000000), _in(200000, 1000000), _in(1, 1), _in(5, 10000000), _in(10000000, 1),
             _in(10000000, 10000000), _in(3, 10), _in(7, 7), _in(7, 8), _in(5, 1), _in(1000, 999), _in(1000, 1000),
             _in(1000, 1001), _in(10, 9999999), _in(9999999, 10000000), _in(100000, 10000000), _in(1, 2000000)]
    while len(tests) < 26:
        x = rng.choice([rng.randint(1, 100), rng.randint(1000, 10 ** 6), rng.randint(1, 10 ** 7)])
        y = rng.randint(1, 10 ** 7)
        if -(-y // x) <= 2_000_000:
            tests.append(_in(x, y))
    return _uniq(tests)


CODEARENA_4 = [
    {
        "slug": "ca4-kassa", "title": "Kassa", "difficulty": "beginner", "tags": ["math", "input-output"],
        "solve": kassa_solve, "tests": kassa_tests, "samples": 2,
        "statement": ("Kassir mijozga $s$ so‘m qaytim berishi kerak. Kassada faqat 10 000 va 1 000 so‘mlik pullar bor. "
                      "Kassir avval iloji boricha ko‘p 10 000 lik beradi, qolganini 1 000 lik bilan.\n\n"
                      "Izoh: 37 000 = 3 · 10 000 + 7 · 1 000."),
        "input": "Bitta butun son $s$ ($0 \\le s \\le 1\\,000\\,000$, 1000 ga karrali).",
        "output": "Ikki qatorda: 10 000 liklar soni va 1 000 liklar soni.",
    },
    {
        "slug": "ca4-chorak-bahosi", "title": "Chorak bahosi", "difficulty": "beginner", "tags": ["conditionals"],
        "solve": chorak_solve, "tests": chorak_tests, "samples": 2,
        "statement": ("Talabaning uchta fan bo‘yicha bali berilgan. O‘rtacha ball bo‘yicha baho chiqaring:\n\n"
                      "- 86 va yuqori — `A'lo`\n- 71–85 — `Yaxshi`\n- 56–70 — `Qoniqarli`\n"
                      "- 56 dan past — `Qoniqarsiz`"),
        "input": "Uchta qatorda uchta butun son — fanlar bo‘yicha ball ($0 \\le$ ball $\\le 100$).",
        "output": "Bitta so‘z — baho.",
    },
    {
        "slug": "ca4-uchlik", "title": "Uchlik", "difficulty": "beginner", "tags": ["loops", "conditionals"],
        "solve": uchlik_solve, "tests": uchlik_tests, "samples": 2,
        "statement": ("Son $n$ berilgan. 1 dan $n$ gacha ($n$ ham kiradi) bo‘lgan, "
                      "3 ga bo‘linadigan sonlar yig‘indisini toping."),
        "input": "Bitta butun son $n$ ($1 \\le n \\le 1000$).",
        "output": "Bitta son — yig‘indi.",
    },
    {
        "slug": "ca4-dokon-hisoboti", "title": "Do‘kon hisoboti", "difficulty": "easy", "tags": ["loops", "arrays"],
        "solve": dokon_solve, "tests": dokon_tests, "samples": 2,
        "statement": ("Do‘kon $n$ kun ishladi. Har kungi savdo summasi berilgan (savdo bo‘lmagan kun — 0). "
                      "Uch qatorda chiqaring:\n\n1. Jami savdo\n2. Eng ko‘p savdo bo‘lgan kundagi summa\n"
                      "3. Savdo bo‘lmagan kunlar soni"),
        "input": ("Birinchi qatorda $n$ ($1 \\le n \\le 100$), keyin $n$ ta qatorda summa "
                  "($0 \\le$ summa $\\le 10\\,000\\,000$)."),
        "output": "Uch qator.",
    },
    {
        "slug": "ca4-toq-boluvchilar", "title": "Toq bo‘luvchilar", "difficulty": "easy", "tags": ["loops", "math"],
        "solve": toq_solve, "tests": toq_tests, "samples": 2,
        "statement": ("Son $n$ berilgan. Uch qatorda chiqaring:\n\n1. $n$ ning nechta toq bo‘luvchisi bor\n"
                      "2. Toq bo‘luvchilari yig‘indisi\n"
                      "3. Toq bo‘luvchilar juft bo‘luvchilardan ko‘p bo‘lsa — `Toq ko'p`, kam bo‘lsa — `Juft ko'p`, "
                      "teng bo‘lsa — `Teng`\n\n"
                      "Izoh: 12 ning bo‘luvchilari: 1, 2, 3, 4, 6, 12. Toq: 1, 3 (2 ta, yig‘indi 4). Juft: 4 ta."),
        "input": "Bitta butun son $n$ ($1 \\le n \\le 1000$).",
        "output": "Uch qator.",
    },
    {
        "slug": "ca4-yettilik", "title": "Yettilik", "difficulty": "easy", "tags": ["loops", "math"],
        "solve": yettilik_solve, "tests": yettilik_tests, "samples": 2,
        "statement": ("Ikki son $a$ va $b$ berilgan ($a \\le b$). $a$ dan $b$ gacha (ikkalasi ham kiradi) "
                      "nechta son 7 ga bo‘linadi?"),
        "input": "Ikki qatorda $a$ va $b$ ($1 \\le a \\le b \\le 10\\,000$).",
        "output": "Bitta son.",
    },
    {
        "slug": "ca4-harf-baho", "title": "Harf baho", "difficulty": "medium", "tags": ["loops", "conditionals"],
        "solve": harf_solve, "tests": harf_tests, "samples": 2,
        "statement": ("$n$ ta talaba bali berilgan. Har bir talaba uchun harf bahoni alohida qatorda chiqaring:\n\n"
                      "- 90 va yuqori — `A`\n- 70–89 — `B`\n- 60–69 — `C`\n- 60 dan past — `F`"),
        "input": "Birinchi qatorda $n$ ($1 \\le n \\le 100$), keyin $n$ ta qatorda ball ($0 \\le$ ball $\\le 100$).",
        "output": "$n$ ta qator — har bir talabaning harf bahosi.",
    },
    {
        "slug": "ca4-jamgarma", "title": "Jamg‘arma", "difficulty": "medium", "tl_ms": 2000, "tags": ["loops", "math"],
        "solve": jamgarma_solve, "tests": jamgarma_tests, "samples": 2,
        "statement": "Har oy $x$ so‘m tejayman. Maqsadim — kamida $y$ so‘m yig‘ish. Necha oyda maqsadga yetaman?",
        "input": "Ikki qatorda $x$ va $y$ ($1 \\le x, y \\le 10\\,000\\,000$).",
        "output": "Bitta son — oylar soni.",
    },
]


# ---- Mini Contest #1 (the teacher's own tests, samples first) ----------------------------
def partalar_solve(inp):
    return _lines((int(inp) + 1) // 2)


def chetki_solve(inp):
    n = int(inp)
    return _lines(n // 1000 + n % 10)


def login_solve(inp):
    ism, familiya, yil = inp.split("\n")
    return _lines(familiya[:3].lower() + ism[0].lower() + yil[-2:])


def soat_solve(inp):
    m = int(inp)
    return _lines(f"{m // 60:02}:{m % 60:02}")


def _table(solve, rows, samples):
    """Inputs with the statement's samples first, every row checked against the teacher's answer."""
    def tests(rng):
        for inp, out in rows:
            assert solve(inp) == _lines(out), (inp, out)
        inputs = [inp for inp, _ in rows]
        return [i for i in inputs if i in samples] + [i for i in inputs if i not in samples]
    return tests


PARTALAR = [("1", 1), ("2", 1), ("3", 2), ("25", 13), ("30", 15), ("31", 16), ("99", 50), ("100", 50), ("7", 4),
            ("1000000", 500000)]
CHETKI = [("1000", 1), ("2026", 8), ("4071", 5), ("9999", 18), ("1234", 5), ("5005", 10), ("8000", 8), ("1001", 2),
          ("7777", 14), ("3009", 12)]
LOGIN = [(_in("Komron", "Obloyev", 2003), "oblk03"), (_in("aziza", "KARIMOVA", 2005), "kara05"),
         (_in("Bobur", "Ali", 1999), "alib99"), (_in("sardor", "rahimov", 2010), "rahs10"),
         (_in("Madina", "Yusupova", 2000), "yusm00"), (_in("Ali", "Tosh", 1987), "tosa87"),
         (_in("Olim", "Umarov", 2001), "umao01"), (_in("Zarina", "Nazarova", 2006), "nazz06")]
SOAT = [("0", "00:00"), ("5", "00:05"), ("59", "00:59"), ("60", "01:00"), ("125", "02:05"), ("600", "10:00"),
        ("719", "11:59"), ("720", "12:00"), ("1379", "22:59"), ("1439", "23:59")]

MINI_1 = [
    {
        "slug": "mc1-partalar", "title": "Partalar", "difficulty": "beginner", "tags": ["math", "input-output"],
        "solve": partalar_solve, "tests": _table(partalar_solve, PARTALAR, {"25", "30"}), "samples": 2,
        "statement": ("Sinfda $n$ ta talaba bor. Har bir partaga 2 kishi o‘tiradi. "
                      "Hamma o‘tirishi uchun eng kamida nechta parta kerak?"),
        "input": "Bitta butun son $n$ ($1 \\le n \\le 10^6$).",
        "output": "Bitta butun son — partalar soni.",
    },
    {
        "slug": "mc1-chetki-raqamlar", "title": "Chetki raqamlar", "difficulty": "beginner",
        "tags": ["math", "input-output"],
        "solve": chetki_solve, "tests": _table(chetki_solve, CHETKI, {"2026", "4071"}), "samples": 2,
        "statement": "To‘rt xonali son berilgan. Uning birinchi va oxirgi raqamlari yig‘indisini chiqaring.",
        "input": "Bitta butun son $n$ ($1000 \\le n \\le 9999$).",
        "output": "Bitta butun son.",
    },
    {
        "slug": "mc1-login", "title": "Login", "difficulty": "easy", "tags": ["strings", "input-output"],
        "solve": login_solve,
        "tests": _table(login_solve, LOGIN, {LOGIN[0][0], LOGIN[1][0]}), "samples": 2,
        "statement": ("Universitet talaba uchun login quyidagi tartibda yasaydi: familiyaning birinchi 3 harfi, "
                      "keyin ismning birinchi harfi, keyin tug‘ilgan yilning oxirgi 2 raqami. "
                      "Logindagi barcha harflar kichik bo‘ladi."),
        "input": ("Uch qator: ism, familiya, tug‘ilgan yil. Familiyada kamida 3 harf bor. "
                  "Harflar katta yoki kichik bo‘lishi mumkin."),
        "output": "Login.",
    },
    {
        "slug": "mc1-soat-formati", "title": "Soat formati", "difficulty": "easy", "tags": ["math", "strings"],
        "solve": soat_solve, "tests": _table(soat_solve, SOAT, {"125", "1439"}), "samples": 2,
        "statement": ("Tun yarmidan beri necha daqiqa o‘tgani berilgan. Vaqtni `SS:DD` ko‘rinishida chiqaring. "
                      "Soat ham, daqiqa ham doim 2 xonali bo‘lsin, kerak bo‘lsa oldiga 0 qo‘shiladi."),
        "input": "Bitta butun son $m$ ($0 \\le m \\le 1439$).",
        "output": "Vaqt `SS:DD` ko‘rinishida.",
    },
]

CONTESTS = [
    {
        "title": "CodeArena #4", "start": datetime(2026, 9, 30, 11, 45, tzinfo=TASHKENT), "minutes": 60,
        "description": ("# Kirish formati har masalada boshqacha\n\n"
                        "`//` va `%`, `if / elif`, `for`, `while` asosidagi masalalar. "
                        "Kirish formatini diqqat bilan o‘qing."),
        "problems": CODEARENA_4,
    },
    {
        "title": "Mini Contest #1", "start": datetime(2026, 9, 30, 15, 10, tzinfo=TASHKENT), "minutes": 40,
        "description": "# Mini contest\n\nKirish-chiqish, `//` va `%`, satrlar bilan ishlash.",
        "problems": MINI_1,
    },
]


class Command(WeekendCommand):
    help = "Creates CodeArena #4 and Mini Contest #1 and attaches their hidden problems as A, B, C..."
    ml_mb = 64
    min_tests = 8

    def add_arguments(self, parser):
        parser.add_argument("--author", default=None, help="Author username (default: first superuser)")
        parser.add_argument("--dry-run", action="store_true", help="Check everything, change nothing")

    def handle(self, *args, **opts):
        User = get_user_model()
        author = (User.objects.filter(username=opts["author"]).first() if opts["author"]
                  else User.objects.filter(is_superuser=True).order_by("pk").first())
        if author is None:
            raise CommandError("Muallif topilmadi — --author bilan mavjud login bering.")

        with transaction.atomic():
            for spec in CONTESTS:
                contest, created = Contest.objects.get_or_create(
                    title=spec["title"],
                    defaults={"start": spec["start"], "end": spec["start"] + timedelta(minutes=spec["minutes"]),
                              "description_md": spec["description"], "is_rated": True})
                self.stdout.write(f"{'Yaratildi' if created else 'Bor'}: {contest.title}, "
                                  f"{contest.start.astimezone(TASHKENT):%d.%m %H:%M}, {contest.duration_label}")
                taken = set(contest.contest_problems.values_list("label", flat=True))
                for i, problem in enumerate(spec["problems"]):
                    self._add(contest, problem, "ABCDEFGH"[i], i, author, taken)
            if opts["dry_run"]:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("Dry run — hech narsa saqlanmadi."))
                return
        self.stdout.write(self.style.SUCCESS(
            "Tayyor. Masalalar yashirin; musobaqa tugagach Boshqaruv → Musobaqalar → «Masalalarni ochish»."))

