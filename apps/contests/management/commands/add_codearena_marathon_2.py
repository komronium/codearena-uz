"""CodeArena Marathon #2: a rated round with a personal clock. The round stays open for days, but whoever enters
presses "Boshlash" and has 120 minutes from then (Contest.personal_minutes). Six hidden problems on one theme, a
warehouse, from a first-week Beginner (A, B) to one Hard one (F): a parcel tariff, values that occur once, range sums
(64-bit), the shortest window with a given sum, the fewest removals to make a sequence increase, and the cheapest
roads that connect every city. None repeats a problem already on the portal.

Every expected output comes from a reference solution here, never typed by hand. Safe to re-run: problems that
already exist (by slug) are reused, not duplicated.

    python manage.py add_codearena_marathon_2 --start "2026-10-19 08:00" --end "2026-10-21 20:00" [--minutes 120]
        [--author admin] [--dry-run]
"""
import heapq
from bisect import bisect_left
from collections import Counter
from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import CommandError
from django.db import transaction
from django.utils import timezone

from apps.contests.management.commands.add_codearena_marathon_1 import _arr, _size, _uniq
from apps.contests.management.commands.add_weekend_contest_1 import Command as WeekendCommand, _lines
from apps.contests.models import Contest

TITLE = "CodeArena Marathon #2"
BADGE = "Marathon #2"
DESCRIPTION = """**Marafon #2: 6 ta masala, sizga 120 daqiqa.** Musobaqa bir necha kun ochiq, lekin vaqtingiz — **«Boshlash» tugmasini bosgan paytdan 120 daqiqa**. Qulay paytda boshlang, soat to‘xtamaydi va qayta boshlanmaydi.

- **Reytingli**: natija reytingingizga ta’sir qiladi. Reyting musobaqa tugagach hisoblanadi.
- Masalalar «Boshlash»dan keyin ochiladi. Natijalar jadvali musobaqa tugagach ochiladi: hamma o‘z vaqtida boshlaydi, shuning uchun boshqalarning natijasi oldindan ko‘rinmaydi.
- Har bir to‘liq yechilgan masala uchun uning bali; ball teng bo‘lsa, jarimasi kam bo‘lgan yuqorida. Jarima sizning boshlagan paytingizdan hisoblanadi.
- **Nishon**: kamida bitta masala yechgan har bir ishtirokchi profiliga «Marathon #2» nishoni qo‘shiladi, birinchi uchtalikka — medal.
- Halollik qoidalari amal qiladi: kod o‘zingizniki bo‘lsin; masalalarni va yechimlarni boshqalarga yubormang, AI yoki boshqa birovning yechimi taqiqlanadi. Shubhali yechimlar diskvalifikatsiyaga olinadi."""


# ---- A. Beginner: yetkazib berish narxi --------------------------------------------------
def ship_solve(inp):
    w, a, b = map(int, inp.split())
    return _lines(a if w <= 1000 else a + ((w - 1000 + 499) // 500) * b)


def ship_tests(rng):
    tests = ["1500 3000 800", "2300 3000 800", "1 1 1", "1000 5 7", "1001 5 7", "1500 5 7", "1501 5 7", "2000 5 7",
             "10 1000000000 1000000000", "1000000000 1000000000 1000000000", "999999999 1000000000 1000000000",
             "1000000000 1 1", "1000 1000000000 1", "1001 1 1000000000", "2500 100 30", "1999 100 30", "2001 100 30"]
    for _ in range(10):
        w = rng.choice([rng.randint(1, 1000), rng.randint(1000, 5000), rng.randint(1, 10**9)])
        tests.append(f"{w} {rng.randint(1, 10**4)} {rng.randint(1, 10**4)}")
    for _ in range(3):
        tests.append(f"{rng.randint(10**8, 10**9)} {rng.randint(10**8, 10**9)} {rng.randint(10**8, 10**9)}")
    return _uniq(tests)


# ---- B. Beginner: bir marta uchraydiganlar -----------------------------------------------
def once_solve(inp):
    lines = inp.split("\n")
    a = list(map(int, lines[1].split()))
    count = Counter(a)
    result = [x for x in dict.fromkeys(a) if count[x] == 1]
    return _lines(0) if not result else _lines(len(result), _arr(result))


def once_tests(rng):
    def case(a):
        return f"{len(a)}\n{_arr(a)}"
    tests = [case([4, 7, 4, 9, 7, 1]), case([3, 3, 3]), case([5]), case([1, 2, 3, 4]), case([-1, 1, -1, 1]),
             case([0, 0, 1]), case([10**9, -10**9, 10**9]), case([2, 1, 2, 1, 3]), case(list(range(1, 2001))),
             case([7] * 1000 + [8])]
    for _ in range(12):
        n = _size(rng, 8, 300, 2 * 10**5)
        hi = rng.choice([3, 10, n, 10**9])
        tests.append(case([rng.randint(-hi, hi) for _ in range(n)]))
    return _uniq(tests)


# ---- C. Easy: savdo hisoboti (64-bit yig'indilar) ----------------------------------------
def sales_solve(inp):
    lines = inp.split("\n")
    n, q = map(int, lines[0].split())
    pre = [0]
    for x in map(int, lines[1].split()):
        pre.append(pre[-1] + x)
    out = []
    for line in lines[2:2 + q]:
        l, r = map(int, line.split())
        out.append(pre[r] - pre[l - 1])
    return _lines(*out)


def sales_tests(rng):
    def case(a, queries):
        return f"{len(a)} {len(queries)}\n{_arr(a)}\n" + "\n".join(f"{l} {r}" for l, r in queries)
    tests = [case([5, 3, 8, 2, 7], [(1, 3), (2, 5), (4, 4)]), case([1], [(1, 1)]),
             case([10**9] * 5, [(1, 5), (2, 4)]), case([1, 2, 3, 4, 5, 6], [(1, 6), (1, 1), (6, 6), (3, 5)]),
             case([10**9] * 2 * 10**5, [(1, 2 * 10**5), (5, 2 * 10**5 - 3), (7, 7)])]
    for _ in range(18):
        n = _size(rng, 8, 2000, 2 * 10**5)
        q = _size(rng, 8, 2000, 2 * 10**5)
        hi = rng.choice([5, 1000, 10**9])
        a = [rng.randint(1, hi) for _ in range(n)]
        queries = []
        for _ in range(q):
            l = rng.randint(1, n)
            queries.append((l, rng.randint(l, n)))
        tests.append(case(a, queries))
    return _uniq(tests)


# ---- D. Medium: eng qisqa bo'lak ---------------------------------------------------------
def window_solve(inp):
    lines = inp.split("\n")
    n, s = map(int, lines[0].split())
    a = list(map(int, lines[1].split()))
    best, best_start, total, left = n + 1, 0, 0, 0
    for right in range(n):
        total += a[right]
        while total - a[left] >= s:
            total -= a[left]
            left += 1
        if total >= s and right - left + 1 < best:
            best, best_start = right - left + 1, left + 1
    return _lines(-1) if best == n + 1 else _lines(f"{best} {best_start}")


def window_tests(rng):
    def case(s, a):
        return f"{len(a)} {s}\n{_arr(a)}"
    tests = [case(15, [5, 1, 3, 5, 10, 7, 4, 9, 2, 8]), case(7, [2, 3, 1, 2, 4, 3]), case(1, [1]), case(2, [1]),
             case(5, [5, 5, 5]), case(10, [1, 1, 1, 1, 1]), case(10**14, [10**9] * 10**5),
             case(2 * 10**14, [10**9] * 2 * 10**5), case(2 * 10**14 + 1, [10**9] * 2 * 10**5),
             case(9, [4, 5, 9, 1, 8, 9]), case(6, [3, 3, 6, 6, 1, 5, 1]), case(3, [1, 1, 1, 3, 1, 1])]
    for _ in range(12):
        n = _size(rng, 8, 2000, 2 * 10**5)
        hi = rng.choice([4, 30, 10**4, 10**9])
        a = [rng.randint(1, hi) for _ in range(n)]
        total = sum(a)
        s = rng.choice([rng.randint(1, max(1, total // 50)), rng.randint(1, total), total, total + 1])
        tests.append(case(s, a))
    return _uniq(tests)


# ---- E. Medium: eng kam olib tashlash ----------------------------------------------------
def remove_solve(inp):
    lines = inp.split("\n")
    n = int(lines[0])
    tails = []
    for x in map(int, lines[1].split()):
        i = bisect_left(tails, x)  # strictly increasing: an equal value replaces, never extends
        if i == len(tails):
            tails.append(x)
        else:
            tails[i] = x
    return _lines(n - len(tails))


def remove_tests(rng):
    def case(a):
        return f"{len(a)}\n{_arr(a)}"
    tests = [case([3, 1, 2, 5, 4]), case([2, 2, 2, 2]), case([1]), case([5, 4, 3, 2, 1]), case([1, 2, 3, 4, 5]),
             case([1, 2, 2, 3]), case([10, 1, 11, 2, 12, 3]), case(list(range(2 * 10**5, 0, -1))),
             case(list(range(1, 2 * 10**5 + 1))), case([1, 3, 2, 3, 1, 4]), case([7, 7, 8, 8, 9, 9]),
             case([4, 10, 4, 3, 8, 9])]
    for _ in range(14):
        n = _size(rng, 8, 3000, 2 * 10**5)
        hi = rng.choice([3, 20, n, 10**9])
        tests.append(case([rng.randint(1, hi) for _ in range(n)]))
    tests.append(case([rng.choice([1, 2, 3, 4, 5]) for _ in range(2 * 10**5)]))
    return _uniq(tests)


# ---- F. Hard: yo'llar qurilishi ----------------------------------------------------------
def roads_solve(inp):
    lines = inp.split("\n")
    n, m, k = map(int, lines[0].split())
    parent = list(range(n + 1))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    parts = n
    for line in lines[1:1 + k]:
        u, v = map(int, line.split())
        ru, rv = find(u), find(v)
        if ru != rv:
            parent[ru] = rv
            parts -= 1
    edges = []
    for line in lines[1 + k:1 + k + m]:
        u, v, c = map(int, line.split())
        edges.append((c, u, v))
    edges.sort()
    cost = 0
    for c, u, v in edges:
        if parts == 1:
            break
        ru, rv = find(u), find(v)
        if ru != rv:
            parent[ru] = rv
            parts -= 1
            cost += c
    return _lines(cost if parts == 1 else -1)


def roads_tests(rng):
    def case(n, built, roads):
        rows = [f"{n} {len(roads)} {len(built)}", *[f"{u} {v}" for u, v in built], *[f"{u} {v} {c}" for u, v, c in roads]]
        return "\n".join(rows)

    def spanning(n, extra, hi):
        """Random roads that do connect every city (a tree), plus `extra` more."""
        order = list(range(1, n + 1))
        rng.shuffle(order)
        roads = [(order[i], order[rng.randint(0, i - 1)], rng.randint(1, hi)) for i in range(1, n)]
        for _ in range(extra):
            u, v = rng.randint(1, n), rng.randint(1, n)
            if u != v:
                roads.append((u, v, rng.randint(1, hi)))
        rng.shuffle(roads)
        return roads

    tests = [case(4, [], [(1, 2, 5), (2, 3, 4), (3, 4, 6), (1, 4, 1), (1, 3, 2)]),
             case(5, [(1, 2), (4, 5)], [(2, 3, 7), (3, 4, 3), (1, 5, 9), (2, 4, 8)]),
             case(1, [], []), case(2, [], []), case(2, [(1, 2)], []),
             case(3, [], [(1, 2, 4)]), case(3, [(1, 2), (2, 3), (1, 3)], [(1, 2, 9)]),
             case(4, [(1, 2)], [(1, 2, 1), (1, 2, 1), (3, 4, 10**9)]),
             case(5, [], [(1, 2, 3), (2, 3, 3), (3, 1, 3), (4, 5, 1)]),
             case(2 * 10**5, [], [(i, i + 1, 10**9) for i in range(1, 2 * 10**5)]),
             case(2 * 10**5, [(i, i + 1) for i in range(1, 10**5)], [(i, i + 1, 10**9) for i in range(10**5, 2 * 10**5)])]
    for _ in range(10):
        n = _size(rng, 8, 2000, 2 * 10**5)
        extra = rng.randint(0, min(2 * 10**5 - max(0, n - 1), n))
        roads = spanning(n, extra, rng.choice([5, 1000, 10**9]))
        built = []
        if rng.random() < 0.6:
            for _ in range(rng.randint(0, min(n, 10))):
                u, v = rng.randint(1, n), rng.randint(1, n)
                if u != v:
                    built.append((u, v))
        if rng.random() < 0.35 and len(roads) > 3:  # break the connection: drop some roads, maybe disconnecting
            del roads[:rng.randint(1, max(1, len(roads) // 3))]
        tests.append(case(n, built, roads[:2 * 10**5]))
    return _uniq(tests)


PROBLEMS = [
    {
        "slug": "cam2-yetkazib-berish", "title": "Yetkazib berish", "difficulty": "beginner", "points": 250,
        "tags": ["input-output", "arithmetic"], "solve": ship_solve, "tests": ship_tests, "samples": 2,
        "statement": ("Ombor posilkalarni quyidagi tarif bo‘yicha yuboradi: **birinchi 1000 gramm** uchun $a$ so‘m, "
                      "undan keyingi **har bir boshlangan 500 gramm** uchun yana $b$ so‘m.\n\n"
                      "Masalan, posilka 1001 gramm bo‘lsa, ortiqcha 1 gramm ham to‘liq 500 grammlik qadam sanaladi.\n\n"
                      "Og‘irligi $w$ gramm bo‘lgan posilkani yuborish necha so‘m turadi?"),
        "input": "Bitta qatorda uchta butun son: $w$, $a$ va $b$ ($1 \\le w, a, b \\le 10^9$).",
        "output": "Bitta son: yuborish narxi. U 32 bitli butun songa sig‘masligi mumkin.",
    },
    {
        "slug": "cam2-bir-marta-uchraydiganlar", "title": "Bir marta uchraydiganlar", "difficulty": "beginner",
        "points": 250, "tags": ["hash-table", "arrays"], "solve": once_solve, "tests": once_tests, "samples": 2,
        "statement": ("Omborga $n$ ta buyum keldi, har birining kodi butun son. Faqat **bitta** buyumi bor kodlarni "
                      "toping: ular ro‘yxatda aynan bir marta uchraydi.\n\n"
                      "Kodlarni ro‘yxatda birinchi marta uchragan tartibda chiqaring."),
        "input": ("Birinchi qatorda $n$ ($1 \\le n \\le 2 \\cdot 10^5$). Ikkinchi qatorda $n$ ta butun son — "
                  "kodlar ($|x_i| \\le 10^9$)."),
        "output": ("Birinchi qatorda bunday kodlar soni $k$. $k > 0$ bo‘lsa, ikkinchi qatorda ularning o‘zi. "
                   "Bunday kod bo‘lmasa, faqat `0` chiqaring."),
    },
    {
        "slug": "cam2-savdo-hisoboti", "title": "Savdo hisoboti", "difficulty": "easy", "points": 500,
        "tags": ["prefix-sums", "arrays"], "solve": sales_solve, "tests": sales_tests, "samples": 2,
        "statement": ("Do‘kon $n$ kun davomida savdo qildi: $a_i$ — $i$-kundagi tushum (so‘mda). Hisobchi $q$ ta "
                      "savol berdi: $l$-kundan $r$-kungacha (ikkalasi ham kiradi) jami tushum qancha?\n\n"
                      "Har bir savolga javob bering."),
        "input": ("Birinchi qatorda $n$ va $q$ ($1 \\le n, q \\le 2 \\cdot 10^5$). Ikkinchi qatorda $n$ ta butun son "
                  "$a_i$ ($1 \\le a_i \\le 10^9$). Keyingi $q$ qatorda ikkitadan son: $l$ va $r$ "
                  "($1 \\le l \\le r \\le n$)."),
        "output": "$q$ ta qator: har bir savolning javobi. Yig‘indi 32 bitli butun songa sig‘masligi mumkin.",
    },
    {
        "slug": "cam2-eng-qisqa-bolak", "title": "Eng qisqa bo‘lak", "difficulty": "medium", "points": 750,
        "tl_ms": 2000, "tags": ["two-pointers", "sliding-window"], "solve": window_solve, "tests": window_tests,
        "samples": 2,
        "statement": ("Omborda $n$ ta quti ketma-ket turibdi, $i$-qutining og‘irligi $a_i$. Yuk mashinasi ketma-ket "
                      "joylashgan bir nechta qutini olib ketadi va ularning jami og‘irligi **kamida $S$** bo‘lishi "
                      "kerak.\n\n"
                      "Eng kam nechta quti olish mumkin? Shunday eng qisqa bo‘laklar bir nechta bo‘lsa, eng "
                      "chapdagisini oling. Bo‘lak uzunligini va u nechanchi qutidan boshlanishini chiqaring. "
                      "Hech qanday bo‘lakning og‘irligi $S$ ga yetmasa, `-1`."),
        "input": ("Birinchi qatorda $n$ va $S$ ($1 \\le n \\le 2 \\cdot 10^5$, $1 \\le S \\le 2 \\cdot 10^{14}$). "
                  "Ikkinchi qatorda $n$ ta butun son $a_i$ ($1 \\le a_i \\le 10^9$)."),
        "output": ("Ikkita son: eng qisqa bo‘lakning uzunligi va uning boshlanish raqami ($1$ dan boshlab), "
                   "yoki `-1`."),
    },
    {
        "slug": "cam2-eng-kam-olib-tashlash", "title": "Eng kam olib tashlash", "difficulty": "medium",
        "points": 750, "tl_ms": 2000, "tags": ["binary-search", "dynamic-programming"], "solve": remove_solve,
        "tests": remove_tests, "samples": 2,
        "statement": ("Konveyerdan $n$ ta posilka o‘tadi, $i$-posilkaning raqami $a_i$. Posilkalarni raqami "
                      "**qat’iy o‘sib borishi** uchun tartiblash kerak: ularning ba’zilarini konveyerdan olib "
                      "tashlash mumkin, qolganlarining tartibi o‘zgarmaydi.\n\n"
                      "Qolgan posilkalarning raqamlari qat’iy o‘suvchi bo‘lishi uchun eng kamida nechtasini olib "
                      "tashlash kerak? Qat’iy o‘suvchi: har bir keyingi raqam oldingisidan **katta**, teng emas."),
        "input": ("Birinchi qatorda $n$ ($1 \\le n \\le 2 \\cdot 10^5$). Ikkinchi qatorda $n$ ta butun son "
                  "$a_i$ ($1 \\le a_i \\le 10^9$)."),
        "output": "Bitta son: olib tashlanadigan posilkalarning eng kam soni.",
    },
    {
        "slug": "cam2-yollar-qurilishi", "title": "Yo‘llar qurilishi", "difficulty": "hard", "points": 1000,
        "tl_ms": 2000, "tags": ["graphs", "dsu", "greedy"], "solve": roads_solve, "tests": roads_tests,
        "samples": 2,
        "statement": ("Mamlakatda $n$ ta shahar bor. Ba’zi shaharlar orasida yo‘l allaqachon qurilgan. Yana $m$ ta "
                      "yo‘lni qurish mumkin: $i$-yo‘l $u_i$ va $v_i$ shaharlarni bog‘laydi va $c_i$ so‘m turadi.\n\n"
                      "Har qanday ikki shahar orasida (boshqa shaharlar orqali bo‘lsa ham) yo‘l bo‘lishi uchun eng "
                      "kamida necha so‘m sarflash kerak? Iloji bo‘lmasa, `-1` chiqaring."),
        "input": ("Birinchi qatorda $n$, $m$ va $k$ ($1 \\le n \\le 2 \\cdot 10^5$, $0 \\le m, k \\le 2 \\cdot 10^5$): "
                  "shaharlar, qurilishi mumkin bo‘lgan yo‘llar va allaqachon qurilgan yo‘llar soni. Keyingi $k$ "
                  "qatorda ikkitadan son $u$, $v$ — qurilgan yo‘l. Undan keyingi $m$ qatorda uchtadan son "
                  "$u_i$, $v_i$, $c_i$ ($1 \\le u_i, v_i \\le n$, $u_i \\ne v_i$, $1 \\le c_i \\le 10^9$). "
                  "Bir juft shahar orasida bir nechta yo‘l bo‘lishi mumkin."),
        "output": ("Bitta son: eng kam xarajat yoki `-1`. Hamma shahar allaqachon bog‘langan bo‘lsa, `0`. "
                   "Javob 32 bitli butun songa sig‘masligi mumkin."),
    },
]


class Command(WeekendCommand):
    help = "Creates CodeArena Marathon #2 (rated, 120-minute personal clock) if needed and attaches its 6 problems (hidden) as A..F."
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
                    type=Contest.Type.SCORE, is_rated=True, personal_minutes=opts["minutes"],
                    division=Contest.Division.OPEN, badge=BADGE)
                self.stdout.write(f"«{contest.title}» yaratildi: {timezone.localtime(contest.start):%d.%m.%Y %H:%M} — "
                                  f"{timezone.localtime(contest.end):%d.%m.%Y %H:%M}, reytingli, "
                                  f"har kimga {contest.personal_minutes} daqiqa.")
            elif contest.start <= timezone.now() and not opts["force"]:
                raise CommandError("Musobaqa allaqachon boshlangan. Baribir ulash uchun --force qo'shing.")

            self._drop_old(contest, PROBLEMS, "cam2-")
            taken = set(contest.contest_problems.values_list("label", flat=True))
            for i, spec in enumerate(PROBLEMS):
                self._add(contest, spec, "ABCDEFGHIJ"[i], i, author, taken)
            if opts["dry_run"]:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("Dry run — hech narsa saqlanmadi."))
                return
        self.stdout.write(self.style.SUCCESS(
            f"Tayyor: «{contest.title}» da {contest.contest_problems.count()} ta masala. "
            "Masalalar yashirin; musobaqa tugagach Boshqaruv → Musobaqalar → «Masalalarni ochish»."))
