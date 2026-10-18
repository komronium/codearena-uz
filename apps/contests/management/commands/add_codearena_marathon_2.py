"""CodeArena Marathon #2: a rated round with a personal clock, scored by Codeforces rules (the worth falls with the person's own
minutes, every wrong try costs 50, never below 30%). The round stays open for days, but whoever enters
presses "Boshlash" and has 120 minutes from then (Contest.personal_minutes). Eight hidden problems in the style of Round #6 (short
everyday stories, small inputs, one small trap each): two very easy Beginner (A, B), two Beginner (C, D), three Easy
(E beginner-easy, F, G easy-medium) and one deciding Medium (H) that looks like a story about lamps but is an invariant
puzzle. None repeats a problem already on the portal.

Every expected output comes from a reference solution here, never typed by hand. Safe to re-run: problems that
already exist (by slug) are reused, not duplicated.

    python manage.py add_codearena_marathon_2 --start "2026-10-19 08:00" --end "2026-10-21 20:00" [--minutes 120]
        [--author admin] [--dry-run]
"""
from datetime import datetime
from math import gcd

from django.contrib.auth import get_user_model
from django.core.management.base import CommandError
from django.db import transaction
from django.utils import timezone

from apps.contests.management.commands.add_codearena_marathon_1 import _arr, _size, _uniq
from apps.contests.management.commands.add_weekend_contest_1 import Command as WeekendCommand, _lines
from apps.contests.models import Contest

TITLE = "CodeArena Marathon #2"
BADGE = "Marathon #2"
DESCRIPTION = """**Marafon #2: 8 ta masala, sizga 120 daqiqa.** Musobaqa bir necha kun ochiq, lekin vaqtingiz — **«Boshlash» tugmasini bosgan paytdan 120 daqiqa**. Qulay paytda boshlang, soat to‘xtamaydi va qayta boshlanmaydi.

- **Reytingli**: natija reytingingizga ta’sir qiladi. Reyting musobaqa tugagach hisoblanadi.
- Masalalar «Boshlash»dan keyin ochiladi. Natijalar jadvali musobaqa tugagach ochiladi: hamma o‘z vaqtida boshlaydi, shuning uchun boshqalarning natijasi oldindan ko‘rinmaydi.
- **Codeforces qoidasi**: masala bahosi sizning soatingiz o‘tishi bilan kamayadi (120 daqiqa oxirida taxminan yarmigacha), har bir noto‘g‘ri urinish **−50 ball**, lekin baho boshlang‘ich bahoning 30% idan pastga tushmaydi. Vaqt «Boshlash»dan hisoblanadi. Birinchi testda xato qilish jarima bermaydi.
- **Nishon**: kamida bitta masala yechgan har bir ishtirokchi profiliga «Marathon #2» nishoni qo‘shiladi, birinchi uchtalikka — medal.
- Halollik qoidalari amal qiladi: kod o‘zingizniki bo‘lsin; masalalarni va yechimlarni boshqalarga yubormang, AI yoki boshqa birovning yechimi taqiqlanadi. Shubhali yechimlar diskvalifikatsiyaga olinadi."""


# ---- A. Juda oson: qadamlar --------------------------------------------------------------
def steps_solve(inp):
    a, b, d = map(int, inp.split())
    return _lines((a + b) * d)


def steps_tests(rng):
    tests = ["3000 4000 7", "0 5000 30", "0 0 1", "20000 20000 365", "1 1 1", "20000 0 100", "0 20000 365",
             "1234 5678 90", "10000 10000 31", "500 0 1"]
    for _ in range(14):
        tests.append(f"{rng.choice([0, rng.randint(0, 20000)])} {rng.randint(0, 20000)} {rng.randint(1, 365)}")
    return _uniq(tests)


# ---- B. Juda oson: baho ------------------------------------------------------------------
def grade_solve(inp):
    s = int(inp)
    return _lines(5 if s >= 86 else 4 if s >= 71 else 3 if s >= 56 else 2)


def grade_tests(rng):
    tests = ["90", "55", "0", "100", "56", "70", "71", "85", "86", "87", "69", "72", "54", "1", "99", "60", "80"]
    tests += [str(rng.randint(0, 100)) for _ in range(8)]
    return _uniq(tests)


# ---- C. Beginner: bir xil harorat --------------------------------------------------------
def same_solve(inp):
    lines = inp.split("\n")
    t = list(map(int, lines[1].split()))
    return _lines(sum(1 for i in range(1, len(t)) if t[i] == t[i - 1]))


def same_tests(rng):
    def case(t):
        return f"{len(t)}\n{_arr(t)}"
    tests = [case([20, 20, 21, 21, 21, 19]), case([5]), case([7, 7]), case([7, 8]), case([3] * 100),
             case([1, 2] * 50), case([-5, -5, -5, 0, 0, -5]), case([0, 0, 0]), case([-50, 50, -50, 50]),
             case([10, 11, 11, 10, 10, 10, 9])]
    for _ in range(14):
        n = rng.choice([rng.randint(1, 10), rng.randint(1, 100), 100])
        span = rng.choice([1, 2, 5, 50])
        tests.append(case([rng.randint(-span, span) for _ in range(n)]))
    return _uniq(tests)


# ---- D. Beginner: eng uzun yomg'ir -------------------------------------------------------
def rain_solve(inp):
    lines = inp.split("\n")
    best = run = 0
    for x in map(int, lines[1].split()):
        run = run + 1 if x > 0 else 0
        best = max(best, run)
    return _lines(best)


def rain_tests(rng):
    def case(r):
        return f"{len(r)}\n{_arr(r)}"
    tests = [case([0, 4, 9, 0, 2, 7, 1, 0]), case([0, 0, 0, 0]), case([5]), case([0]), case([1] * 100),
             case([0] * 100), case([3, 0, 3, 0, 3]), case([0, 1, 1, 1]), case([1, 1, 1, 0]),
             case([2, 2, 0, 5, 5, 5, 0, 1]), case([200, 0, 200, 200])]
    for _ in range(14):
        n = rng.choice([rng.randint(1, 10), rng.randint(1, 100), 100])
        rain = rng.choice([0.2, 0.5, 0.8])
        tests.append(case([rng.randint(1, 200) if rng.random() < rain else 0 for _ in range(n)]))
    return _uniq(tests)


# ---- E. Easy (beginner-easy): kitob ------------------------------------------------------
def book_solve(inp):
    n, a = map(int, inp.split())
    days = (n + a - 1) // a  # reading days needed
    return _lines(days + (days - 1) // 2)  # the 3rd, 6th, 9th... calendar day is a rest day


def book_tests(rng):
    tests = ["10 4", "5 5", "1 1", "1000000000 1", "1000000000 1000000000", "7 3", "6 3", "9 3", "12 4", "13 4",
             "2 1", "3 1", "4 1", "5 1", "1000000000 2", "999999999 1", "1000000000 3", "100 7", "100 100", "99 100"]
    for _ in range(8):
        n = rng.choice([rng.randint(1, 100), rng.randint(1, 10**5), rng.randint(1, 10**9)])
        a = rng.choice([rng.randint(1, 10), rng.randint(1, 1000), rng.randint(1, 10**9)])
        tests.append(f"{n} {a}")
    return _uniq(tests)


# ---- F. Easy: bank navbati ---------------------------------------------------------------
def queue_solve(inp):
    lines = inp.split("\n")
    n, limit = map(int, lines[0].split())
    served = used = 0
    for t in map(int, lines[1].split()):
        if used + t > limit:
            break  # nobody behind may skip ahead
        used += t
        served += 1
    return _lines(f"{served} {used}")


def queue_tests(rng):
    def case(limit, t):
        return f"{len(t)} {limit}\n{_arr(t)}"
    tests = [case(20, [5, 7, 6, 3, 9]), case(5, [6, 1, 1]), case(10, [10]), case(9, [10]), case(10, [4, 6, 1]),
             case(10, [4, 6]), case(1, [1]), case(10**9, [10**4] * 10**5), case(10**8, [10**4] * 10**5),
             case(15, [5, 20, 1, 1]), case(7, [3, 3, 3, 1])]
    for _ in range(14):
        n = _size(rng, 8, 500, 10**5)
        t = [rng.randint(1, rng.choice([5, 100, 10**4])) for _ in range(n)]
        limit = rng.choice([rng.randint(1, max(1, sum(t))), sum(t), sum(t) // 2 + 1, rng.randint(1, 30)])
        tests.append(case(limit, t))
    return _uniq(tests)


# ---- G. Easy-medium: ikki avtobus (64-bit) -----------------------------------------------
def buses_solve(inp):
    a, b, t = map(int, inp.split())
    return _lines(t // (a // gcd(a, b) * b) + 1)  # together at minute 0, then every lcm(a, b) minutes


def buses_tests(rng):
    tests = ["4 6 25", "5 7 30", "1 1 1", "1 1 10", "6 6 60", "6 6 59", "999983 999979 10000000000",
             "1000000 999999 1000000000000", "1000000 1000000 1000000000000", "12 18 36", "12 18 35", "2 4 8",
             "3 5 14", "3 5 15", "3 5 16", "999999 1000000 999999999999", "999999 1000000 999998000001",
             "999999 1000000 999998000000", "7 1 7", "1 7 6"]
    for _ in range(8):
        a, b = rng.randint(1, 10**6), rng.randint(1, 10**6)
        tests.append(f"{a} {b} {rng.choice([rng.randint(1, 10**4), rng.randint(1, 10**9), rng.randint(1, 10**12)])}")
    return _uniq(tests)


# ---- H. Medium (hal qiluvchi): chiroqlar -------------------------------------------------
def lamps_solve(inp):
    lines = inp.split("\n")
    n, s = int(lines[0]), lines[1].strip()
    if n < 3:
        return _lines("YES" if "0" not in s else "NO")  # no move exists
    # a move switches one lamp of each class (position mod 3), so the three classes' "off" counts change parity together
    parity = [0, 0, 0]
    for i, ch in enumerate(s, start=1):
        if ch == "0":
            parity[i % 3] ^= 1
    return _lines("YES" if parity[0] == parity[1] == parity[2] else "NO")


def lamps_tests(rng):
    def case(s):
        return f"{len(s)}\n{s}"

    def reachable(n):
        s = [1] * n
        for _ in range(rng.randint(0, 3 * n)):
            i = rng.randint(0, max(0, n - 3))
            for j in range(i, min(n, i + 3)):
                s[j] ^= 1
        return s

    def text(bits):
        return "".join(map(str, bits))

    tests = [case("10001"), case("11011"), case("1"), case("0"), case("11"), case("10"), case("111"), case("000"),
             case("100"), case("110"), case("1111"), case("0000"), case("1001"), case("0110"), case("00000"),
             case("11111"), case("01110"), case("1" * 2 * 10**5), case("0" * 2 * 10**5),
             case("1" * (2 * 10**5 - 1) + "0")]
    for _ in range(10):
        n = _size(rng, 12, 3000, 2 * 10**5)
        bits = reachable(n) if n >= 3 else [1] * n
        tests.append(case(text(bits)))
        wrong = list(bits)
        wrong[rng.randrange(n)] ^= 1  # one lamp switched by hand: the parities no longer agree
        tests.append(case(text(wrong)))
    return _uniq(tests)


PROBLEMS = [
    {
        "slug": "cam2-qadamlar", "title": "Qadamlar", "difficulty": "beginner", "points": 200,
        "tags": ["input-output", "arithmetic"], "solve": steps_solve, "tests": steps_tests, "samples": 2,
        "statement": ("Sardor sog‘lom turmush tarziga o‘tdi: har kuni ertalab $a$ qadam, kechqurun $b$ qadam yuradi.\n\n"
                      "U $d$ kun shunday yursa, jami necha qadam yuradi?"),
        "input": "Bitta qatorda uchta butun son: $a$, $b$ va $d$ ($0 \\le a, b \\le 20000$, $1 \\le d \\le 365$).",
        "output": "Bitta butun son: jami qadamlar soni.",
    },
    {
        "slug": "cam2-baho", "title": "Baho", "difficulty": "beginner", "points": 200,
        "tags": ["conditionals"], "solve": grade_solve, "tests": grade_tests, "samples": 2,
        "statement": ("Maktabda imtihon $100$ ballik tizimda baholanadi:\n\n"
                      "- $86$ dan $100$ gacha — baho `5`\n"
                      "- $71$ dan $85$ gacha — baho `4`\n"
                      "- $56$ dan $70$ gacha — baho `3`\n"
                      "- $0$ dan $55$ gacha — baho `2`\n\n"
                      "O‘quvchi $s$ ball to‘pladi. Uning bahosi nechchi?"),
        "input": "Bitta qatorda butun son $s$ ($0 \\le s \\le 100$).",
        "output": "Bitta butun son: baho ($2$, $3$, $4$ yoki $5$).",
    },
    {
        "slug": "cam2-bir-xil-harorat", "title": "Bir xil harorat", "difficulty": "beginner", "points": 250,
        "tags": ["arrays", "for-loop"], "solve": same_solve, "tests": same_tests, "samples": 2,
        "statement": ("Meteorolog $n$ kun ketma-ket havo haroratini yozib bordi.\n\n"
                      "Nechta kunning harorati **avvalgi kundagi harorat bilan aynan bir xil** bo‘lgan? "
                      "Birinchi kunning avvalgi kuni yo‘q, shuning uchun u hisoblanmaydi."),
        "input": ("* Birinchi qatorda kunlar soni $n$ ($1 \\le n \\le 100$) beriladi.\n"
                  "* Ikkinchi qatorda $n$ ta butun son $t_1, \\ldots, t_n$ ($|t_i| \\le 50$) bo‘shliq bilan ajratilgan "
                  "holda beriladi."),
        "output": "Bitta butun son: avvalgi kun bilan harorati bir xil bo‘lgan kunlar soni.",
    },
    {
        "slug": "cam2-eng-uzun-yomgir", "title": "Eng uzun yomg‘ir", "difficulty": "beginner", "points": 250,
        "tags": ["arrays", "for-loop"], "solve": rain_solve, "tests": rain_tests, "samples": 2,
        "statement": ("Fermer $n$ kun davomida yog‘gan yomg‘ir miqdorini (millimetrda) yozib bordi. Yomg‘ir miqdori "
                      "$0$ dan katta bo‘lgan kun **yomg‘irli** hisoblanadi.\n\n"
                      "Ketma-ket yomg‘irli kunlarning eng uzun seriyasi necha kun davom etgan? Yomg‘irli kun "
                      "bo‘lmasa, javob $0$."),
        "input": ("* Birinchi qatorda kunlar soni $n$ ($1 \\le n \\le 100$) beriladi.\n"
                  "* Ikkinchi qatorda $n$ ta butun son $r_1, \\ldots, r_n$ ($0 \\le r_i \\le 200$) bo‘shliq bilan "
                  "ajratilgan holda beriladi."),
        "output": "Bitta butun son: ketma-ket yomg‘irli kunlarning eng uzun seriyasi.",
    },
    {
        "slug": "cam2-kitob", "title": "Kitob", "difficulty": "easy", "points": 400,
        "tags": ["arithmetic", "math"], "solve": book_solve, "tests": book_tests, "samples": 2,
        "statement": ("Aziza $n$ betlik kitob o‘qimoqchi. U har kuni aynan $a$ bet o‘qiydi, faqat **har uchinchi kuni** "
                      "(3-, 6-, 9-, ... kunlar) dam oladi va o‘sha kuni umuman o‘qimaydi.\n\n"
                      "Oxirgi o‘qiladigan kuni kitobda $a$ betdan kam qolgan bo‘lsa, qolganini o‘qib tugatadi. "
                      "Aziza kitobni nechanchi kuni o‘qib tugatadi?"),
        "input": "Bitta qatorda ikkita butun son: $n$ va $a$ ($1 \\le n, a \\le 10^9$).",
        "output": "Bitta butun son: Aziza kitobni o‘qib tugatadigan kun raqami (kunlar $1$ dan boshlab sanaladi).",
    },
    {
        "slug": "cam2-bank-navbati", "title": "Bank navbati", "difficulty": "easy", "points": 500,
        "tags": ["arrays", "simulation"], "solve": queue_solve, "tests": queue_tests, "samples": 2,
        "statement": ("Bankda navbat bor: $n$ ta mijoz, $i$-mijozga xizmat ko‘rsatish $t_i$ daqiqa oladi. Xodim "
                      "mijozlarga navbat tartibida, birin-ketin xizmat ko‘rsatadi va bank ish vaqti tugaguncha "
                      "faqat $T$ daqiqa qoldi.\n\n"
                      "Mijozga xizmat boshlansa, u to‘liq tugatilishi kerak: ish vaqti tugab qolsa, xodim uni "
                      "boshlamaydi. **Navbatdan chiqib ketib bo‘lmaydi**: biror mijozga ulgurilmasa, undan keyingilarga "
                      "ham xizmat ko‘rsatilmaydi (ularga vaqt yetadigan bo‘lsa ham).\n\n"
                      "Nechta mijozga xizmat ko‘rsatiladi va buning uchun jami necha daqiqa ketadi?"),
        "input": ("* Birinchi qatorda $n$ va $T$ ($1 \\le n \\le 10^5$, $1 \\le T \\le 10^9$) beriladi.\n"
                  "* Ikkinchi qatorda $n$ ta butun son $t_1, \\ldots, t_n$ ($1 \\le t_i \\le 10^4$) bo‘shliq bilan "
                  "ajratilgan holda beriladi."),
        "output": "Bitta qatorda ikkita son: xizmat ko‘rsatilgan mijozlar soni va sarflangan jami daqiqalar.",
    },
    {
        "slug": "cam2-ikki-avtobus", "title": "Ikki avtobus", "difficulty": "easy", "points": 650,
        "tags": ["math", "gcd"], "solve": buses_solve, "tests": buses_tests, "samples": 2,
        "statement": ("Avtoparkdan ikki yo‘nalishdagi avtobuslar chiqadi. Ikkalasi ham $0$-daqiqada birga chiqadi. "
                      "Keyin birinchi yo‘nalish har $a$ daqiqada, ikkinchisi har $b$ daqiqada yana chiqadi.\n\n"
                      "$0$-daqiqadan $T$-daqiqagacha (ikkala chegara ham kiradi) ikkala avtobus **aynan bir daqiqada** "
                      "necha marta chiqadi? $0$-daqiqa ham hisobga kiradi."),
        "input": ("Bitta qatorda uchta butun son: $a$, $b$ va $T$ ($1 \\le a, b \\le 10^6$, $1 \\le T \\le 10^{12}$)."),
        "output": "Bitta butun son: avtobuslar birga chiqadigan daqiqalar soni.",
    },
    {
        "slug": "cam2-chiroqlar", "title": "Chiroqlar", "difficulty": "medium", "points": 1000,
        "tl_ms": 1000, "tags": ["math", "constructive"], "solve": lamps_solve, "tests": lamps_tests, "samples": 2,
        "statement": ("Katta zalda $n$ ta chiroq bir qatorda turibdi. Ba’zilari yonib turibdi, ba’zilari o‘chiq. "
                      "Navbatchi zalni to‘liq yoritmoqchi: **hamma chiroq yonib turishi** kerak.\n\n"
                      "Pult bilan faqat bitta ish qilish mumkin: **ketma-ket turgan uchta chiroqni** tanlab, ularning "
                      "uchalasining holatini almashtirish (yonig‘i o‘chadi, o‘chig‘i yonadi). Bu ishni istagancha "
                      "marta, istalgan joyda takrorlash mumkin. Ikkita yoki bitta chiroqni alohida o‘zgartirib "
                      "bo‘lmaydi.\n\n"
                      "Navbatchi hamma chiroqni yondira oladimi?"),
        "input": ("* Birinchi qatorda chiroqlar soni $n$ ($1 \\le n \\le 2 \\cdot 10^5$) beriladi.\n"
                  "* Ikkinchi qatorda uzunligi $n$ bo‘lgan satr: $i$-belgi `1` bo‘lsa $i$-chiroq yonib turibdi, "
                  "`0` bo‘lsa o‘chiq."),
        "output": "Hamma chiroqni yondirish mumkin bo‘lsa `YES`, aks holda `NO` chiqaring.",
    },
]


class Command(WeekendCommand):
    help = "Creates CodeArena Marathon #2 (rated, 120-minute personal clock) if needed and attaches its 8 problems (hidden) as A..H."
    ml_mb = 256

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.set_defaults(contest=TITLE)
        parser.add_argument("--start", default=None, help='Opens, Tashkent time: "2026-10-19 08:00" (new contest)')
        parser.add_argument("--end", default=None, help='Closes, Tashkent time: "2026-10-21 20:00" (new contest)')
        parser.add_argument("--minutes", type=int, default=120, help="Each participant's own time (new contest)")

    def _when(self, text, name):
        try:
            return timezone.make_aware(datetime.strptime(text, "%Y-%m-%d %H:%M"))
        except (TypeError, ValueError):
            raise CommandError(f'{name} "YYYY-MM-DD HH:MM" ko‘rinishida bo‘lsin.')

    def handle(self, *args, **opts):
        User = get_user_model()
        author = (User.objects.filter(username=opts["author"]).first() if opts["author"]
                  else User.objects.filter(is_superuser=True).order_by("pk").first())
        if author is None:
            raise CommandError("Muallif topilmadi — --author bilan mavjud login bering.")

        with transaction.atomic():
            contest = Contest.objects.filter(title__iexact=opts["contest"]).first()
            if contest is None:
                if not (opts["start"] and opts["end"]):
                    raise CommandError("Musobaqa hali yo'q: --start va --end bering.")
                start, end = self._when(opts["start"], "--start"), self._when(opts["end"], "--end")
                if end <= start:
                    raise CommandError("Tugash vaqti boshlanishdan keyin bo‘lsin.")
                if start <= timezone.now():
                    raise CommandError("Boshlanish vaqti o'tib ketgan.")
                contest = Contest.objects.create(
                    title=opts["contest"], description_md=DESCRIPTION, start=start, end=end,
                    type=Contest.Type.CF, is_rated=True, personal_minutes=opts["minutes"],
                    division=Contest.Division.OPEN, badge=BADGE)
                self.stdout.write(f"«{contest.title}» yaratildi: {timezone.localtime(contest.start):%d.%m.%Y %H:%M} — "
                                  f"{timezone.localtime(contest.end):%d.%m.%Y %H:%M}, reytingli, "
                                  f"har kimga {contest.personal_minutes} daqiqa.")
            elif contest.start <= timezone.now() and not opts["force"]:
                raise CommandError("Musobaqa allaqachon boshlangan. Baribir ulash uchun --force qo'shing.")
            else:  # a re-run before the start: the rules text and the personal clock follow this file
                contest.description_md, contest.personal_minutes, contest.badge = DESCRIPTION, opts["minutes"], BADGE
                contest.type = Contest.Type.CF
                contest.save(update_fields=["description_md", "personal_minutes", "badge", "type"])

            self._drop_old(contest, PROBLEMS, "cam2-")
            taken = set(contest.contest_problems.values_list("label", flat=True))
            for i, spec in enumerate(PROBLEMS):
                self._add(contest, spec, "ABCDEFGHIJ"[i], i, author, taken)
            for spec in PROBLEMS:  # a re-run keeps the worth of problems already attached in step with this file
                contest.contest_problems.filter(problem__slug=spec["slug"]).update(points=spec["points"])
            if opts["dry_run"]:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("Dry run — hech narsa saqlanmadi."))
                return
        self.stdout.write(self.style.SUCCESS(
            f"Tayyor: «{contest.title}» da {contest.contest_problems.count()} ta masala. "
            "Masalalar yashirin; musobaqa tugagach Boshqaruv → Musobaqalar → «Masalalarni ochish»."))
