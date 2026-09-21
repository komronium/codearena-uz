"""Story problems for the if/else unit: every input value on its own line, each
tied to something real (taxi fare, electricity bill, exam pass...). 8 public +
7 hidden (for a contest), 25 tests each.

Separate from `seed_problems` so the two batches can be refreshed independently.
Re-running rebuilds this batch's statements and tests (matched by slug).
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User
from apps.problems.models import Problem, Tag, TestCase

from .seed_problems import NO, YES, Spec, _build_tests, _ints, _lines


# ---- batch 2: story problems, one value per line, 25 tests each ---------------
#
# Every input value sits on its own line: students practise reading several
# `input()` calls, not `split()`. Numbers stay integer so no float formatting.

def _story(gen, solve, *samples, **kw):
    kw.setdefault("tests", 25)
    return dict(gen=gen, solve=solve, samples=list(samples), **kw)


def _taxi(s):
    km, hour = _ints(s)
    return _lines(km * (4500 if hour >= 22 else 3000))


def _electricity(s):
    prev, cur = _ints(s)
    used = cur - prev
    return _lines(used * (450 if used <= 200 else 900))


def _walk_or_taxi(s):
    walk, wait, ride = _ints(s)
    taxi = wait + ride
    return _lines("Piyoda" if walk < taxi else "Taksi" if taxi < walk else "Farqi yo'q")


def _exam(s):
    a, b, c = _ints(s)
    return _lines("O'tdi" if min(a, b, c) >= 40 and a + b + c >= 165 else "O'tmadi")


def _password(s):
    pw, again = s.split()
    return _lines("Qisqa" if len(pw) < 8 else "Mos" if pw == again else "Mos emas")


def _parking(s):
    h = int(s)
    return _lines(0 if h <= 1 else 5000 * (h - 1))


def _weight(s):
    w, h = _ints(s)
    ideal = h - 100
    return _lines("Kam vazn" if w < ideal - 5 else "Ortiqcha vazn" if w > ideal + 5 else "Normal")


def _weather(s):
    t, rain = s.split()
    if rain == YES:
        return _lines("Soyabon")
    return _lines("Palto" if int(t) < 0 else "Kurtka" if int(t) < 15 else "Futbolka")


def _change(s):
    price, paid = _ints(s)
    return _lines("Yetarli emas" if paid < price else paid - price)


def _late(s):
    h, m = _ints(s)
    late = h * 60 + m - (8 * 60 + 30)
    return _lines("Vaqtida" if late <= 0 else late)


def _delivery(s):
    total, km = _ints(s)
    return _lines(total if total >= 200000 else total + 5000 + 1000 * km)


def _phone(s):
    used, limit = _ints(s)
    return _lines(30000 + max(used - limit, 0) * 200)


def _shop(s):
    price, qty = _ints(s)
    total = price * qty
    return _lines(total - total // 10 if qty >= 10 else total)


def _elevator(s):
    cur, target, kg = _ints(s)
    if kg > 400:
        return _lines("Ortiqcha yuk")
    if cur == target:
        return _lines("Joyida")
    return _lines(f"Yuqoriga {target - cur}" if target > cur else f"Pastga {cur - target}")


def _two_legs(s):
    a1, b1, a2, b2 = _ints(s)
    ta, tb = a1 + a2, b1 + b2
    return _lines("A" if ta > tb else "B" if tb > ta else "Penalti")


def _weight_gen(r):
    h = r.randint(150, 200)
    return _lines(h - 100 + r.randint(-25, 25), h)


def _taxi_gen(r):
    wait, ride = r.randint(0, 15), r.randint(3, 30)
    walk = wait + ride if r.random() < 0.15 else r.randint(5, 60)
    return _lines(walk, wait, ride)


_WORDS = ["salom", "parol", "python", "olma", "toshkent", "kod", "arena", "qwerty", "maktab", "dastur"]


def _pw_gen(r):
    pw = r.choice(_WORDS) + str(r.randint(1, 9999))
    if r.random() < 0.3:
        pw = pw[:r.randint(3, 7)]
    again = pw if r.random() < 0.5 else pw[:-1] + r.choice("0aZ!")
    return _lines(pw, again)


STORY_SPECS: list[Spec] = [
    Spec("taxi-fare", "Taksi haqi",
         "Toshkentda taksi 1 km uchun 3000 so'm oladi. Kechqurun soat 22 dan boshlab 1 km 4500 so'm. "
         "Sardor uyiga qaytishi uchun qancha to'laydi?",
         "Birinchi qatorda masofa $d$ km ($1 \\le d \\le 200$), ikkinchi qatorda safar boshlangan soat $h$ ($0 \\le h \\le 23$).",
         "Safar narxi so'mda.",
         **_story(lambda r: _lines(r.randint(1, 200), r.randint(0, 23)), _taxi, "10\n14\n", "4\n23\n"),
         tags=["if-else", "real-life"]),

    Spec("electricity-bill", "Elektr to'lovi",
         "Hisoblagich o'tgan oy va shu oy ko'rsatkichlari berilgan. Ishlatilgan kVt·soat 200 dan oshmasa har biri "
         "450 so'm, oshsa hammasi 900 so'mdan hisoblanadi. Oila necha so'm to'laydi?",
         "Birinchi qatorda o'tgan oy ko'rsatkichi $p$, ikkinchi qatorda shu oy ko'rsatkichi $c$ ($0 \\le p \\le c \\le 10^6$).",
         "To'lov summasi so'mda.",
         **_story(lambda r: (lambda p: _lines(p, p + r.randint(0, 500)))(r.randint(0, 10**5)), _electricity,
                  "1000\n1150\n", "500\n800\n"),
         tags=["if-else", "real-life", "math"]),

    Spec("walk-or-taxi", "Piyoda yoki taksi",
         "Aziz maktabga piyoda $a$ daqiqada yetib boradi. Taksi $w$ daqiqada keladi va yana $t$ daqiqa yuradi. "
         "Qaysi biri tezroq?",
         "Uch qatorda: piyoda vaqti $a$, taksini kutish $w$, taksida yurish $t$ (daqiqalarda, $0 \\le a, w, t \\le 60$).",
         "`Piyoda`, `Taksi` yoki vaqt teng bo'lsa `Farqi yo'q`.",
         **_story(_taxi_gen, _walk_or_taxi, "20\n5\n10\n", "12\n8\n10\n", "15\n5\n10\n"),
         tags=["if-else", "real-life"]),

    Spec("exam-pass", "Imtihon",
         "Talaba uchta fandan imtihon topshirdi. O'tish uchun har bir fandan kamida 40 ball va uchta ball "
         "yig'indisi kamida 165 bo'lishi kerak.",
         "Uch qatorda uchta ball $a$, $b$, $c$ ($0 \\le a, b, c \\le 100$).",
         "`O'tdi` yoki `O'tmadi`.",
         **_story(lambda r: _lines(*(r.randint(25, 100) for _ in range(3))), _exam, "60\n70\n45\n", "90\n90\n35\n"),
         tags=["if-else", "real-life"]),

    Spec("password-check", "Parolni tasdiqlash",
         "Ro'yxatdan o'tishda foydalanuvchi parolni ikki marta kiritadi. Parol 8 belgidan qisqa bo'lsa — `Qisqa`. "
         "Aks holda ikkalasi bir xil bo'lsa `Mos`, bo'lmasa `Mos emas`.",
         "Ikki qatorda ikkita parol (faqat harf va raqamlar, uzunligi 1 dan 30 gacha).",
         "`Qisqa`, `Mos` yoki `Mos emas`.",
         **_story(_pw_gen, _password, "python2024\npython2024\n", "olma1\nolma1\n", "toshkent99\ntoshkent98\n"),
         tags=["if-else", "strings"]),

    Spec("parking-fee", "Avtoturargoh",
         "Savdo markazi avtoturargohida birinchi soat bepul, keyingi har bir soat 5000 so'm. "
         "Mashina $h$ soat turdi. Qancha to'lanadi?",
         "Yagona butun son $h$ ($1 \\le h \\le 100$).",
         "To'lov so'mda.",
         **_story(lambda r: _lines(r.randint(1, 100)), _parking, "1\n", "3\n", "6\n"),
         tags=["if-else", "real-life"]),

    Spec("ideal-weight", "Ideal vazn",
         "Oddiy qoida: ideal vazn = bo'y (sm) − 100. Vazn ideal vazndan 5 kg dan ko'proq kam bo'lsa — `Kam vazn`, "
         "5 kg dan ko'proq ortiq bo'lsa — `Ortiqcha vazn`, aks holda `Normal`.",
         "Birinchi qatorda vazn $w$ kg, ikkinchi qatorda bo'y $h$ sm ($150 \\le h \\le 200$).",
         "Xulosa so'zi.",
         **_story(_weight_gen, _weight, "70\n175\n", "95\n170\n", "60\n180\n"),
         tags=["if-else", "real-life"]),

    Spec("weather-advice", "Nima kiyay?",
         "Ob-havo ilovasi maslahat beradi. Yomg'ir bo'lsa — `Soyabon`. Bo'lmasa harorat 0 dan past — `Palto`, "
         "15 dan past — `Kurtka`, aks holda `Futbolka`.",
         "Birinchi qatorda harorat $t$ ($-30 \\le t \\le 45$), ikkinchi qatorda yomg'ir bormi: `Ha` yoki `Yo'q`.",
         "Maslahat so'zi.",
         **_story(lambda r: _lines(r.randint(-30, 45), r.choice([YES, NO, NO])), _weather, "12\nYo'q\n", "25\nHa\n"),
         tags=["if-else", "strings"]),
]

STORY_CONTEST_SPECS: list[Spec] = [
    Spec("c2-change", "Qaytim",
         "Do'konda mahsulot narxi va xaridor bergan pul ma'lum. Pul yetmasa `Yetarli emas` deb chiqaring, "
         "yetsa qaytimni chiqaring.",
         "Birinchi qatorda narx $p$, ikkinchi qatorda berilgan pul $m$ ($1 \\le p, m \\le 10^7$).",
         "Qaytim yoki `Yetarli emas`.",
         **_story(lambda r: _lines(r.randint(1, 10**7), r.randint(1, 10**7)), _change, "15000\n20000\n", "50000\n45000\n"),
         tags=["if-else", "real-life"], is_public=False),

    Spec("c2-late", "Darsga kechikish",
         "Dars 08:30 da boshlanadi. Malika maktabga kelgan vaqt berilgan. Kechikmagan bo'lsa `Vaqtida`, "
         "kechikkan bo'lsa necha daqiqa kechikkanini chiqaring.",
         "Birinchi qatorda soat $h$ ($0 \\le h \\le 23$), ikkinchi qatorda daqiqa $m$ ($0 \\le m \\le 59$).",
         "`Vaqtida` yoki kechikish daqiqalari.",
         **_story(lambda r: _lines(r.randint(7, 10), r.randint(0, 59)), _late, "8\n20\n", "9\n5\n"),
         tags=["if-else", "real-life"], is_public=False),

    Spec("c2-delivery", "Yetkazib berish",
         "Onlayn do'kon 200 000 so'mdan boshlab bepul yetkazadi. Undan kam buyurtmaga 5000 so'm + har km uchun "
         "1000 so'm qo'shiladi. Xaridor jami qancha to'laydi?",
         "Birinchi qatorda buyurtma summasi $s$ ($1000 \\le s \\le 10^6$), ikkinchi qatorda masofa $k$ km ($1 \\le k \\le 50$).",
         "Jami to'lov.",
         **_story(lambda r: _lines(r.randint(1, 1000) * 1000, r.randint(1, 50)), _delivery, "150000\n3\n", "250000\n10\n"),
         tags=["if-else", "real-life"], is_public=False),

    Spec("c2-phone-plan", "Tarif rejasi",
         "Oylik tarif 30 000 so'm, unga $L$ daqiqa kiradi. Limitdan oshgan har daqiqa 200 so'm. "
         "Oy oxirida abonent qancha to'laydi?",
         "Birinchi qatorda gaplashilgan daqiqalar $u$ ($0 \\le u \\le 5000$), ikkinchi qatorda limit $L$ ($0 \\le L \\le 3000$).",
         "To'lov so'mda.",
         **_story(lambda r: _lines(r.randint(0, 5000), r.choice([300, 500, 1000, 2000, 3000])), _phone, "250\n300\n", "650\n500\n"),
         tags=["if-else", "real-life"], is_public=False),

    Spec("c2-shop-discount", "Ulgurji chegirma",
         "Do'kon 10 dona va undan ko'p olganda umumiy summadan 10% chegirma beradi. Xaridor qancha to'laydi?",
         "Birinchi qatorda dona narxi $p$ ($100 \\le p \\le 10^6$, 100 ga karrali), ikkinchi qatorda soni $q$ ($1 \\le q \\le 100$).",
         "To'lov summasi.",
         **_story(lambda r: _lines(r.randint(1, 10**4) * 100, r.randint(1, 100)), _shop,
                  "12000\n10\n", "12000\n3\n"),
         tags=["if-else", "real-life", "math"], is_public=False),

    Spec("c2-elevator", "Lift",
         "Lift eng ko'pi 400 kg ko'taradi. Yuk ortiq bo'lsa `Ortiqcha yuk`. Boriladigan qavat hozirgi qavat bilan "
         "bir xil bo'lsa `Joyida`. Aks holda yo'nalish va necha qavat yurishini chiqaring: `Yuqoriga 5` yoki `Pastga 3`.",
         "Uch qatorda: hozirgi qavat $a$, boriladigan qavat $b$ ($1 \\le a, b \\le 30$), yuk $w$ kg ($1 \\le w \\le 700$).",
         "Yuqoridagi uch variantdan biri.",
         **_story(lambda r: _lines(r.randint(1, 30), r.randint(1, 30), r.randint(1, 700)), _elevator,
                  "3\n8\n250\n", "10\n10\n120\n", "5\n2\n450\n"),
         difficulty=Problem.Difficulty.EASY, tags=["if-else", "real-life"], is_public=False),

    Spec("c2-two-legs", "Ikki o'yin",
         "Kubok bosqichida A va B jamoalari ikki marta o'ynaydi. Ikki o'yinda jami ko'proq gol urgan jamoa "
         "keyingi bosqichga o'tadi. Teng bo'lsa `Penalti`.",
         "To'rt qatorda: 1-o'yinda A gollari, 1-o'yinda B gollari, 2-o'yinda A gollari, 2-o'yinda B gollari "
         "(har biri 0 dan 9 gacha).",
         "`A`, `B` yoki `Penalti`.",
         **_story(lambda r: _lines(*(r.randint(0, 4) for _ in range(4))), _two_legs,
                  "2\n1\n1\n1\n", "1\n1\n2\n2\n", "0\n2\n1\n0\n"),
         difficulty=Problem.Difficulty.EASY, tags=["if-else", "real-life"], is_public=False),
]


class Command(BaseCommand):
    help = "Create/refresh the story-problem batch (matched by slug)."

    def add_arguments(self, parser):
        parser.add_argument("--author", default=None, help="Username of the author (default: first staff user).")

    def handle(self, *args, **opts):
        author = (User.objects.get(username=opts["author"]) if opts["author"]
                  else User.objects.filter(is_staff=True).order_by("pk").first())
        if author is None:
            self.stderr.write("No staff user found; run `seed` first or pass --author.")
            return

        with transaction.atomic():
            for spec in STORY_SPECS + STORY_CONTEST_SPECS:
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
            f"{len(STORY_SPECS)} public + {len(STORY_CONTEST_SPECS)} hidden story problems"))
