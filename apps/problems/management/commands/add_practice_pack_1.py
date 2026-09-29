"""Practice pack #1: 25 Beginner/Easy problems on input/output, conditions (if-else) and loops, for
students who are just starting. None repeats a problem already on the portal (seed_problems,
seed_story_problems, Weekend Contest #1).

Every expected output is computed here by a reference solution, never typed by hand, so a test
can't be wrong. Safe to re-run: problems that already exist (by slug) are left as they are.

    python manage.py add_practice_pack_1 [--author admin] [--hidden] [--dry-run]
"""
import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.problems.models import Problem, Tag, TestCase


def _lines(*rows) -> str:
    return "\n".join(str(r) for r in rows) + "\n"


def _yes(ok: bool) -> str:
    return _lines("YES" if ok else "NO")


def _nums(line: str) -> list[int]:
    return list(map(int, line.split()))


# ============================== Kiritish / chiqarish ==============================

def olma_solve(inp):
    n, k = _nums(inp)
    return _lines(n // k, n % k)


def olma_tests(rng):
    t = ["17 5", "20 4", "0 3", "1 1", "5 10", "1000000000 1", "1000000000 1000000000", "999999999 1000"]
    return t + [f"{rng.randint(0, 10**9)} {rng.randint(1, rng.choice([10, 1000, 10**9]))}" for _ in range(14)]


def kino_solve(inp):
    n, k = _nums(inp)
    return _lines(f"{(n - 1) // k + 1} {(n - 1) % k + 1}")


def kino_tests(rng):
    t = ["25 10", "20 10", "1 1", "1 1000", "1000 1000", "1001 1000", "1000000000 1", "1000000000 1000", "7 3"]
    return t + [f"{rng.randint(1, 10**9)} {rng.randint(1, 1000)}" for _ in range(13)]


def dars_solve(inp):
    h, m, k = _nums(inp)
    t = (h * 60 + m + k) % 1440
    return _lines(f"{t // 60:02d}:{t % 60:02d}")


def dars_tests(rng):
    t = ["8 30 80", "23 10 90", "0 0 1440", "23 59 1", "0 0 1", "12 0 60", "9 5 5", "23 59 10000", "0 0 10000"]
    return t + [f"{rng.randint(0, 23)} {rng.randint(0, 59)} {rng.randint(1, 10000)}" for _ in range(13)]


def poyezd_solve(inp):
    s, v = _nums(inp)
    return _lines((s * 60 + v - 1) // v)


def poyezd_tests(rng):
    t = ["120 80", "100 60", "1 300", "100000 1", "1 1", "7 300", "300 300", "100000 300", "59 59"]
    return t + [f"{rng.randint(1, 10**5)} {rng.randint(1, 300)}" for _ in range(13)]


def konfet_solve(inp):
    n, k = _nums(inp)
    packs = (n * k + 11) // 12
    return _lines(packs, packs * 12 - n * k)


def konfet_tests(rng):
    t = ["5 3", "4 3", "1 1", "12 1", "13 1", "10000 10000", "1 12", "6 2", "7 7"]
    return t + [f"{rng.randint(1, 10**4)} {rng.randint(1, rng.choice([20, 10**4]))}" for _ in range(13)]


# ============================== Shart (if-else) ==============================

def ish_solve(inp):
    return _lines("Ish kuni" if int(inp) <= 5 else "Dam olish kuni")


def ish_tests(rng):
    return ["3", "6"] + [str(d) for d in range(1, 8)] + [str(rng.randint(1, 7)) for _ in range(13)]


def oraliq_solve(inp):
    a, b, x = _nums(inp)
    return _yes(min(a, b) <= x <= max(a, b))


def oraliq_tests(rng):
    t = ["1 10 5", "10 1 11", "10 1 5", "3 3 3", "3 3 4", "-5 5 -5", "-5 5 5", "-5 5 -6",
         "-1000000000 1000000000 0", "1000000000 -1000000000 1000000000"]
    for _ in range(12):
        a, b = rng.randint(-100, 100), rng.randint(-100, 100)
        t.append(f"{a} {b} {rng.randint(-120, 120)}")
    return t


def ortancha_solve(inp):
    return _lines(sorted(_nums(inp))[1])


def ortancha_tests(rng):
    t = ["3 1 2", "5 5 1", "7 2 7", "4 4 4", "-1 -5 -3", "1000000000 -1000000000 0", "1 2 3", "3 2 1", "2 3 1"]
    return t + [" ".join(str(rng.randint(-10**9, 10**9)) for _ in range(3)) for _ in range(13)]


def svetofor_solve(inp):
    t = int(inp) % 60
    return _lines("Yashil" if t < 30 else "Sariq" if t < 33 else "Qizil")


def svetofor_tests(rng):
    t = ["10", "31", "0", "29", "30", "32", "33", "59", "60", "90", "1000000000", "119"]
    return t + [str(rng.randint(0, 10**9)) for _ in range(10)]


def ildiz_solve(inp):
    a, b, c = _nums(inp)
    d = b * b - 4 * a * c
    return _lines(2 if d > 0 else 1 if d == 0 else 0)


def ildiz_tests(rng):
    t = ["1 -3 2", "1 2 1", "1 0 1", "-1 0 4", "2 4 2", "1000 0 1000", "-1000 1000 -250", "1 0 0", "5 1 -1"]
    for _ in range(13):
        a = rng.choice([x for x in range(-20, 21) if x])
        if rng.random() < 0.3:  # a perfect square: exactly one root
            r = rng.randint(-10, 10)
            t.append(f"{a} {-2 * a * r} {a * r * r}")
        else:
            t.append(f"{a} {rng.randint(-1000, 1000)} {rng.randint(-1000, 1000)}")
    return t


def aylana_solve(inp):
    x, y, r = _nums(inp)
    d, rr = x * x + y * y, r * r
    return _lines("Ichida" if d < rr else "Chegarada" if d == rr else "Tashqarida")


def aylana_tests(rng):
    t = ["1 2 5", "3 4 5", "6 0 5", "0 0 1", "0 -1 1", "-3 -4 5", "10000 10000 10000", "0 10000 10000",
         "-6000 8000 10000", "1 1 1"]
    for _ in range(12):
        r = rng.randint(1, 10000)
        t.append(f"{rng.randint(-r - 50, r + 50)} {rng.randint(-r - 50, r + 50)} {r}")
    return t


def shaxmat_solve(inp):
    s = inp.strip()
    col, row = ord(s[0]) - ord("a") + 1, int(s[1])
    return _lines("Qora" if (col + row) % 2 == 0 else "Oq")


def shaxmat_tests(rng):
    t = ["a1", "e4", "h8", "a8", "h1", "d1", "e1", "b2"]
    cells = [f"{c}{r}" for c in "abcdefgh" for r in range(1, 9)]
    return t + rng.sample(cells, 14)


def shkaf_solve(inp):
    a, b, c, d = _nums(inp)
    return _yes((a <= c and b <= d) or (a <= d and b <= c))


def shkaf_tests(rng):
    t = ["80 200 90 210", "220 80 90 210", "100 100 99 1000", "90 210 90 210", "210 90 90 210",
         "1 1 1 1", "2 1 1 1", "1000 1 1 1000", "50 300 100 250"]
    for _ in range(13):
        t.append(" ".join(str(rng.randint(40, 260)) for _ in range(4)))
    return t


# ============================== Sikllar ==============================

def fakt_solve(inp):
    n, f = int(inp), 1
    for i in range(2, n + 1):
        f *= i
    return _lines(f)


def fakt_tests(rng):
    return ["5", "0"] + [str(n) for n in range(1, 21)]


def rsoni_solve(inp):
    return _lines(len(inp.strip()))


def rsoni_tests(rng):
    t = ["2026", "7", "0", "10", "99", "100", "1000000000000000000", "999999999999999999"]
    return t + [str(rng.randint(0, 10 ** rng.randint(1, 18))) for _ in range(14)]


def rkop_solve(inp):
    p = 1
    for ch in inp.strip():
        p *= int(ch)
    return _lines(p)


def rkop_tests(rng):
    t = ["234", "105", "7", "1", "10", "999999999999999999", "1000000000000000000", "111111111111111111"]
    return t + [str(rng.randint(1, 10 ** rng.randint(1, 18))) for _ in range(14)]


def boluv_solve(inp):
    n = int(inp)
    return _lines(sum(1 for i in range(1, n + 1) if n % i == 0))


def boluv_tests(rng):
    t = ["12", "7", "1", "2", "36", "1000000", "720720", "999983", "997", "65536"]
    return t + [str(rng.randint(1, 10**6)) for _ in range(12)]


def tub_solve(inp):
    n = int(inp)
    if n < 2:
        return _yes(False)
    i = 2
    while i * i <= n:
        if n % i == 0:
            return _yes(False)
        i += 1
    return _yes(True)


def tub_tests(rng):
    t = ["7", "12", "1", "2", "3", "4", "9", "97", "999999937", "1000000000", "999999929", "961748941",
         "999999893", "35"]
    return t + [str(rng.randint(1, 10**9)) for _ in range(8)]


def harorat_solve(inp):
    a = _nums(inp.split("\n", 1)[1])
    return _lines(max(a), min(a))


def harorat_tests(rng):
    def case(xs):
        return f"{len(xs)}\n{' '.join(map(str, xs))}"
    t = [case([12, -3, 25, 7, 18]), case([5, 5, 5]), case([-50]), case([50, -50]), case([-1, -2, -3, -4])]
    for _ in range(17):
        n = rng.choice([1, 2, 10, 100, 1000])
        t.append(case([rng.randint(-50, 50) for _ in range(n)]))
    return t


def ishora_solve(inp):
    a = _nums(inp.split("\n", 1)[1])
    return _lines(f"{sum(x > 0 for x in a)} {sum(x < 0 for x in a)} {sum(x == 0 for x in a)}")


def ishora_tests(rng):
    def case(xs):
        return f"{len(xs)}\n{' '.join(map(str, xs))}"
    t = [case([3, -1, 0, 7, -5, 0]), case([1, 2, 3]), case([0]), case([-7]), case([0, 0, 0, 0])]
    for _ in range(17):
        n = rng.choice([1, 5, 50, 1000])
        t.append(case([rng.choice([0, rng.randint(-10**9, 10**9)]) for _ in range(n)]))
    return t


def fib_solve(inp):
    n, a, b = int(inp), 1, 1
    for _ in range(n - 1):
        a, b = b, a + b
    return _lines(a)


def fib_tests(rng):
    t = ["6", "10", "1", "2", "3", "50", "90", "89"]
    return t + [str(rng.randint(1, 90)) for _ in range(14)]


def bakt_solve(inp):
    a, m = _nums(inp)
    h = 0
    while a < m:
        a *= 2
        h += 1
    return _lines(h)


def bakt_tests(rng):
    t = ["3 20", "5 5", "1 1", "1 2", "1 1000000000000000000", "1000000000000000000 1000000000000000000",
         "7 8", "8 16", "8 17"]
    for _ in range(13):
        m = rng.randint(1, 10**18)
        t.append(f"{rng.randint(1, min(m, 10 ** rng.randint(1, 18)))} {m}")
    return t


def zina_solve(inp):
    return _lines(*("*" * i for i in range(1, int(inp) + 1)))


def zina_tests(rng):
    return ["3", "5", "1", "2", "50", "49", "10"] + [str(rng.randint(1, 50)) for _ in range(15)]


def ildizr_solve(inp):
    n = int(inp)
    while n >= 10:
        n = sum(int(ch) for ch in str(n))
    return _lines(n)


def ildizr_tests(rng):
    t = ["9875", "7", "0", "10", "99", "999999999999999999", "1000000000000000000", "123456789"]
    return t + [str(rng.randint(0, 10 ** rng.randint(1, 18))) for _ in range(14)]


def jamg_solve(inp):
    a, d, s = _nums(inp)
    total = days = 0
    while total < s:
        total += a + days * d
        days += 1
    return _lines(days)


def jamg_tests(rng):
    t = ["1000 500 10000", "5 0 20", "1 0 1", "1 0 1000000", "1000 1000 1000000", "1 1 1000000",
         "1000 0 1000", "1000 0 1001", "3 2 15"]
    return t + [f"{rng.randint(1, 1000)} {rng.randint(0, 1000)} {rng.randint(1, 10**6)}" for _ in range(13)]


YN = "Javob `YES` (ha) yoki `NO` (yo‘q) bo‘lsin."

PROBLEMS = [
    # ---------- kiritish / chiqarish ----------
    {"slug": "p1-olmalarni-bolish", "title": "Olmalarni bo‘lish", "difficulty": "beginner",
     "tags": ["input-output", "math"], "solve": olma_solve, "tests": olma_tests,
     "statement": "Savatda $n$ ta olma bor. Ularni $k$ ta bolaga teng bo‘lishdi: har biriga bir xil miqdorda, "
                  "iloji boricha ko‘p. Har bir bolaga nechta olma tegadi va savatda nechtasi qoladi?",
     "input": "Bitta qatorda ikkita butun son: $n$ va $k$ ($0 \\le n \\le 10^9$, $1 \\le k \\le 10^9$).",
     "output": "Birinchi qatorda bir bolaga tekkan olmalar sonini, ikkinchi qatorda qolgan olmalar sonini chiqaring."},
    {"slug": "p1-kinoteatrda-orin", "title": "Kinoteatrda o‘rin", "difficulty": "beginner",
     "tags": ["input-output", "math"], "solve": kino_solve, "tests": kino_tests,
     "statement": "Kinoteatrda har bir qatorda $k$ ta o‘rin bor. O‘rinlar birinchi qatordan boshlab, chapdan "
                  "o‘ngga qarab $1, 2, 3, \\ldots$ deb raqamlangan. Chiptada $n$ raqami yozilgan. "
                  "Bu o‘rin nechanchi qatorda va shu qatorning nechanchi o‘rni?",
     "input": "Bitta qatorda ikkita butun son: $n$ va $k$ ($1 \\le n \\le 10^9$, $1 \\le k \\le 1000$).",
     "output": "Bitta qatorda probel bilan: qator raqami va qatordagi o‘rin raqami."},
    {"slug": "p1-dars-qachon-tugaydi", "title": "Dars qachon tugaydi?", "difficulty": "easy",
     "tags": ["input-output", "math"], "solve": dars_solve, "tests": dars_tests,
     "statement": "Dars $h$ soat $m$ daqiqada boshlanadi va $k$ daqiqa davom etadi. Dars soat nechada tugaydi? "
                  "Vaqt 24 soatlik formatda; yarim tundan keyin soat yana $00:00$ dan boshlanadi.",
     "input": "Bitta qatorda uchta butun son: $h$, $m$ va $k$ ($0 \\le h \\le 23$, $0 \\le m \\le 59$, "
              "$1 \\le k \\le 10\\,000$).",
     "output": "Tugash vaqtini `SS:DD` ko‘rinishida chiqaring, masalan `09:05` (soat ham, daqiqa ham ikki xonali)."},
    {"slug": "p1-poyezd-yoli", "title": "Poyezd yo‘li", "difficulty": "beginner",
     "tags": ["input-output", "math"], "solve": poyezd_solve, "tests": poyezd_tests,
     "statement": "Poyezd $s$ km yo‘lni soatiga $v$ km tezlik bilan bosib o‘tadi. Yo‘l necha daqiqa davom etadi? "
                  "Javob butun bo‘lmasa, yuqoriga yaxlitlang: masalan, 10.2 daqiqa bo‘lsa, 11 deb chiqaring.",
     "input": "Bitta qatorda ikkita butun son: $s$ va $v$ ($1 \\le s \\le 10^5$, $1 \\le v \\le 300$).",
     "output": "Yo‘l davomiyligini daqiqalarda chiqaring."},
    {"slug": "p1-bayram-konfetlari", "title": "Bayram konfetlari", "difficulty": "beginner",
     "tags": ["input-output", "math"], "solve": konfet_solve, "tests": konfet_tests,
     "statement": "Sinfda $n$ ta bola bor, har biriga $k$ tadan konfet berilishi kerak. Konfetlar faqat "
                  "12 talik qutilarda sotiladi. Eng kamida nechta quti olish kerak va hammaga "
                  "tarqatilgandan keyin nechta konfet ortib qoladi?",
     "input": "Bitta qatorda ikkita butun son: $n$ va $k$ ($1 \\le n, k \\le 10^4$).",
     "output": "Birinchi qatorda qutilar sonini, ikkinchi qatorda ortib qolgan konfetlar sonini chiqaring."},
    # ---------- shart (if-else) ----------
    {"slug": "p1-ish-kunimi", "title": "Ish kunimi?", "difficulty": "beginner",
     "tags": ["conditionals"], "solve": ish_solve, "tests": ish_tests,
     "statement": "Hafta kunlari raqamlangan: 1 — dushanba, 2 — seshanba, …, 7 — yakshanba. "
                  "Shanba va yakshanba — dam olish kunlari, qolganlari — ish kunlari. Berilgan kun qaysi biri?",
     "input": "Bitta butun son $d$ ($1 \\le d \\le 7$).",
     "output": "`Ish kuni` yoki `Dam olish kuni` deb chiqaring."},
    {"slug": "p1-son-oraliqdami", "title": "Son oraliqdami?", "difficulty": "beginner",
     "tags": ["conditionals"], "solve": oraliq_solve, "tests": oraliq_tests,
     "statement": "Uchta son berilgan: $a$, $b$ va $x$. $x$ soni $a$ va $b$ orasida yotadimi (chegaralari bilan)? "
                  "Diqqat: $a$ har doim ham $b$ dan kichik emas.",
     "input": "Bitta qatorda uchta butun son: $a$, $b$, $x$ ($|a|, |b|, |x| \\le 10^9$).",
     "output": YN},
    {"slug": "p1-ortancha-son", "title": "O‘rtancha son", "difficulty": "easy",
     "tags": ["conditionals"], "solve": ortancha_solve, "tests": ortancha_tests,
     "statement": "Uchta son berilgan. Ularni o‘sish tartibida qo‘yganda o‘rtada turadigan sonni toping. "
                  "Masalan, 3, 1, 2 uchun javob 2; 5, 5, 1 uchun javob 5.",
     "input": "Bitta qatorda uchta butun son, har biri modul bo‘yicha $10^9$ dan oshmaydi.",
     "output": "O‘rtancha sonni chiqaring."},
    {"slug": "p1-svetofor", "title": "Svetofor", "difficulty": "easy",
     "tags": ["conditionals", "math"], "solve": svetofor_solve, "tests": svetofor_tests,
     "statement": "Svetofor bir xil tartibda ishlaydi: 30 soniya yashil, keyin 3 soniya sariq, keyin 27 soniya "
                  "qizil yonadi, so‘ng yana yashildan boshlanadi. Yashil chiroq yonganidan $t$ soniya o‘tdi. "
                  "Hozir qaysi chiroq yonib turibdi?\n\nMasalan, $t = 0$ dan $t = 29$ gacha — yashil, $t = 30$ — sariq.",
     "input": "Bitta butun son $t$ ($0 \\le t \\le 10^9$).",
     "output": "`Yashil`, `Sariq` yoki `Qizil` deb chiqaring."},
    {"slug": "p1-tenglama-ildizlari", "title": "Tenglama ildizlari", "difficulty": "easy",
     "tags": ["conditionals", "math"], "solve": ildiz_solve, "tests": ildiz_tests,
     "statement": "$ax^2 + bx + c = 0$ kvadrat tenglama nechta haqiqiy ildizga ega? Eslatma: diskriminant "
                  "$D = b^2 - 4ac$. $D > 0$ bo‘lsa — 2 ta, $D = 0$ bo‘lsa — 1 ta, $D < 0$ bo‘lsa — ildiz yo‘q.",
     "input": "Bitta qatorda uchta butun son: $a$, $b$, $c$ ($a \\ne 0$; $|a|, |b|, |c| \\le 1000$).",
     "output": "Ildizlar sonini chiqaring: 0, 1 yoki 2."},
    {"slug": "p1-nuqta-va-aylana", "title": "Nuqta va aylana", "difficulty": "easy",
     "tags": ["conditionals", "math"], "solve": aylana_solve, "tests": aylana_tests,
     "statement": "Markazi koordinata boshida, radiusi $r$ bo‘lgan aylana chizilgan. $(x, y)$ nuqta aylananing "
                  "ichidami, aynan chizig‘ida (chegarada)mi yoki tashqarisidami?\n\nMaslahat: ildiz olmasdan, "
                  "$x^2 + y^2$ ni $r^2$ bilan solishtiring — shunda kasr sonlar kerak bo‘lmaydi.",
     "input": "Bitta qatorda uchta butun son: $x$, $y$, $r$ ($|x|, |y| \\le 10^4 + 50$, $1 \\le r \\le 10^4$).",
     "output": "`Ichida`, `Chegarada` yoki `Tashqarida` deb chiqaring."},
    {"slug": "p1-shaxmat-katagi", "title": "Shaxmat katagi rangi", "difficulty": "easy",
     "tags": ["conditionals", "strings"], "solve": shaxmat_solve, "tests": shaxmat_tests,
     "statement": "Shaxmat taxtasida kataklar harf (ustun, `a`–`h`) va raqam (qator, `1`–`8`) bilan belgilanadi. "
                  "`a1` katagi — qora, undan o‘ngdagi `b1` — oq, va ranglar navbatlashib keladi. "
                  "Berilgan katak qanday rangda?",
     "input": "Bitta qatorda katak nomi, masalan `e4`.",
     "output": "`Oq` yoki `Qora` deb chiqaring."},
    {"slug": "p1-shkaf-eshikdan", "title": "Shkaf eshikdan o‘tadimi?", "difficulty": "easy",
     "tags": ["conditionals"], "solve": shkaf_solve, "tests": shkaf_tests,
     "statement": "Shkafning old tomoni $a \\times b$ sm, eshik o‘lchami $c \\times d$ sm. Shkafni 90° ga "
                  "burib ham olib o‘tish mumkin. Uning o‘lchamlari eshikdan katta bo‘lmasa, u sig‘adi "
                  "(teng bo‘lsa ham sig‘adi). Shkaf eshikdan o‘tadimi?",
     "input": "Bitta qatorda to‘rtta butun son: $a$, $b$, $c$, $d$ ($1 \\le a, b, c, d \\le 1000$).",
     "output": YN},
    # ---------- sikllar ----------
    {"slug": "p1-faktorial", "title": "Faktorial", "difficulty": "beginner",
     "tags": ["loops"], "solve": fakt_solve, "tests": fakt_tests,
     "statement": "$n! = 1 \\cdot 2 \\cdot 3 \\cdot \\ldots \\cdot n$ — $n$ ning faktoriali. Masalan, $5! = 120$. "
                  "Kelishuvga ko‘ra $0! = 1$. $n!$ ni hisoblang.",
     "input": "Bitta butun son $n$ ($0 \\le n \\le 20$).",
     "output": "$n!$ ni chiqaring."},
    {"slug": "p1-raqamlar-soni", "title": "Raqamlar soni", "difficulty": "beginner",
     "tags": ["loops"], "solve": rsoni_solve, "tests": rsoni_tests,
     "statement": "Berilgan son necha xonali? Masalan, 2026 — to‘rt xonali, 0 — bir xonali. "
                  "Sonni 10 ga bo‘lib borib, sikl yordamida hisoblang.",
     "input": "Bitta butun son $n$ ($0 \\le n \\le 10^{18}$).",
     "output": "Raqamlar sonini chiqaring."},
    {"slug": "p1-raqamlar-kopaytmasi", "title": "Raqamlar ko‘paytmasi", "difficulty": "beginner",
     "tags": ["loops"], "solve": rkop_solve, "tests": rkop_tests,
     "statement": "Sonning barcha raqamlari ko‘paytmasini toping. Masalan, 234 uchun $2 \\cdot 3 \\cdot 4 = 24$, "
                  "105 uchun esa 0.",
     "input": "Bitta butun son $n$ ($1 \\le n \\le 10^{18}$).",
     "output": "Raqamlar ko‘paytmasini chiqaring."},
    {"slug": "p1-boluvchilar-soni", "title": "Bo‘luvchilar soni", "difficulty": "easy",
     "tags": ["loops", "math"], "solve": boluv_solve, "tests": boluv_tests,
     "statement": "$n$ soni nechta natural songa qoldiqsiz bo‘linadi? Masalan, 12 ning bo‘luvchilari: "
                  "1, 2, 3, 4, 6, 12 — jami 6 ta.",
     "input": "Bitta butun son $n$ ($1 \\le n \\le 10^6$).",
     "output": "Bo‘luvchilar sonini chiqaring."},
    {"slug": "p1-tub-sonmi", "title": "Tub sonmi?", "difficulty": "easy",
     "tags": ["loops", "math"], "solve": tub_solve, "tests": tub_tests,
     "statement": "Faqat 1 ga va o‘ziga bo‘linadigan, 1 dan katta son tub son deyiladi: 2, 3, 5, 7, 11, … "
                  "Berilgan son tubmi?\n\nMaslahat: $n$ gacha tekshirish sekin. Agar $n$ ning bo‘luvchisi bo‘lsa, "
                  "ulardan biri $\\sqrt{n}$ dan oshmaydi — shuncha tekshirish yetarli.",
     "input": "Bitta butun son $n$ ($1 \\le n \\le 10^9$).",
     "output": YN},
    {"slug": "p1-eng-issiq-eng-sovuq", "title": "Eng issiq va eng sovuq kun", "difficulty": "beginner",
     "tags": ["loops"], "solve": harorat_solve, "tests": harorat_tests,
     "statement": "Ob-havo stansiyasi $n$ kun davomida havo haroratini yozib bordi. Eng issiq va eng sovuq "
                  "kunlardagi haroratni toping.",
     "input": "Birinchi qatorda $n$ ($1 \\le n \\le 1000$). Ikkinchi qatorda $n$ ta butun son — haroratlar "
              "($-50 \\le t_i \\le 50$).",
     "output": "Birinchi qatorda eng yuqori, ikkinchi qatorda eng past haroratni chiqaring."},
    {"slug": "p1-musbat-manfiy-nol", "title": "Musbat, manfiy va nollar", "difficulty": "beginner",
     "tags": ["loops", "conditionals"], "solve": ishora_solve, "tests": ishora_tests,
     "statement": "$n$ ta son berilgan. Ularning nechtasi musbat, nechtasi manfiy va nechtasi nolga teng?",
     "input": "Birinchi qatorda $n$ ($1 \\le n \\le 1000$). Ikkinchi qatorda $n$ ta butun son, har biri modul "
              "bo‘yicha $10^9$ dan oshmaydi.",
     "output": "Bitta qatorda probel bilan uchta son: musbatlar, manfiylar va nollar soni."},
    {"slug": "p1-quyonlar-oilasi", "title": "Quyonlar oilasi", "difficulty": "easy",
     "tags": ["loops"], "solve": fib_solve, "tests": fib_tests,
     "statement": "Fibonachchi ketma-ketligida birinchi ikki had 1 ga teng, keyingi har bir had oldingi ikkitasining "
                  "yig‘indisi: 1, 1, 2, 3, 5, 8, 13, … Ketma-ketlikning $n$-hadini toping.",
     "input": "Bitta butun son $n$ ($1 \\le n \\le 90$).",
     "output": "$n$-hadni chiqaring."},
    {"slug": "p1-bakteriyalar", "title": "Bakteriyalar", "difficulty": "easy",
     "tags": ["loops"], "solve": bakt_solve, "tests": bakt_tests,
     "statement": "Idishda $a$ ta bakteriya bor, ularning soni har soatda ikki baravar ko‘payadi. Necha soatdan "
                  "keyin bakteriyalar kamida $m$ ta bo‘ladi? Hozirning o‘zida $a \\ge m$ bo‘lsa, javob 0.",
     "input": "Bitta qatorda ikkita butun son: $a$ va $m$ ($1 \\le a \\le m \\le 10^{18}$).",
     "output": "Soatlar sonini chiqaring."},
    {"slug": "p1-yulduzcha-zinapoya", "title": "Yulduzcha zinapoya", "difficulty": "beginner",
     "tags": ["loops", "strings"], "solve": zina_solve, "tests": zina_tests,
     "statement": "$n$ qatorli zinapoya chizing: birinchi qatorda bitta `*`, ikkinchisida ikkita, …, "
                  "$n$-qatorda $n$ ta yulduzcha.",
     "input": "Bitta butun son $n$ ($1 \\le n \\le 50$).",
     "output": "$n$ ta qator; $i$-qatorda $i$ ta `*` belgisi, orasida probelsiz."},
    {"slug": "p1-raqamli-ildiz", "title": "Raqamli ildiz", "difficulty": "easy",
     "tags": ["loops"], "solve": ildizr_solve, "tests": ildizr_tests,
     "statement": "Sonning raqamlarini qo‘shamiz; natija bir xonali bo‘lmasa, uning raqamlarini yana qo‘shamiz — "
                  "bir xonali son qolguncha. Masalan: $9875 \\to 29 \\to 11 \\to 2$. Oxirgi bir xonali sonni toping.",
     "input": "Bitta butun son $n$ ($0 \\le n \\le 10^{18}$).",
     "output": "Bir xonali natijani chiqaring."},
    {"slug": "p1-jamgarma", "title": "Jamg‘arma", "difficulty": "easy",
     "tags": ["loops"], "solve": jamg_solve, "tests": jamg_tests,
     "statement": "Aziz telefon uchun pul yig‘moqda. Birinchi kuni $a$ so‘m qo‘ydi, keyingi har kuni oldingi "
                  "kundan $d$ so‘m ko‘proq qo‘yadi: $a$, $a + d$, $a + 2d$, … Necha kunda jamg‘arma kamida "
                  "$s$ so‘m bo‘ladi?",
     "input": "Bitta qatorda uchta butun son: $a$, $d$, $s$ ($1 \\le a \\le 1000$, $0 \\le d \\le 1000$, "
              "$1 \\le s \\le 10^6$).",
     "output": "Kunlar sonini chiqaring."},
]


class Command(BaseCommand):
    help = "Adds 25 Beginner/Easy practice problems (input/output, if-else, loops)."
    problems = PROBLEMS  # later packs subclass this command with their own list
    ml_mb = 256

    def add_arguments(self, parser):
        parser.add_argument("--author", default=None, help="Author username (default: first superuser)")
        parser.add_argument("--hidden", action="store_true", help="Add them hidden (e.g. for a contest)")
        parser.add_argument("--dry-run", action="store_true", help="Check everything, change nothing")

    def handle(self, *args, **opts):
        User = get_user_model()
        author = (User.objects.filter(username=opts["author"]).first() if opts["author"]
                  else User.objects.filter(is_superuser=True).order_by("pk").first())
        if author is None:
            raise CommandError("Muallif topilmadi — --author bilan mavjud login bering.")

        created = 0
        with transaction.atomic():
            for spec in self.problems:
                created += self._add(spec, author, public=not opts["hidden"])
            if opts["dry_run"]:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("Dry run — hech narsa saqlanmadi."))
                return
        where = "yashirin" if opts["hidden"] else "ochiq (Masalalar ro'yxatida)"
        self.stdout.write(self.style.SUCCESS(f"Tayyor: {created} ta yangi masala qo'shildi, {where}."))

    def _add(self, spec, author, public) -> int:
        if Problem.objects.filter(slug=spec["slug"]).exists():
            self.stdout.write(f"  = {spec['title']}: avvaldan bor — o'zgartirilmadi")
            return 0
        rng = random.Random(spec["slug"])  # same tests on every run
        inputs = spec["tests"](rng)
        if len(inputs) < 20:
            raise CommandError(f"{spec['slug']}: testlar kam ({len(inputs)})")
        problem = Problem.objects.create(
            slug=spec["slug"], title=spec["title"], statement_md=spec["statement"],
            input_md=spec["input"], output_md=spec["output"], difficulty=spec["difficulty"],
            tl_ms=1000, ml_mb=self.ml_mb, is_public=public, status=Problem.Status.APPROVED, author=author,
        )
        problem.tags.set([Tag.objects.get_or_create(name=name)[0] for name in spec["tags"]])
        TestCase.objects.bulk_create(
            TestCase(problem=problem, input=inp.rstrip("\n") + "\n", expected=spec["solve"](inp),
                     is_sample=k < 2, order=k)
            for k, inp in enumerate(inputs))
        self.stdout.write(f"  + {problem.title} ({problem.get_difficulty_display()}): {len(inputs)} ta test")
        return 1
