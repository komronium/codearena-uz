"""CodeArena Marathon #1: a 48-hour unrated round of ten hidden problems on one theme, a marathon, from
a first-week Beginner (A) to two Hard ones (I, J): arithmetic, a time string, arrays, counting and
sorting, ranks with ties, a sliding window, greedy, binary search on the answer, a minimax path and
counting inversions. None repeats a problem already on the portal. Creates the contest when it does
not exist yet (points rules, Open, unrated, the "Marathon #1" badge) and attaches the problems as A..J.

Every expected output comes from a reference solution here, never typed by hand. Safe to re-run:
problems that already exist (by slug) are reused, not duplicated.

    python manage.py add_codearena_marathon_1 --start "2026-10-09 18:00" [--hours 48] [--author admin] [--dry-run]
"""
import heapq
from collections import Counter
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import CommandError
from django.db import transaction
from django.utils import timezone

from apps.contests.management.commands.add_weekend_contest_1 import Command as WeekendCommand, _lines
from apps.contests.models import Contest

TITLE = "CodeArena Marathon #1"
BADGE = "Marathon #1"
DESCRIPTION = """**48 soatlik marafon:** 10 ta masala, osonidan qiyiniga. Shoshilmang — vaqt yetarli.

- Istalgan paytda qo‘shiling: musobaqa juma kechqurundan yakshanba kechqurungacha ochiq.
- **Reytingsiz**: natija reytingingizga ta’sir qilmaydi.
- Har bir to‘liq yechilgan masala uchun uning bali; ball teng bo‘lsa, jarimasi kam bo‘lgan yuqorida (jarima musobaqa boshlanganidan hisoblanadi).
- **Nishon**: kamida bitta masala yechgan har bir ishtirokchi profiliga «Marathon #1» nishoni qo‘shiladi, birinchi uchtalikka — medal.
- Halollik qoidalari amal qiladi: kod o‘zingizniki bo‘lsin; AI yoki boshqa birovning yechimi taqiqlanadi."""


def _uniq(inputs):
    return list(dict.fromkeys(inputs))


def _arr(values) -> str:
    return " ".join(map(str, values))


def _size(rng, small, medium, big):
    """A random test's size: mostly small and medium, one time in six the limit (the fixed tests have
    their own limit-sized cases), so the judge doesn't read megabytes on every run."""
    return rng.choice([rng.randint(1, small), rng.randint(1, small), rng.randint(1, medium),
                       rng.randint(1, medium), rng.randint(1, medium), big])


# ---- A. Beginner: start to'lqinlari ------------------------------------------------------
def wave_solve(inp):
    k, x = map(int, inp.split())
    return _lines(f"{(x - 1) // k + 1} {(x - 1) % k + 1}")


def wave_tests(rng):
    tests = ["500 1234", "100 100", "1 1", "1 1000000000", "1000000000 1", "1000000000 1000000000",
             "7 7", "7 8", "7 14", "7 15", "2 3", "3 2", "999999999 1000000000"]
    for _ in range(10):
        k = rng.choice([rng.randint(1, 10), rng.randint(1, 1000), rng.randint(1, 10**9)])
        tests.append(f"{k} {rng.randint(1, 10**9)}")
    return _uniq(tests)


# ---- B. Beginner: finish vaqti -----------------------------------------------------------
def finish_solve(inp):
    h, m, s = map(int, inp.strip().split(":"))
    t = h * 3600 + m * 60 + s
    for limit, name in ((3 * 3600, "Oltin"), (4 * 3600, "Kumush"), (5 * 3600, "Bronza")):
        if t < limit:
            return _lines(name)
    return _lines("Finish" if t <= 6 * 3600 else "Vaqt tugadi")


def finish_tests(rng):
    tests = ["3:41:07", "5:12:40", "2:59:59", "3:00:00", "3:59:59", "4:00:00", "4:59:59", "5:00:00", "6:00:00",
             "6:00:01", "0:00:01", "9:59:59", "2:05:30", "1:00:00", "7:30:00"]
    for _ in range(10):
        tests.append(f"{rng.randint(0, 9)}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}")
    return _uniq(tests)


# ---- C. Easy: eng tez kilometr -----------------------------------------------------------
def km_solve(inp):
    t = list(map(int, inp.split()[1:]))
    best_km, best, prev = 0, None, 0
    for i, x in enumerate(t, 1):
        if best is None or x - prev < best:
            best_km, best = i, x - prev
        prev = x
    return _lines(f"{best_km} {best}")


def km_tests(rng):
    def case(splits):
        times, now = [], 0
        for d in splits:
            now += d
            times.append(now)
        return f"{len(times)}\n{_arr(times)}"
    tests = [case([300, 310, 295, 310, 285]), case([250]), case([300, 300, 300]), case([400, 380, 360, 380, 360]),
             case([10**9]), case([1, 1]), case(range(10**4, 0, -1)), case(range(1, 10**4 + 1)),
             case([10**4] * 10**5)]
    for _ in range(14):
        n = _size(rng, 10, 1000, 10**5)
        lo = rng.choice([1, 180, 240])
        tests.append(case([rng.randint(lo, lo + rng.choice([5, 60, 9000])) for _ in range(n)]))
    return _uniq(tests)


# ---- D. Easy: davlatlar ------------------------------------------------------------------
def country_solve(inp):
    counts = Counter(inp.split()[1:])
    return _lines(*(f"{code} {n}" for code, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))))


def country_tests(rng):
    pool = ["UZB", "KAZ", "KGZ", "TJK", "TKM", "RUS", "TUR", "KOR", "JPN", "CHN", "USA", "GBR", "DEU", "FRA",
            "ITA", "ESP", "IND", "PAK", "AFG", "IRN", "AZE", "GEO", "ARM", "UKR", "BLR", "KEN", "ETH", "BRA"]

    def case(codes):
        return f"{len(codes)}\n" + "\n".join(codes)
    tests = [case(["UZB", "KAZ", "UZB", "KGZ", "UZB", "KAZ"]), case(["TJK"]), case(["UZB"] * 1000),
             case(["KEN", "ETH", "KEN", "ETH"]), case(sorted(pool, reverse=True)), case(["ZZZ", "AAA", "MMM"]),
             case(["AAB", "AAA", "AAB", "AAA", "AAC"])]
    for _ in range(14):
        n = _size(rng, 20, 2000, 10**5)
        if rng.random() < 0.3:  # many distinct codes, ties everywhere
            codes = ["".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(3)) for _ in range(n)]
        else:
            few = rng.sample(pool, rng.randint(1, len(pool)))
            codes = [rng.choice(few) for _ in range(n)]
        tests.append(case(codes))
    return _uniq(tests)


# ---- E. Easy: o'rinlar -------------------------------------------------------------------
def place_solve(inp):
    t = list(map(int, inp.split()[1:]))
    place = {}
    for i, x in enumerate(sorted(t), 1):
        place.setdefault(x, i)  # the first of equal times: everyone tied shares it
    return _lines(_arr(place[x] for x in t))


def place_tests(rng):
    def case(times):
        return f"{len(times)}\n{_arr(times)}"
    tests = [case([9000, 8500, 9000, 10200, 8500]), case([100, 100, 100]), case([7]), case([5, 4, 3, 2, 1]),
             case([1, 2, 3, 4, 5]), case([10**9, 1, 10**9, 1]), case([3600] * 2 * 10**5),
             case(range(2 * 10**5, 0, -1))]
    for _ in range(14):
        n = _size(rng, 15, 3000, 2 * 10**5)
        hi = rng.choice([5, 1000, 10**9])
        tests.append(case([rng.randint(1, hi) for _ in range(n)]))
    return _uniq(tests)


# ---- F. Medium: eng og'ir bo'lak ---------------------------------------------------------
def climb_solve(inp):
    data = list(map(int, inp.split()))
    n, k, h = data[0], data[1], data[2:]
    up = [max(0, h[i] - h[i - 1]) for i in range(1, n + 1)]
    window = sum(up[:k])
    best, start = window, 1
    for i in range(k, n):
        window += up[i] - up[i - k]
        if window > best:
            best, start = window, i - k + 2
    return _lines(f"{best} {start}")


def climb_tests(rng):
    def case(k, h):
        return f"{len(h) - 1} {k}\n{_arr(h)}"
    tests = [case(3, [100, 120, 110, 140, 150, 150, 130]), case(2, [10, 5, 0, 0]), case(1, [0, 10**4]),
             case(1, [10**4, 0]), case(5, list(range(0, 600, 100))), case(3, [500] * 10),
             case(2, [0, 10, 0, 10, 0, 10]), case(2 * 10**5, [i % 10**4 for i in range(2 * 10**5 + 1)]),
             case(1, [0] * (2 * 10**5 + 1))]
    for _ in range(14):
        n = _size(rng, 15, 3000, 2 * 10**5)
        k = rng.randint(1, n)
        h, cur = [], rng.randint(0, 10**4)
        for _ in range(n + 1):  # a walk, so climbs and descents come in runs like a real route
            cur = min(10**4, max(0, cur + rng.randint(-rng.choice([3, 50, 10**4]), rng.choice([3, 50, 10**4]))))
            h.append(cur)
        tests.append(case(k, h))
    return _uniq(tests)


# ---- G. Medium: suv punktlari ------------------------------------------------------------
def water_solve(inp):
    data = list(map(int, inp.split()))
    length, d, n, p = data[0], data[1], data[2], data[3:]
    pos = count = i = 0
    while pos + d < length:
        far = pos
        while i < n and p[i] <= pos + d:
            far = p[i]
            i += 1
        if far == pos:
            return _lines(-1)
        pos, count = far, count + 1
    return _lines(count)


def water_tests(rng):
    def case(length, d, points):
        return f"{length} {d} {len(points)}\n{_arr(points)}"

    def spread(length, n):
        return sorted(rng.sample(range(1, length), n))
    tests = [case(42195, 10000, [5000, 9000, 15000, 21000, 30000, 38000]), case(100, 30, [20, 70]),
             case(100, 100, [50]), case(100, 99, [1]), case(100, 50, [50]), case(100, 49, [49, 98]),
             case(10, 1, list(range(1, 10))), case(10, 1, list(range(1, 9))), case(10**9, 1, [5]),
             case(10**9, 10**9, [1, 2, 3]), case(10**9, 5000, list(range(5000, 10**9, 5000))[:2 * 10**5])]
    for _ in range(14):
        length = rng.choice([rng.randint(2, 100), rng.randint(2, 10**5), rng.randint(2, 10**9)])
        n = min(length - 1, _size(rng, 10, 2000, 2 * 10**5))
        points = spread(length, n)
        gaps = [b - a for a, b in zip([0, *points], [*points, length])]
        d = max(gaps) if rng.random() < 0.8 else max(1, max(gaps) - rng.randint(1, max(1, max(gaps) // 2)))
        tests.append(case(length, min(10**9, rng.randint(d, d + d // 3)) if rng.random() < 0.5 else d, points))
    return _uniq(tests)


# ---- H. Medium: bosqichlarga bo'lish -----------------------------------------------------
def stages_solve(inp):
    data = list(map(int, inp.split()))
    k, a = data[1], data[2:]

    def days(limit):
        used, cur = 1, 0
        for x in a:
            if cur + x > limit:
                used, cur = used + 1, 0
            cur += x
        return used
    lo, hi = max(a), sum(a)
    while lo < hi:
        mid = (lo + hi) // 2
        if days(mid) <= k:
            hi = mid
        else:
            lo = mid + 1
    return _lines(lo)


def stages_tests(rng):
    def case(k, a):
        return f"{len(a)} {k}\n{_arr(a)}"
    tests = [case(2, [7, 2, 5, 10, 8]), case(4, [1, 2, 3, 4]), case(1, [5]), case(1, [10**4] * 10**5),
             case(10**5, [10**4] * 10**5), case(3, [1, 1, 1, 1, 1, 1, 1, 1, 1, 10]), case(2, [10, 1, 1, 1, 1]),
             case(2, [1, 1, 1, 1, 10]), case(50000, [i % 10**4 + 1 for i in range(10**5)])]
    for _ in range(14):
        n = _size(rng, 12, 3000, 10**5)
        hi = rng.choice([10, 10**4])
        tests.append(case(rng.randint(1, n), [rng.randint(1, hi) for _ in range(n)]))
    return _uniq(tests)


# ---- I. Hard: eng yumshoq yo'l -----------------------------------------------------------
def gentle_solve(inp):
    data = list(map(int, inp.split()))
    n, m, h = data[0], data[1], data[2:]
    best = [None] * (n * m)
    best[0] = 0
    heap = [(0, 0)]
    while heap:
        effort, v = heapq.heappop(heap)
        if v == n * m - 1:
            return _lines(effort)
        if effort > best[v]:
            continue
        r, c = divmod(v, m)
        for u in (v - m if r else -1, v + m if r + 1 < n else -1, v - 1 if c else -1, v + 1 if c + 1 < m else -1):
            if u >= 0:
                e = max(effort, abs(h[u] - h[v]))
                if best[u] is None or e < best[u]:
                    best[u] = e
                    heapq.heappush(heap, (e, u))
    raise AssertionError("the grid is connected")


def gentle_tests(rng):
    def case(grid):
        return f"{len(grid)} {len(grid[0])}\n" + "\n".join(_arr(row) for row in grid)

    def rand(n, m, hi):
        return [[rng.randint(0, hi) for _ in range(m)] for _ in range(n)]

    def walls(n, m):
        # a winding corridor of gentle steps through high walls: the gentle route is the long way round
        grid = [[10**6] * m for _ in range(n)]
        for r in range(0, n, 2):
            for c in range(m):
                grid[r][c] = rng.randint(0, 3)
        for r in range(1, n, 2):
            grid[r][m - 1 if r % 4 == 1 else 0] = rng.randint(0, 3)
        return grid
    tests = [case([[1, 2, 2], [3, 8, 2], [5, 3, 5]]), case([[7]]), case([[1, 2, 3, 4, 5]]),
             case([[1], [10], [3], [8]]), case([[5] * 300 for _ in range(300)]), case(walls(9, 7)),
             case(walls(299, 300)), case([[0, 10**6], [10**6, 0]]), case([[1, 10, 6, 7, 9, 10, 4, 9]])]
    for _ in range(12):
        n, m = rng.choice([(rng.randint(1, 8), rng.randint(1, 8)), (rng.randint(1, 60), rng.randint(1, 60)),
                           (300, 300)])
        tests.append(case(rand(n, m, rng.choice([10, 1000, 10**6]))))
    return _uniq(tests)


# ---- J. Hard: quvib o'tishlar ------------------------------------------------------------
def overtake_solve(inp):
    order = list(map(int, inp.split()[1:]))
    n = len(order)
    tree = [0] * (n + 1)
    total = 0
    for seen, x in enumerate(order):  # finish order: count the ones already in with a larger start number
        i, before = x, 0
        while i > 0:
            before += tree[i]
            i -= i & -i
        total += seen - before
        while x <= n:
            tree[x] += 1
            x += x & -x
    return _lines(total)


def overtake_tests(rng):
    def case(order):
        return f"{len(order)}\n{_arr(order)}"

    def near(n, swaps):
        order = list(range(1, n + 1))
        for _ in range(swaps):
            i = rng.randrange(n - 1)
            order[i], order[i + 1] = order[i + 1], order[i]
        return order
    tests = [case([2, 1, 5, 3, 4]), case([1, 2, 3]), case([1]), case([2, 1]), case(list(range(10, 0, -1))),
             case(list(range(2 * 10**5, 0, -1))), case(list(range(1, 1001))), case(near(2 * 10**5, 1000)),
             case([*range(2, 5001), 1])]
    for _ in range(14):
        n = _size(rng, 10, 3000, 2 * 10**5)
        order = list(range(1, n + 1))
        rng.shuffle(order)
        tests.append(case(order))
    return _uniq(tests)


PROBLEMS = [
    {
        "slug": "cam1-start-tolqinlari", "title": "Start to‘lqinlari", "difficulty": "beginner", "points": 100,
        "tags": ["input-output", "arithmetic"], "solve": wave_solve, "tests": wave_tests, "samples": 2,
        "statement": ("Marafonda yuguruvchilar startga to‘lqin-to‘lqin bo‘lib chiqadi: birinchi to‘lqinda start "
                      "raqami $1$ dan $k$ gacha bo‘lganlar, ikkinchisida $k + 1$ dan $2k$ gacha, va hokazo.\n\n"
                      "Start raqami $x$ bo‘lgan yuguruvchi nechanchi to‘lqinda va o‘z to‘lqinida nechanchi bo‘lib "
                      "turadi?"),
        "input": "Bitta qatorda ikkita butun son: $k$ va $x$ ($1 \\le k, x \\le 10^9$).",
        "output": "Ikkita son: to‘lqin raqami va to‘lqindagi o‘rni.",
    },
    {
        "slug": "cam1-finish-vaqti", "title": "Finish vaqti", "difficulty": "beginner", "points": 100,
        "tags": ["conditionals", "strings"], "solve": finish_solve, "tests": finish_tests, "samples": 2,
        "statement": ("Yuguruvchining marafondagi vaqti `H:MM:SS` ko‘rinishida berilgan: soat, daqiqa va soniya. "
                      "Vaqtiga qarab unga nishon beriladi:\n\n"
                      "- 3 soatdan kam — `Oltin`\n"
                      "- 3 soatdan 4 soatgacha (4 soat kirmaydi) — `Kumush`\n"
                      "- 4 soatdan 5 soatgacha (5 soat kirmaydi) — `Bronza`\n"
                      "- 5 soatdan 6 soatgacha, 6 soat ham kiradi — `Finish`\n"
                      "- 6 soatdan ko‘p — `Vaqt tugadi`"),
        "input": ("Bitta qatorda vaqt `H:MM:SS`: $0 \\le H \\le 9$, daqiqa va soniya — ikki xonali, "
                  "`00` dan `59` gacha."),
        "output": "Nishon nomi, yuqoridagidek yozilgan.",
    },
    {
        "slug": "cam1-eng-tez-kilometr", "title": "Eng tez kilometr", "difficulty": "easy", "points": 200,
        "tags": ["arrays", "for-loop"], "solve": km_solve, "tests": km_tests, "samples": 2,
        "statement": ("Sportchining soati har kilometr belgisida startdan beri o‘tgan vaqtni yozib boradi: $t_i$ — "
                      "$i$-kilometr belgisidagi vaqt (soniyada). Demak $i$-kilometr $t_i - t_{i-1}$ soniyada "
                      "yugurilgan, bunda $t_0 = 0$.\n\n"
                      "Eng tez yugurilgan kilometrni toping. Bunday kilometr bir nechta bo‘lsa, raqami eng "
                      "kichigini oling."),
        "input": ("Birinchi qatorda $n$ ($1 \\le n \\le 10^5$). Ikkinchi qatorda $n$ ta butun son "
                  "$t_1 < t_2 < \\ldots < t_n$ ($1 \\le t_i \\le 10^9$)."),
        "output": "Ikkita son: eng tez kilometrning raqami va u necha soniyada yugurilgani.",
    },
    {
        "slug": "cam1-davlatlar", "title": "Davlatlar", "difficulty": "easy", "points": 200,
        "tags": ["hash-table", "sorting", "strings"], "solve": country_solve, "tests": country_tests, "samples": 2,
        "statement": ("Marafonda $n$ kishi qatnashdi. Har birining start raqami yonida davlatining kodi bor — uchta "
                      "katta lotin harfi, masalan `UZB` yoki `KAZ`.\n\n"
                      "Har bir davlatdan nechta yuguruvchi qatnashganini chiqaring: ko‘p qatnashgan davlat oldin; "
                      "soni teng bo‘lsa, kodi alifbo bo‘yicha oldin keladigani oldin."),
        "input": "Birinchi qatorda $n$ ($1 \\le n \\le 10^5$). Keyingi $n$ qatorda bittadan davlat kodi.",
        "output": "Har bir davlat uchun bitta qator: kodi va qatnashchilar soni, bo‘sh joy bilan.",
    },
    {
        "slug": "cam1-orinlar", "title": "O‘rinlar", "difficulty": "easy", "points": 250,
        "tags": ["sorting", "arrays"], "solve": place_solve, "tests": place_tests, "samples": 2,
        "statement": ("$n$ ta yuguruvchining finish vaqti soniyalarda berilgan, start raqami tartibida. Har bir "
                      "yuguruvchining o‘rnini toping: vaqti kam bo‘lgan oldinda.\n\n"
                      "Vaqti teng bo‘lganlar bir xil o‘rinni egallaydi, keyingi o‘rin esa ular soniga qarab "
                      "o‘tkazib yuboriladi: vaqtlar $100, 100, 120$ bo‘lsa, o‘rinlar $1, 1, 3$."),
        "input": ("Birinchi qatorda $n$ ($1 \\le n \\le 2 \\cdot 10^5$). Ikkinchi qatorda $n$ ta butun son — "
                  "vaqtlar ($1 \\le t_i \\le 10^9$)."),
        "output": "Bitta qatorda $n$ ta son: har bir yuguruvchining o‘rni, kirishdagi tartibda.",
    },
    {
        "slug": "cam1-eng-ogir-bolak", "title": "Eng og‘ir bo‘lak", "difficulty": "medium", "points": 300,
        "tags": ["sliding-window", "prefix-sums"], "solve": climb_solve, "tests": climb_tests, "samples": 2,
        "statement": ("Trassaning balandligi har 100 metrda o‘lchangan: $h_0, h_1, \\ldots, h_n$. Trassa $n$ ta "
                      "bo‘lakka bo‘linadi, $i$-bo‘lak $h_{i-1}$ dan $h_i$ gacha. Bo‘lakdagi ko‘tarilish — "
                      "$\\max(0,\\ h_i - h_{i-1})$: pastga tushish ko‘tarilishni kamaytirmaydi.\n\n"
                      "Ketma-ket $k$ ta bo‘lakdan iborat qaysi qismda jami ko‘tarilish eng katta? Bunday qism bir "
                      "nechta bo‘lsa, eng chapdagisini oling."),
        "input": ("Birinchi qatorda $n$ va $k$ ($1 \\le k \\le n \\le 2 \\cdot 10^5$). Ikkinchi qatorda $n + 1$ ta "
                  "butun son $h_0, \\ldots, h_n$ ($0 \\le h_i \\le 10^4$)."),
        "output": ("Ikkita son: eng katta jami ko‘tarilish va o‘sha qism boshlanadigan bo‘lak raqami (bo‘laklar "
                   "$1$ dan $n$ gacha raqamlangan)."),
    },
    {
        "slug": "cam1-suv-punktlari", "title": "Suv punktlari", "difficulty": "medium", "points": 350,
        "tags": ["greedy"], "solve": water_solve, "tests": water_tests, "samples": 2,
        "statement": ("Trassa uzunligi $L$ metr: start $0$ da, finish $L$ da. Suv punktini faqat $n$ ta joyga "
                      "qo‘yish mumkin: $p_1 < p_2 < \\ldots < p_n$.\n\n"
                      "Yuguruvchi suvsiz $D$ metrdan ko‘p yugurmasligi kerak: startdan birinchi punktgacha, "
                      "qo‘shni punktlar orasida va oxirgi punktdan finishgacha masofa $D$ dan oshmasin. Eng kamida "
                      "nechta punkt qo‘yish kerak? Iloji bo‘lmasa, `-1` chiqaring."),
        "input": ("Birinchi qatorda $L$, $D$ va $n$ ($2 \\le L \\le 10^9$, $1 \\le D \\le 10^9$, "
                  "$1 \\le n \\le \\min(L - 1,\\ 2 \\cdot 10^5)$). Ikkinchi qatorda $n$ ta butun son "
                  "$p_1 < \\ldots < p_n$ ($0 < p_i < L$)."),
        "output": "Eng kam punktlar soni yoki `-1`.",
    },
    {
        "slug": "cam1-bosqichlarga-bolish", "title": "Bosqichlarga bo‘lish", "difficulty": "medium", "points": 400,
        "tl_ms": 2000, "tags": ["binary-search", "greedy"], "solve": stages_solve, "tests": stages_tests,
        "samples": 2,
        "statement": ("Mashg‘ulot yo‘li $n$ ta ketma-ket bo‘lakdan iborat, $i$-bo‘lak uzunligi $a_i$ metr. Sportchi "
                      "uni $k$ kunda yugurib chiqmoqchi: har kuni kamida bitta ketma-ket bo‘lakni yuguradi, "
                      "bo‘laklar tartibi o‘zgarmaydi va bo‘lak bo‘linmaydi.\n\n"
                      "Eng ko‘p yuguriladigan kundagi masofa iloji boricha kichik bo‘lsin. Shu masofani toping."),
        "input": ("Birinchi qatorda $n$ va $k$ ($1 \\le k \\le n \\le 10^5$). Ikkinchi qatorda $n$ ta butun son "
                  "$a_i$ ($1 \\le a_i \\le 10^4$)."),
        "output": "Eng ko‘p yugurilgan kun masofasining eng kichik mumkin bo‘lgan qiymati.",
    },
    {
        "slug": "cam1-eng-yumshoq-yol", "title": "Eng yumshoq yo‘l", "difficulty": "hard", "points": 500,
        "tl_ms": 2000, "tags": ["graphs", "shortest-paths"], "solve": gentle_solve, "tests": gentle_tests,
        "samples": 2,
        "statement": ("Shahar xaritasi $n \\times m$ katakli jadval, har bir katakda balandlik bor. Yuguruvchi chap "
                      "yuqori katakdan o‘ng pastki katakka borishi kerak; har qadamda yonma-yon katakka — yuqoriga, "
                      "pastga, chapga yoki o‘ngga — o‘tadi.\n\n"
                      "Qadamning og‘irligi — ikki katak balandliklari farqining moduli. Yo‘lning og‘irligi — undagi "
                      "eng og‘ir qadam. Eng yengil yo‘lning og‘irligini toping."),
        "input": ("Birinchi qatorda $n$ va $m$ ($1 \\le n, m \\le 300$). Keyingi $n$ qatorda $m$ tadan butun son — "
                  "balandliklar ($0 \\le h_{i,j} \\le 10^6$)."),
        "output": "Eng yengil yo‘lning og‘irligi ($n = m = 1$ bo‘lsa, `0`).",
    },
    {
        "slug": "cam1-quvib-otishlar", "title": "Quvib o‘tishlar", "difficulty": "hard", "points": 500,
        "tl_ms": 2000, "tags": ["data-structures", "divide-and-conquer"], "solve": overtake_solve,
        "tests": overtake_tests, "samples": 2,
        "statement": ("Startda yuguruvchilar start raqami tartibida turadi: $1$-raqamli eng oldinda, $n$-raqamli "
                      "eng orqada. Finishga kelish tartibi ma’lum.\n\n"
                      "Startda orqaroqda turgan yuguruvchi finishga oldinroq kelgan bo‘lsa, u oldindagini quvib "
                      "o‘tgan hisoblanadi: har bir shunday juftlik — bitta quvib o‘tish. Jami nechta quvib o‘tish "
                      "bo‘lgan?"),
        "input": ("Birinchi qatorda $n$ ($1 \\le n \\le 2 \\cdot 10^5$). Ikkinchi qatorda $n$ ta son — finishga "
                  "kelish tartibidagi start raqamlari: $1$ dan $n$ gacha har biri bir martadan."),
        "output": "Quvib o‘tishlar soni. U 32 bitli butun songa sig‘masligi mumkin.",
    },
]


class Command(WeekendCommand):
    help = "Creates CodeArena Marathon #1 if needed and attaches its 10 problems (hidden) as A..J."
    ml_mb = 256

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.set_defaults(contest=TITLE)
        parser.add_argument("--start", default=None, help='Start, Tashkent time: "2026-10-09 18:00" (new contest)')
        parser.add_argument("--hours", type=int, default=48, help="Length in hours (new contest)")

    def handle(self, *args, **opts):
        User = get_user_model()
        author = (User.objects.filter(username=opts["author"]).first() if opts["author"]
                  else User.objects.filter(is_superuser=True).order_by("pk").first())
        if author is None:
            raise CommandError("Muallif topilmadi — --author bilan mavjud login bering.")

        with transaction.atomic():
            contest = Contest.objects.filter(title__iexact=opts["contest"]).first()
            if contest is None:
                if not opts["start"]:
                    raise CommandError("Musobaqa hali yo'q: --start bilan boshlanish vaqtini bering, "
                                       'masalan --start "2026-10-09 18:00".')
                try:
                    start = timezone.make_aware(datetime.strptime(opts["start"], "%Y-%m-%d %H:%M"))
                except ValueError:
                    raise CommandError('--start "YYYY-MM-DD HH:MM" ko‘rinishida bo‘lsin.')
                if start <= timezone.now():
                    raise CommandError("Boshlanish vaqti o'tib ketgan.")
                contest = Contest.objects.create(
                    title=opts["contest"], description_md=DESCRIPTION, start=start,
                    end=start + timedelta(hours=opts["hours"]), type=Contest.Type.SCORE, is_rated=False,
                    division=Contest.Division.OPEN, badge=BADGE)
                self.stdout.write(f"«{contest.title}» yaratildi: {timezone.localtime(contest.start):%d.%m.%Y %H:%M} — "
                                  f"{timezone.localtime(contest.end):%d.%m.%Y %H:%M}, reytingsiz.")
            elif contest.start <= timezone.now() and not opts["force"]:
                raise CommandError("Musobaqa allaqachon boshlangan. Baribir ulash uchun --force qo'shing.")

            self._drop_old(contest, PROBLEMS, "cam1-")
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
