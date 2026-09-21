"""Real practice problems for the intro course (input/output, arithmetic, if/elif/else).

Every input value is on its own line (one `input()` per value) — the course
convention; multi-value outputs stay space-separated on one line.

Each entry declares samples, a random input generator and a reference solution;
the command materialises TESTS_PER_PROBLEM deterministic tests per problem.
Re-running is safe: problems are matched by slug and their tests are rebuilt.
"""
import random
from dataclasses import dataclass, field
from collections.abc import Callable

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User
from apps.problems.models import Problem, Tag, TestCase

TESTS_PER_PROBLEM = 50
YES, NO = "Ha", "Yo'q"


@dataclass
class Spec:
    slug: str
    title: str
    statement: str
    input: str
    output: str
    gen: Callable[[random.Random], str]      # -> stdin text
    solve: Callable[[str], str]              # stdin text -> expected stdout
    samples: list[str]                       # fixed inputs shown to students
    difficulty: str = Problem.Difficulty.BEGINNER
    tags: list[str] = field(default_factory=lambda: ["if-else"])
    is_public: bool = True
    tests: int = TESTS_PER_PROBLEM


def _ints(s: str) -> list[int]:
    return [int(x) for x in s.split()]


def _line(*xs) -> str:
    return " ".join(str(x) for x in xs) + "\n"


def _lines(*xs) -> str:
    return "".join(f"{x}\n" for x in xs)


def _is_leap(y: int) -> bool:
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


SPECS: list[Spec] = [
    Spec("a-plus-b", "A + B",
         "Ikkita butun son berilgan. Ularning yig'indisini chiqaring.",
         "Ikki qatorda ikkita butun son $a$ va $b$ ($-10^9 \\le a, b \\le 10^9$).",
         "Yagona son — $a + b$.",
         lambda r: _lines(r.randint(-10**9, 10**9), r.randint(-10**9, 10**9)),
         lambda s: _lines(sum(_ints(s))),
         ["2\n3\n", "-5\n5\n"], tags=["input-output", "math"]),

    Spec("rectangle", "To'g'ri to'rtburchak",
         "To'g'ri to'rtburchakning tomonlari berilgan. Uning perimetri va yuzini toping.",
         "Ikki qatorda ikkita natural son $a$ va $b$ ($1 \\le a, b \\le 10^4$).",
         "Bir qatorda ikkita son: perimetr va yuza.",
         lambda r: _lines(r.randint(1, 10**4), r.randint(1, 10**4)),
         lambda s: _line(2 * (_ints(s)[0] + _ints(s)[1]), _ints(s)[0] * _ints(s)[1]),
         ["3\n4\n", "5\n5\n"], tags=["input-output", "math"]),

    Spec("last-digit", "Oxirgi raqam",
         "Natural son berilgan. Uning oxirgi raqamini chiqaring.",
         "Yagona natural son $n$ ($1 \\le n \\le 10^{18}$).",
         "$n$ sonining oxirgi raqami.",
         lambda r: _lines(r.randint(1, 10**18)),
         lambda s: _lines(int(s) % 10),
         ["1234\n", "7\n"], tags=["input-output", "math"]),

    Spec("digit-sum-3", "Uch xonali son raqamlari yig'indisi",
         "Uch xonali natural son berilgan. Uning raqamlari yig'indisini toping.",
         "Yagona uch xonali son $n$ ($100 \\le n \\le 999$).",
         "Raqamlar yig'indisi.",
         lambda r: _lines(r.randint(100, 999)),
         lambda s: _lines(sum(int(c) for c in s.strip())),
         ["123\n", "905\n"], tags=["input-output", "math"]),

    Spec("reverse-two-digit", "Ikki xonali sonni teskari yozish",
         "Ikki xonali natural son berilgan. Raqamlari o'rnini almashtirib hosil bo'lgan sonni chiqaring. "
         "Masalan, $30$ uchun javob $3$ (chunki $03 = 3$).",
         "Yagona ikki xonali son $n$ ($10 \\le n \\le 99$).",
         "Raqamlari teskari tartibda yozilgan son (boshidagi nolsiz).",
         lambda r: _lines(r.randint(10, 99)),
         lambda s: _lines(int(s.strip()[::-1])),
         ["47\n", "30\n"], tags=["input-output", "math"]),

    Spec("seconds-to-hms", "Soat, daqiqa, soniya",
         "Yarim kun ichida o'tgan soniyalar soni berilgan. Buni soat, daqiqa va soniyaga ajrating.",
         "Yagona butun son $n$ ($0 \\le n < 86400$).",
         "Bir qatorda uchta son: soat, daqiqa, soniya.",
         lambda r: _lines(r.randint(0, 86399)),
         lambda s: _line(int(s) // 3600, int(s) % 3600 // 60, int(s) % 60),
         ["3661\n", "0\n"], tags=["input-output", "math"]),

    Spec("even-odd", "Juft yoki toq",
         "Butun son berilgan. U juft bo'lsa `Juft`, aks holda `Toq` deb chiqaring.",
         "Yagona butun son $n$ ($-10^9 \\le n \\le 10^9$).",
         "`Juft` yoki `Toq`.",
         lambda r: _lines(r.randint(-10**9, 10**9)),
         lambda s: _lines("Juft" if int(s) % 2 == 0 else "Toq"),
         ["4\n", "-7\n"]),

    Spec("max-of-two", "Ikkita sonning kattasi",
         "Ikkita butun son berilgan. Kattasini chiqaring.",
         "Ikki qatorda ikkita butun son $a$ va $b$ ($-10^9 \\le a, b \\le 10^9$).",
         "Kattasi.",
         lambda r: _lines(r.randint(-10**9, 10**9), r.randint(-10**9, 10**9)),
         lambda s: _lines(max(_ints(s))),
         ["3\n8\n", "-1\n-9\n"]),

    Spec("min-of-three", "Uchta sonning kichigi",
         "Uchta butun son berilgan. Eng kichigini chiqaring.",
         "Uch qatorda uchta butun son $a$, $b$, $c$ ($-10^9 \\le a, b, c \\le 10^9$).",
         "Eng kichik son.",
         lambda r: _lines(*(r.randint(-10**9, 10**9) for _ in range(3))),
         lambda s: _lines(min(_ints(s))),
         ["3\n1\n2\n", "5\n5\n5\n"]),

    Spec("compare", "Taqqoslash",
         "Ikkita butun son berilgan. $a < b$ bo'lsa `<`, $a > b$ bo'lsa `>`, teng bo'lsa `=` chiqaring.",
         "Ikki qatorda ikkita butun son $a$ va $b$ ($-10^9 \\le a, b \\le 10^9$).",
         "`<`, `>` yoki `=` belgilaridan biri.",
         lambda r: _lines(r.randint(-50, 50), r.randint(-50, 50)),
         lambda s: _lines("<" if _ints(s)[0] < _ints(s)[1] else ">" if _ints(s)[0] > _ints(s)[1] else "="),
         ["3\n8\n", "4\n4\n"]),

    Spec("sign", "Son ishorasi",
         "Butun son berilgan. U musbat bo'lsa `Musbat`, manfiy bo'lsa `Manfiy`, nol bo'lsa `Nol` chiqaring.",
         "Yagona butun son $n$ ($-10^9 \\le n \\le 10^9$).",
         "`Musbat`, `Manfiy` yoki `Nol`.",
         lambda r: _lines(r.choice([0, r.randint(-10**9, -1), r.randint(1, 10**9)])),
         lambda s: _lines("Nol" if int(s) == 0 else "Musbat" if int(s) > 0 else "Manfiy"),
         ["5\n", "0\n"]),

    Spec("abs", "Modul",
         "Butun son berilgan. Uning modulini (absolyut qiymatini) `abs` funksiyasisiz toping.",
         "Yagona butun son $n$ ($-10^9 \\le n \\le 10^9$).",
         "$|n|$.",
         lambda r: _lines(r.randint(-10**9, 10**9)),
         lambda s: _lines(abs(int(s))),
         ["-12\n", "7\n"]),

    Spec("leap-year", "Kabisa yili",
         "Yil berilgan. U kabisa yili bo'lsa `Ha`, aks holda `Yo'q` chiqaring. "
         "Yil 4 ga bo'linsa va 100 ga bo'linmasa, yoki 400 ga bo'linsa — kabisa.",
         "Yagona natural son $y$ ($1 \\le y \\le 9999$).",
         "`Ha` yoki `Yo'q`.",
         lambda r: _lines(r.choice([r.randint(1, 9999), r.randint(1, 99) * 100, r.randint(1, 24) * 400])),
         lambda s: _lines(YES if _is_leap(int(s)) else NO),
         ["2024\n", "1900\n"], difficulty=Problem.Difficulty.EASY),

    Spec("divisible-3-5", "3 va 5",
         "Natural son berilgan. U 3 ga ham, 5 ga ham bo'linsa `FizzBuzz`, faqat 3 ga bo'linsa `Fizz`, "
         "faqat 5 ga bo'linsa `Buzz`, aks holda sonning o'zini chiqaring.",
         "Yagona natural son $n$ ($1 \\le n \\le 10^9$).",
         "`FizzBuzz`, `Fizz`, `Buzz` yoki $n$.",
         lambda r: _lines(r.randint(1, 10**9) if r.random() < .4 else r.randint(1, 10**6) * r.choice([3, 5, 15])),
         lambda s: _lines("FizzBuzz" if int(s) % 15 == 0 else "Fizz" if int(s) % 3 == 0
                          else "Buzz" if int(s) % 5 == 0 else int(s)),
         ["15\n", "9\n", "7\n"], difficulty=Problem.Difficulty.EASY),

    Spec("grade", "Baho",
         "Talabaning balli (0 dan 100 gacha) berilgan. Bahoni aniqlang: "
         "$90$ va undan yuqori — `A`, $80$–$89$ — `B`, $70$–$79$ — `C`, $60$–$69$ — `D`, aks holda `F`.",
         "Yagona butun son $s$ ($0 \\le s \\le 100$).",
         "Bitta harf: `A`, `B`, `C`, `D` yoki `F`.",
         lambda r: _lines(r.randint(0, 100)),
         lambda s: _lines("A" if int(s) >= 90 else "B" if int(s) >= 80 else "C" if int(s) >= 70
                          else "D" if int(s) >= 60 else "F"),
         ["95\n", "61\n", "12\n"]),

    Spec("age-group", "Yosh toifasi",
         "Odamning yoshi berilgan. Toifasini aniqlang: $0$–$12$ — `Bola`, $13$–$17$ — `O'smir`, "
         "$18$–$59$ — `Katta`, $60$ va undan yuqori — `Keksa`.",
         "Yagona butun son $a$ ($0 \\le a \\le 120$).",
         "Toifa nomi.",
         lambda r: _lines(r.randint(0, 120)),
         lambda s: _lines("Bola" if int(s) <= 12 else "O'smir" if int(s) <= 17 else "Katta" if int(s) <= 59 else "Keksa"),
         ["10\n", "17\n", "64\n"]),

    Spec("quadrant", "Chorak",
         "Koordinata tekisligida nuqta berilgan. U qaysi chorakda yotishini (1, 2, 3 yoki 4) chiqaring. "
         "Nuqta o'qlardan birida yotsa `O'q` chiqaring.",
         "Ikki qatorda ikkita butun son $x$ va $y$ ($-1000 \\le x, y \\le 1000$).",
         "`1`, `2`, `3`, `4` yoki `O'q`.",
         lambda r: _lines(r.choice([0, r.randint(-1000, 1000)]), r.choice([0, r.randint(-1000, 1000)])),
         lambda s: _lines("O'q" if 0 in _ints(s) else 1 if _ints(s)[0] > 0 and _ints(s)[1] > 0
                          else 2 if _ints(s)[0] < 0 < _ints(s)[1] else 3 if _ints(s)[0] < 0 and _ints(s)[1] < 0 else 4),
         ["3\n4\n", "-2\n5\n", "0\n7\n"], difficulty=Problem.Difficulty.EASY),

    Spec("triangle", "Uchburchak mavjudmi",
         "Uchta kesma uzunligi berilgan. Ulardan uchburchak yasash mumkin bo'lsa `Ha`, aks holda `Yo'q` chiqaring. "
         "Har qanday ikki tomon yig'indisi uchinchisidan katta bo'lishi kerak.",
         "Uch qatorda uchta natural son $a$, $b$, $c$ ($1 \\le a, b, c \\le 10^9$).",
         "`Ha` yoki `Yo'q`.",
         lambda r: _lines(*(r.randint(1, 20) for _ in range(3))),
         lambda s: _lines(YES if (lambda a, b, c: a + b > c and a + c > b and b + c > a)(*_ints(s)) else NO),
         ["3\n4\n5\n", "1\n2\n3\n"], difficulty=Problem.Difficulty.EASY),

    Spec("square-or-rect", "Kvadrat yoki to'g'ri to'rtburchak",
         "To'g'ri to'rtburchakning ikki tomoni berilgan. U kvadrat bo'lsa `Kvadrat`, aks holda `To'g'ri to'rtburchak` chiqaring.",
         "Ikki qatorda ikkita natural son $a$ va $b$ ($1 \\le a, b \\le 10^9$).",
         "`Kvadrat` yoki `To'g'ri to'rtburchak`.",
         lambda r: _lines(*([r.randint(1, 10**9)] * 2 if r.random() < .4 else [r.randint(1, 100), r.randint(1, 100)])),
         lambda s: _lines("Kvadrat" if _ints(s)[0] == _ints(s)[1] else "To'g'ri to'rtburchak"),
         ["5\n5\n", "3\n7\n"]),

    Spec("days-in-month", "Oyda necha kun",
         "Oy raqami va yil berilgan. Shu oyda necha kun borligini chiqaring (fevral kabisa yilida 29 kun).",
         "Ikki qatorda ikkita butun son $m$ va $y$ ($1 \\le m \\le 12$, $1 \\le y \\le 9999$).",
         "Kunlar soni.",
         lambda r: _lines(r.randint(1, 12), r.randint(1, 9999)),
         lambda s: _lines([31, 29 if _is_leap(_ints(s)[1]) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][_ints(s)[0] - 1]),
         ["2\n2024\n", "4\n2023\n"], difficulty=Problem.Difficulty.EASY),

    Spec("vowel", "Unli yoki undosh",
         "Kichik lotin harflaridan iborat so'z berilgan. Uning birinchi harfi unli (`a`, `e`, `i`, `o`, `u`) bo'lsa "
         "`Unli`, aks holda `Undosh` chiqaring.",
         "Yagona so'z (uzunligi $1$ dan $20$ gacha, faqat kichik lotin harflari).",
         "`Unli` yoki `Undosh`.",
         lambda r: _lines("".join(r.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(r.randint(1, 20)))),
         lambda s: _lines("Unli" if s[0] in "aeiou" else "Undosh"),
         ["olma\n", "kitob\n"], tags=["if-else", "strings"]),

    Spec("discount", "Chegirma",
         "Xarid summasi berilgan. $100\\,000$ va undan yuqori bo'lsa $10\\%$, $50\\,000$ va undan yuqori bo'lsa $5\\%$ "
         "chegirma qilinadi, aks holda chegirma yo'q. To'lanadigan summani chiqaring.",
         "Yagona butun son $s$ ($0 \\le s \\le 10^9$, $s$ 100 ga karrali).",
         "To'lanadigan summa.",
         lambda r: _lines(r.randint(0, 2000) * 100),
         lambda s: _lines(int(s) - int(s) // 10 if int(s) >= 100_000 else int(s) - int(s) // 20 if int(s) >= 50_000 else int(s)),
         ["120000\n", "60000\n", "1000\n"], difficulty=Problem.Difficulty.EASY, tags=["if-else", "math"]),

    Spec("sort-three", "Uchta sonni tartiblash",
         "Uchta butun son berilgan. Ularni o'sish tartibida chiqaring. `sort` va `sorted` ishlatmang — faqat `if` bilan.",
         "Uch qatorda uchta butun son $a$, $b$, $c$ ($-10^9 \\le a, b, c \\le 10^9$).",
         "Bir qatorda uchta son o'sish tartibida.",
         lambda r: _lines(*(r.randint(-100, 100) for _ in range(3))),
         lambda s: _line(*sorted(_ints(s))),
         ["3\n1\n2\n", "7\n7\n1\n"], difficulty=Problem.Difficulty.MEDIUM),

    Spec("closest-to-zero", "Nolga eng yaqin",
         "Ikkita butun son berilgan. Qaysi biri nolga yaqinroq bo'lsa, shuni chiqaring. Masofalar teng bo'lsa kattasini chiqaring.",
         "Ikki qatorda ikkita butun son $a$ va $b$ ($-10^9 \\le a, b \\le 10^9$).",
         "Nolga eng yaqin son.",
         lambda r: _lines(r.randint(-100, 100), r.randint(-100, 100)),
         lambda s: _lines(max(_ints(s), key=lambda x: (-abs(x), x))),
         ["-3\n5\n", "-4\n4\n"], difficulty=Problem.Difficulty.MEDIUM),
]


# Hidden set for the teacher's own contest: same topics, last one is a step harder.
CONTEST_SPECS: list[Spec] = [
    Spec("c-sum-product", "Yig'indi va ko'paytma",
         "Ikkita butun son berilgan. Ularning yig'indisi va ko'paytmasini chiqaring.",
         "Ikki qatorda ikkita butun son $a$ va $b$ ($-10^4 \\le a, b \\le 10^4$).",
         "Bir qatorda ikkita son: yig'indi va ko'paytma.",
         lambda r: _lines(r.randint(-10**4, 10**4), r.randint(-10**4, 10**4)),
         lambda s: _line(sum(_ints(s)), _ints(s)[0] * _ints(s)[1]),
         ["3\n4\n", "-2\n5\n"], tags=["input-output", "math"], is_public=False),

    Spec("c-middle-digit", "O'rta raqam",
         "Uch xonali natural son berilgan. Uning o'rtadagi raqamini chiqaring.",
         "Yagona uch xonali son $n$ ($100 \\le n \\le 999$).",
         "O'rtadagi raqam.",
         lambda r: _lines(r.randint(100, 999)),
         lambda s: _lines(int(s) // 10 % 10),
         ["456\n", "907\n"], tags=["input-output", "math"], is_public=False),

    Spec("c-manhattan", "Ikki nuqta orasidagi yo'l",
         "Shahar ko'chalari to'r shaklida. $(x_1, y_1)$ dan $(x_2, y_2)$ ga faqat ko'cha bo'ylab (gorizontal yoki vertikal) "
         "yurish mumkin. Eng qisqa yo'l uzunligini toping.",
         "To'rt qatorda to'rtta butun son $x_1$, $y_1$, $x_2$, $y_2$ ($-10^6 \\le x_i, y_i \\le 10^6$).",
         "Yo'l uzunligi.",
         lambda r: _lines(*(r.randint(-10**6, 10**6) for _ in range(4))),
         lambda s: _lines(abs(_ints(s)[0] - _ints(s)[2]) + abs(_ints(s)[1] - _ints(s)[3])),
         ["1\n1\n4\n5\n", "-2\n3\n-2\n3\n"], tags=["math", "if-else"], is_public=False),

    Spec("c-time-of-day", "Kun qismi",
         "Soat va daqiqa berilgan. Soat $5$–$11$ bo'lsa — `Tong`, $12$–$16$ — `Kun`, $17$–$21$ — `Kech`, aks holda `Tun`. "
         "Daqiqa javobga ta'sir qilmaydi, u faqat vaqtni to'liq ko'rsatish uchun.",
         "Ikki qatorda ikkita butun son $h$ va $m$ ($0 \\le h \\le 23$, $0 \\le m \\le 59$).",
         "`Tong`, `Kun`, `Kech` yoki `Tun`.",
         lambda r: _lines(r.randint(0, 23), r.randint(0, 59)),
         lambda s: _lines("Tong" if 5 <= _ints(s)[0] <= 11 else "Kun" if 12 <= _ints(s)[0] <= 16
                          else "Kech" if 17 <= _ints(s)[0] <= 21 else "Tun"),
         ["7\n30\n", "23\n05\n"], is_public=False),

    Spec("c-ticket", "Chipta narxi",
         "Muzey chiptasi: 7 yoshgacha (7 dan kichik) — bepul, 7 dan 17 gacha (shu jumladan) — $5000$, "
         "60 va undan katta — $5000$, qolganlar — $10000$. Tashrif buyuruvchining yoshi berilgan. Narxni chiqaring.",
         "Yagona butun son $a$ ($0 \\le a \\le 120$).",
         "Chipta narxi (so'mda).",
         lambda r: _lines(r.randint(0, 120)),
         lambda s: _lines(0 if int(s) < 7 else 5000 if int(s) <= 17 or int(s) >= 60 else 10000),
         ["5\n", "17\n", "35\n"], difficulty=Problem.Difficulty.EASY, is_public=False),

    Spec("c-triangle-type", "Uchburchak turi",
         "Uchta tomon uzunligi berilgan. Uchburchak yasab bo'lmasa `Uchburchak emas`, uchala tomon teng bo'lsa "
         "`Teng tomonli`, ikkitasi teng bo'lsa `Teng yonli`, aks holda `Turli tomonli` chiqaring.",
         "Uch qatorda uchta natural son $a$, $b$, $c$ ($1 \\le a, b, c \\le 1000$).",
         "Uchburchak turi.",
         lambda r: _lines(*([r.randint(1, 30)] * 3 if r.random() < .15 else
                           (lambda x, y: [x, x, y])(r.randint(1, 30), r.randint(1, 30)) if r.random() < .4 else
                           [r.randint(1, 30) for _ in range(3)])),
         lambda s: _lines((lambda a, b, c: "Uchburchak emas" if a + b <= c or a + c <= b or b + c <= a
                           else "Teng tomonli" if a == b == c else "Teng yonli" if a == b or b == c or a == c
                           else "Turli tomonli")(*_ints(s))),
         ["3\n3\n3\n", "3\n3\n5\n", "1\n2\n3\n"], difficulty=Problem.Difficulty.EASY, is_public=False),

    Spec("c-queen", "Ferz",
         "Shaxmat taxtasida ferz $(x_1, y_1)$ katakda turibdi. U bir yurishda $(x_2, y_2)$ katakka yeta oladimi? "
         "Ferz gorizontal, vertikal va diagonal bo'ylab istalgan masofaga yuradi.",
         "To'rt qatorda to'rtta butun son $x_1$, $y_1$, $x_2$, $y_2$ ($1 \\le x_i, y_i \\le 8$), kataklar har xil.",
         "`Ha` yoki `Yo'q`.",
         lambda r: _lines(*(lambda a, b, c, d: (a, b, c, d) if (a, b) != (c, d) else (a, b, c % 8 + 1, d))(
             *(r.randint(1, 8) for _ in range(4)))),
         lambda s: _lines(YES if (lambda a, b, c, d: a == c or b == d or abs(a - c) == abs(b - d))(*_ints(s)) else NO),
         ["1\n1\n8\n8\n", "2\n3\n5\n7\n"], difficulty=Problem.Difficulty.MEDIUM, tags=["if-else", "math"], is_public=False),
]


class Command(BaseCommand):
    help = f"Create/refresh intro-course practice problems with {TESTS_PER_PROBLEM} tests each."

    def add_arguments(self, parser):
        parser.add_argument("--author", default=None, help="Username of the author (default: first staff user).")

    def handle(self, *args, **opts):
        author = (User.objects.get(username=opts["author"]) if opts["author"]
                  else User.objects.filter(is_staff=True).order_by("pk").first())
        if author is None:
            self.stderr.write("No staff user found; run `seed` first or pass --author.")
            return

        with transaction.atomic():
            for spec in SPECS + CONTEST_SPECS:
                problem, created = Problem.objects.update_or_create(slug=spec.slug, defaults=dict(
                    title=spec.title, statement_md=spec.statement, input_md=spec.input, output_md=spec.output,
                    difficulty=spec.difficulty, kind=Problem.Kind.CODE, author=author,
                    is_public=spec.is_public, status=Problem.Status.APPROVED,
                ))
                problem.tags.set([Tag.objects.get_or_create(name=t)[0] for t in spec.tags])
                problem.testcases.all().delete()
                TestCase.objects.bulk_create(_build_tests(problem, spec))
                self.stdout.write(f"{'created' if created else 'updated'} {spec.slug}{'' if spec.is_public else ' (hidden)'}")
        self.stdout.write(self.style.SUCCESS(
            f"{len(SPECS)} public + {len(CONTEST_SPECS)} hidden problems"))


def _build_tests(problem: Problem, spec: Spec) -> list[TestCase]:
    rng = random.Random(spec.slug)  # same slug -> same tests on every run
    inputs = list(spec.samples)
    seen = set(inputs)
    attempts = 0
    while len(inputs) < spec.tests:
        inp = spec.gen(rng)
        attempts += 1
        if inp not in seen:
            seen.add(inp)
            inputs.append(inp)
        elif attempts > 10_000:
            raise ValueError(f"{spec.slug}: input space too small for {spec.tests} unique tests")
    return [TestCase(problem=problem, input=inp, expected=spec.solve(inp),
                     is_sample=i < len(spec.samples), order=i) for i, inp in enumerate(inputs)]
