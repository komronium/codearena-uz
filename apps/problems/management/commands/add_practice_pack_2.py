"""Practice pack #2: 30 Beginner/Easy classics — the ideas every interview-prep list starts with
(prefix sums, a hash set, two pointers, XOR, a majority vote, Roman numerals, isqrt...), each in
our own words and the portal's stdin/stdout format. None repeats a problem already on the portal.

Easy ones get inputs up to 10^5 so a quadratic loop runs out of time; Beginner ones stay small.
Every expected output comes from the reference solution here. Safe to re-run: problems that
already exist (by slug) are left as they are.

    python manage.py add_practice_pack_2 [--author admin] [--hidden] [--dry-run]
"""
import math
import os
import string
from collections import Counter
from itertools import accumulate

from .add_practice_pack_1 import Command as Pack1Command
from .add_practice_pack_1 import _lines, _yes

# Sizes of the random tests after the fixed ones; the Easy problems add two of the maximum size.
SMALL = [1, 1, 2, 3, 4, 5, 7, 10, 15, 20, 50, 100, 200, 500, 1000, 1000]
BIG = SMALL + [10**5, 10**5]


def _ints(inp: str) -> list[int]:
    return list(map(int, inp.split()))


def _join(xs) -> str:
    return " ".join(map(str, xs))


def _size(rng, cap: int) -> int:
    return cap if cap >= 10**5 else rng.randint(max(1, cap // 2), cap)


def _arr(rng, n, lo, hi) -> list[int]:
    return [rng.randint(lo, hi) for _ in range(n)]


def _arr_case(rng, cap, lo, hi) -> str:
    n = _size(rng, cap)
    return f"{n}\n{_join(_arr(rng, n, lo, hi))}"


def _word(rng, n, letters=string.ascii_lowercase) -> str:
    return "".join(rng.choice(letters) for _ in range(n))


# ============================== Beginner ==============================

def hisob_solve(inp):
    _, *a = _ints(inp)
    return _lines(_join(accumulate(a)))


def hisob_tests(rng):
    t = ["5\n10 20 -5 0 15", "3\n-7 -7 -7", "1\n0", "1\n-1000000",
         "1000\n" + _join([10**6] * 1000), "1000\n" + _join([-10**6] * 1000)]
    return t + [_arr_case(rng, c, -10**6, 10**6) for c in SMALL]


def boy_solve(inp):
    m, n, *a = _ints(inp)
    return _lines(max(sum(a[i * n:(i + 1) * n]) for i in range(m)))


def boy_tests(rng):
    def case(m, n, lo=1, hi=100):
        return f"{m} {n}\n" + "\n".join(_join(_arr(rng, n, lo, hi)) for _ in range(m))
    t = ["3 2\n1 5\n7 3\n3 5", "2 3\n1 1 1\n1 1 1", "1 1\n7", case(50, 50, 100, 100), case(1, 50), case(50, 1)]
    return t + [case(rng.randint(1, 50), rng.randint(1, 50)) for _ in range(16)]


def tosh_solve(inp):
    jewels, stones = inp.split()
    return _lines(sum(c in set(jewels) for c in stones))


def tosh_tests(rng):
    letters = string.ascii_letters
    t = ["xY\nxxYyyZ", "z\nZZZ", "a\na", "abc\n" + "d" * 1000, letters + "\n" + _word(rng, 1000, letters)]
    for _ in range(17):
        jewels = "".join(rng.sample(letters, rng.randint(1, 10)))
        pool = jewels + _word(rng, rng.randint(1, 10), letters)
        t.append(f"{jewels}\n{_word(rng, rng.randint(1, 1000), pool)}")
    return t


def oxirgi_solve(inp):
    return _lines(len(inp.split()[-1]))


def oxirgi_tests(rng):
    t = ["Salom dunyo", "  kod yozamiz   ", "a", "x" * 1000, "   Toshkent", "bir ikki uch  z "]
    for _ in range(16):
        words = [_word(rng, rng.randint(1, 12), string.ascii_letters) for _ in range(rng.randint(1, 30))]
        gaps = [" " * rng.randint(1, 3) for _ in words]
        line = " " * rng.randint(0, 2) + "".join(w + g for w, g in zip(words, gaps))
        t.append(line if rng.random() < 0.5 else line.rstrip())
    return t


def birlar_solve(inp):
    _, *a = _ints(inp)
    best = run = 0
    for x in a:
        run = run + 1 if x else 0
        best = max(best, run)
    return _lines(best)


def birlar_tests(rng):
    t = ["8\n1 1 0 1 1 1 0 1", "5\n0 0 0 0 0", "1\n1", "1\n0", "1000\n" + _join([1] * 1000),
         "6\n0 1 1 1 1 0"]
    for c in SMALL:
        n, p = _size(rng, c), rng.choice([0.3, 0.7, 0.95])
        t.append(f"{n}\n{_join(int(rng.random() < p) for _ in range(n))}")
    return t


def nol_solve(inp):
    _, *a = _ints(inp)
    return _lines(_join([x for x in a if x] + [0] * a.count(0)))


def nol_tests(rng):
    t = ["6\n0 4 0 -2 7 0", "3\n5 6 7", "1\n0", "4\n0 0 0 0", "5\n9 0 0 0 1"]
    for c in SMALL + [1000, 1000]:
        n = _size(rng, c)
        t.append(f"{n}\n{_join(0 if rng.random() < 0.4 else rng.randint(-10**9, 10**9) for _ in range(n))}")
    return t


def ikki_daraja_solve(inp):
    n = int(inp)
    return _yes(n & (n - 1) == 0)


def ikki_daraja_tests(rng):
    t = ["8", "12", "1", "2", "3", str(2**59), str(2**59 + 1), str(2**59 - 1), str(10**18), "1024", "96"]
    for _ in range(11):
        t.append(str(2 ** rng.randint(0, 59)) if rng.random() < 0.5 else str(rng.randint(1, 10**18)))
    return t


def takrorsiz_solve(inp):
    _, *a = _ints(inp)
    u = sorted(set(a))
    return _lines(len(u), _join(u))


def takrorsiz_tests(rng):
    t = ["7\n1 1 2 3 3 3 8", "3\n5 5 5", "1\n0", "5\n-2 -1 0 1 2", "1000\n" + _join([-1000] * 1000)]
    for c in SMALL + [1000]:
        n = _size(rng, c)
        t.append(f"{n}\n{_join(sorted(_arr(rng, n, -1000, 1000) if rng.random() < 0.5 else _arr(rng, n, 0, 9)))}")
    return t


def topish_solve(inp):
    text, pattern = inp.split()
    k = text.find(pattern)
    return _lines(k + 1 if k >= 0 else -1)


def topish_tests(rng):
    t = ["abrakadabra\nkad", "abrakadabra\nabra", "abc\nd", "a\naa", "aaaa\naa", "a" * 10**4 + "\n" + "a" * 99 + "b"]
    for _ in range(16):
        text = _word(rng, rng.randint(1, 10**4), rng.choice(["ab", "abc", string.ascii_lowercase]))
        if rng.random() < 0.6:
            i = rng.randint(0, len(text) - 1)
            pattern = text[i:i + rng.randint(1, 100)]
        else:
            pattern = _word(rng, rng.randint(1, 100), "abc")
        t.append(f"{text}\n{pattern}")
    return t


def teskari_solve(inp):
    return _lines(" ".join(w[::-1] for w in inp.split()))


def teskari_tests(rng):
    t = ["Salom dunyo", "a", "Men kod yozaman", "ABBA qoq", "x" * 1000]
    for _ in range(17):
        words, total = [], 0
        cap = rng.choice([20, 100, 1000])
        while True:
            w = _word(rng, rng.randint(1, 10), string.ascii_letters)
            if total + len(w) + 1 > cap:
                break
            words.append(w)
            total += len(w) + 1
        t.append(" ".join(words or ["a"]))
    return t


# ============================== Easy ==============================

def yoqolgan_solve(inp):
    n, *a = _ints(inp)
    return _lines(n * (n + 1) // 2 - sum(a))


def yoqolgan_tests(rng):
    def case(n, missing):
        a = [x for x in range(n + 1) if x != missing]
        rng.shuffle(a)
        return f"{n}\n{_join(a)}"
    t = ["4\n3 0 4 1", "1\n1", "1\n0", "5\n0 1 2 3 4", case(10**5, 0), case(10**5, 10**5)]
    for c in BIG:
        n = _size(rng, c)
        t.append(case(n, rng.randint(0, n)))
    return t


def bir_qosh_solve(inp):
    return _lines(int(inp) + 1)


def bir_qosh_tests(rng):
    t = ["1299", "9", "0", "9" * 1000, "1" + "0" * 999, "899", "123456789012345678901234567890"]
    for _ in range(15):
        n = rng.randint(1, 1000)
        digits = str(rng.randint(1, 9)) + _word(rng, n - 1, string.digits)
        if rng.random() < 0.4:  # a run of nines at the end: the carry has to travel
            k = rng.randint(1, len(digits))
            digits = digits[:-k] + "9" * k
        t.append(digits)
    return t


def zina_solve(inp):
    a, b = 1, 1
    for _ in range(int(inp) - 1):
        a, b = b, a + b
    return _lines(b)


def zina_tests(rng):
    t = ["3", "5", "1", "2", "80", "79"]
    return t + [str(n) for n in rng.sample(range(4, 79), 16)]


def paskal_solve(inp):
    row, rows = [1], []
    for _ in range(int(inp)):
        rows.append(_join(row))
        row = [1] + [x + y for x, y in zip(row, row[1:])] + [1]
    return _lines(*rows)


def paskal_tests(rng):
    return ["4", "1", "30"] + [str(n) for n in rng.sample([k for k in range(2, 30) if k != 4], 17)]


def juftsiz_solve(inp):
    _, *a = _ints(inp)
    x = 0
    for v in a:
        x ^= v
    return _lines(x)


def juftsiz_tests(rng):
    def case(cap):
        k = (_size(rng, cap) - 1) // 2
        vals = set()
        while len(vals) < k + 1:
            vals.add(rng.randint(-10**9, 10**9))
        vals = list(vals)
        a = vals[:k] * 2 + [vals[k]]
        rng.shuffle(a)
        return f"{len(a)}\n{_join(a)}"
    t = ["7\n5 -3 9 5 9 8 8", "1\n42", "3\n0 7 7", "5\n-1000000000 1000000000 1000000000 3 -1000000000"]
    return t + [case(c if c < 10**5 else 99_999) for c in BIG]


def kopchilik_solve(inp):
    _, *a = _ints(inp)
    return _lines(Counter(a).most_common(1)[0][0])


def kopchilik_tests(rng):
    def case(cap):
        n = _size(rng, cap)
        major = rng.randint(-10**9, 10**9)
        k = rng.randint(n // 2 + 1, n)
        a = [major] * k + _arr(rng, n - k, -10**9, 10**9)
        rng.shuffle(a)
        return f"{n}\n{_join(a)}"
    t = ["5\n3 7 3 3 1", "1\n-5", "2\n9 9", "6\n4 4 4 4 1 2", "3\n1 2 2"]
    return t + [case(c) for c in BIG]


def takror_solve(inp):
    n, *a = _ints(inp)
    return _yes(len(set(a)) < n)


def takror_tests(rng):
    def case(cap, dup):
        n = _size(rng, cap)
        if dup and n > 1:
            a = rng.sample(range(-10**9, 10**9 + 1), n - 1)
            a.append(rng.choice(a))
            rng.shuffle(a)
        else:
            a = rng.sample(range(-10**9, 10**9 + 1), n)
        return f"{n}\n{_join(a)}"
    t = ["5\n10 -3 7 -3 2", "4\n1 2 3 4", "1\n5", "2\n0 0"]
    return t + [case(c, i % 2 == 0) for i, c in enumerate(BIG)]


def anagramma_solve(inp):
    a, b = inp.split()
    return _yes(sorted(a) == sorted(b))


def anagramma_tests(rng):
    t = ["kitob\nbotik", "olma\nolam", "salom\nsalam", "a\naa", "ab\nba", "z\nz"]
    for c in BIG:
        a = _word(rng, _size(rng, c), rng.choice(["ab", "abcde", string.ascii_lowercase]))
        b = list(a)
        rng.shuffle(b)
        if rng.random() < 0.5:  # one letter changed: same length, not an anagram (mostly)
            b[rng.randrange(len(b))] = rng.choice(string.ascii_lowercase)
        t.append(f"{a}\n{''.join(b)}")
    return t


def juftlik_solve(inp):
    _, target, *a = _ints(inp)
    seen = {}
    for j, x in enumerate(a, 1):
        if target - x in seen:
            return _lines(f"{seen[target - x]} {j}")
        seen.setdefault(x, j)
    raise ValueError("no pair")


def _pairs(a, target) -> int:
    c = Counter(a)
    return sum(c[x] * c[target - x] for x in c if x < target - x) + sum(
        c[x] * (c[x] - 1) // 2 for x in c if 2 * x == target)


def juftlik_tests(rng):
    def case(cap):
        n = max(2, _size(rng, cap))
        hi = rng.choice([10, 1000]) if n <= 20 else 10**9  # small values only where a unique pair is likely
        while True:
            a = _arr(rng, n, -hi, hi)
            i, j = sorted(rng.sample(range(n), 2))
            target = a[i] + a[j]
            if _pairs(a, target) == 1:
                return f"{n} {target}\n{_join(a)}"
    t = ["5 10\n3 8 1 7 5", "3 6\n3 2 3", "2 0\n-4 4", "4 -3\n-1 5 -2 9",
         "2 2000000000\n1000000000 1000000000"]
    return t + [case(c) for c in BIG]


def birlashtir_solve(inp):
    it = iter(_ints(inp))
    n = next(it)
    a = [next(it) for _ in range(n)]
    m = next(it)
    return _lines(_join(sorted(a + [next(it) for _ in range(m)])))


def birlashtir_tests(rng):
    def case(cap):
        n, m = _size(rng, cap), _size(rng, cap)
        hi = rng.choice([10, 10**9])
        a, b = sorted(_arr(rng, n, -hi, hi)), sorted(_arr(rng, m, -hi, hi))
        return f"{n}\n{_join(a)}\n{m}\n{_join(b)}"
    t = ["3\n1 4 9\n4\n2 4 5 10", "1\n5\n1\n5", "2\n-3 -1\n1\n7", "3\n10 20 30\n2\n1 2"]
    return t + [case(c) for c in BIG]


_ROMAN = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
          (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def _to_roman(n: int) -> str:
    out = []
    for value, sym in _ROMAN:
        k, n = divmod(n, value)
        out.append(sym * k)
    return "".join(out)


def rim_solve(inp):
    v = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    s = inp.strip()
    total = 0
    for i, ch in enumerate(s):
        total += -v[ch] if i + 1 < len(s) and v[ch] < v[s[i + 1]] else v[ch]
    return _lines(total)


def rim_tests(rng):
    t = [_to_roman(n) for n in (2026, 14, 1, 3999, 444, 90, 3888, 4, 9)]
    return t + [_to_roman(rng.randint(1, 3999)) for _ in range(13)]


def boshlanish_solve(inp):
    return _lines(os.path.commonprefix(inp.split()[1:]) or "-")


def boshlanish_tests(rng):
    t = ["3\nkitobxon\nkitob\nkitoblar", "2\nolma\nnok", "1\nsalom", "3\naa\naa\naa", "2\nab\na",
         "200\n" + "\n".join(["z" * 200] * 200)]
    for _ in range(16):
        n = rng.randint(1, 200)
        prefix = _word(rng, rng.randint(0, 50), "ab")
        words = [prefix + _word(rng, rng.randint(0 if prefix else 1, 150), "abc") for _ in range(n)]
        t.append(f"{n}\n" + "\n".join(words))
    return t


def umumiy_solve(inp):
    it = iter(_ints(inp))
    n = next(it)
    a = {next(it) for _ in range(n)}
    m = next(it)
    common = sorted(a & {next(it) for _ in range(m)})
    return _lines(len(common), _join(common)) if common else _lines(0)


def umumiy_tests(rng):
    def case(cap):
        n, m = _size(rng, cap), _size(rng, cap)
        hi = rng.choice([10, 1000, 10**5, 10**9])
        return f"{n}\n{_join(_arr(rng, n, -hi, hi))}\n{m}\n{_join(_arr(rng, m, -hi, hi))}"
    t = ["5\n4 9 5 9 1\n4\n9 4 9 8", "2\n1 2\n2\n3 4", "1\n7\n1\n7", "3\n-1 -1 -1\n2\n-1 0"]
    return t + [case(c) for c in BIG]


def baxtli_solve(inp):
    n, seen = int(inp), set()
    while n != 1 and n not in seen:
        seen.add(n)
        n = sum(int(d) ** 2 for d in str(n))
    return _yes(n == 1)


def baxtli_tests(rng):
    t = ["7", "2", "1", "4", "1000000000", "999999999", "10", "100", "68", "89"]
    return t + [str(rng.randint(1, 10**9)) for _ in range(12)]


def ustun_solve(inp):
    n = 0
    for ch in inp.strip():
        n = n * 26 + ord(ch) - ord("A") + 1
    return _lines(n)


def ustun_tests(rng):
    t = ["AD", "C", "Z", "AA", "A", "ZZZZZZZ", "AZ", "BA", "ZY"]
    return t + [_word(rng, rng.randint(1, 7), string.ascii_uppercase) for _ in range(13)]


def yaxshi_solve(inp):
    _, *a = _ints(inp)
    return _lines(sum(c * (c - 1) // 2 for c in Counter(a).values()))


def yaxshi_tests(rng):
    t = ["6\n5 2 5 5 2 7", "3\n1 2 3", "1\n1", "4\n9 9 9 9", "100000\n" + _join([100] * 10**5)]
    return t + [_arr_case(rng, c, 1, rng.choice([2, 10, 100])) for c in BIG]


def kvadrat_solve(inp):
    _, *a = _ints(inp)
    return _lines(_join(sorted(x * x for x in a)))


def kvadrat_tests(rng):
    t = ["5\n-6 -2 1 3 5", "1\n-7", "3\n0 0 0", "4\n-5 -4 -3 -1", "3\n-10000 0 10000"]
    for c in BIG:
        n = _size(rng, c)
        t.append(f"{n}\n{_join(sorted(_arr(rng, n, -10**4, rng.choice([-1, 0, 10**4]))))}")
    return t


def ildiz_solve(inp):
    return _lines(math.isqrt(int(inp)))


def ildiz_tests(rng):
    t = ["10", "49", "0", "1", "2", "3", str(10**18), str(10**18 - 1), str((10**9 - 1) ** 2),
         str((10**9 - 1) ** 2 - 1), str(2**59)]
    for _ in range(11):
        k = rng.randint(1, 10**9)
        t.append(str(min(10**18, k * k + rng.choice([-1, 0, 1]))) if rng.random() < 0.6
                 else str(rng.randint(0, 10**18)))
    return t


def aksiya_solve(inp):
    _, *p = _ints(inp)
    best, low = 0, p[0]
    for x in p:
        best, low = max(best, x - low), min(low, x)
    return _lines(best)


def aksiya_tests(rng):
    t = ["6\n9 4 6 2 8 5", "4\n5 4 3 1", "1\n100", "2\n1 10000",
         "100000\n" + _join(max(1, 10**4 - i // 10) for i in range(10**5))]  # never rises: no profit
    return t + [_arr_case(rng, c, 1, 10**4) for c in BIG]


def gazeta_solve(inp):
    note, magazine = inp.split()
    return _yes(not Counter(note) - Counter(magazine))


def gazeta_tests(rng):
    t = ["salom\nmoslash", "aab\nab", "a\na", "xyz\nabc", "ab\n" + "a" * 10**5]
    for c in BIG:
        magazine = _word(rng, _size(rng, c), rng.choice(["abc", string.ascii_lowercase]))
        note = list(rng.sample(magazine, rng.randint(1, len(magazine))))
        if rng.random() < 0.5:
            note[rng.randrange(len(note))] = rng.choice(string.ascii_lowercase)
        t.append(f"{''.join(note)}\n{magazine}")
    return t


# ============================== the list ==============================

_ARR_IN = "Birinchi qatorda $n$, ikkinchi qatorda $n$ ta butun son"

PROBLEMS = [
    # ---------- Beginner ----------
    {"slug": "p2-hisobdagi-pul", "title": "Hisobdagi pul", "difficulty": "beginner",
     "tags": ["arrays", "prefix-sums"], "solve": hisob_solve, "tests": hisob_tests,
     "statement": "Bank kartasi $n$ kun ishlatildi. Har kuni hisobga $a_i$ so‘m tushdi (manfiy bo‘lsa — "
                  "shuncha pul yechildi). Boshida hisob bo‘sh edi. Har bir kun oxirida hisobda qancha pul "
                  "bo‘lganini chiqaring.",
     "input": _ARR_IN + " $a_1, \\ldots, a_n$ ($1 \\le n \\le 1000$, $|a_i| \\le 10^6$).",
     "output": "Bitta qatorda probel bilan $n$ ta son: $i$-si — $i$-kun oxiridagi hisob."},
    {"slug": "p2-eng-boy-mijoz", "title": "Eng boy mijoz", "difficulty": "beginner",
     "tags": ["arrays", "loops"], "solve": boy_solve, "tests": boy_tests,
     "statement": "$m$ ta mijozning har biri $n$ ta bankda hisob ochgan. $i$-mijozning $j$-bankdagi puli "
                  "jadvalda berilgan. Mijozning boyligi — barcha banklardagi pullari yig‘indisi. "
                  "Eng boy mijozning boyligini toping.",
     "input": "Birinchi qatorda $m$ va $n$ ($1 \\le m, n \\le 50$). Keyingi $m$ ta qatorning har birida "
              "$n$ ta butun son — mijozning banklardagi puli ($1 \\le a_{ij} \\le 100$).",
     "output": "Eng katta boylikni chiqaring."},
    {"slug": "p2-qimmatbaho-toshlar", "title": "Qimmatbaho toshlar", "difficulty": "beginner",
     "tags": ["strings", "hash-table"], "solve": tosh_solve, "tests": tosh_tests,
     "statement": "Har bir tosh turi bitta lotin harfi bilan belgilangan; katta va kichik harf — har xil "
                  "turlar (`a` va `A` boshqa-boshqa). Qaysi turlar qimmatbaho ekani ma’lum. Qutidagi "
                  "toshlardan nechtasi qimmatbaho?",
     "input": "Birinchi qatorda qimmatbaho turlar — takrorlanmaydigan harflar (1 tadan 52 tagacha). "
              "Ikkinchi qatorda qutidagi toshlar — uzunligi $1$ dan $1000$ gacha bo‘lgan harflar qatori.",
     "output": "Qutidagi qimmatbaho toshlar sonini chiqaring."},
    {"slug": "p2-oxirgi-soz-uzunligi", "title": "Oxirgi so‘z uzunligi", "difficulty": "beginner",
     "tags": ["strings"], "solve": oxirgi_solve, "tests": oxirgi_tests,
     "statement": "Gap lotin harflari va probellardan iborat. So‘zlar orasida bir nechta probel bo‘lishi, "
                  "gap boshida va oxirida ham probel bo‘lishi mumkin. Gapdagi oxirgi so‘z necha harfdan iborat?",
     "input": "Bitta qatorda gap: uzunligi $1000$ dan oshmaydi, kamida bitta so‘z bor.",
     "output": "Oxirgi so‘zning uzunligini chiqaring."},
    {"slug": "p2-ketma-ket-birlar", "title": "Ketma-ket birlar", "difficulty": "beginner",
     "tags": ["arrays", "loops"], "solve": birlar_solve, "tests": birlar_tests,
     "statement": "Sportchi $n$ kun mashq qildi. Har kuni uchun `1` (mashq qildi) yoki `0` (qilmadi) "
                  "yozilgan. Eng uzun uzluksiz mashq seriyasi necha kun davom etgan?",
     "input": _ARR_IN + ", har biri $0$ yoki $1$ ($1 \\le n \\le 1000$).",
     "output": "Eng uzun ketma-ket birlar sonini chiqaring (birlar bo‘lmasa, `0`)."},
    {"slug": "p2-nollarni-oxiriga", "title": "Nollarni oxiriga", "difficulty": "beginner",
     "tags": ["arrays", "two-pointers"], "solve": nol_solve, "tests": nol_tests,
     "statement": "Ro‘yxatdagi barcha nollarni oxiriga o‘tkazing. Noldan farqli sonlarning o‘zaro tartibi "
                  "o‘zgarmasin.",
     "input": _ARR_IN + " ($1 \\le n \\le 1000$, $|a_i| \\le 10^9$).",
     "output": "Bitta qatorda probel bilan yangi tartibdagi $n$ ta son."},
    {"slug": "p2-ikkining-darajasi", "title": "Ikkining darajasimi?", "difficulty": "beginner",
     "tags": ["math", "bit-manipulation"], "solve": ikki_daraja_solve, "tests": ikki_daraja_tests,
     "statement": "$n$ soni ikkining butun darajasimi, ya’ni biror butun $k \\ge 0$ uchun $n = 2^k$ bo‘ladimi?",
     "input": "Bitta butun son $n$ ($1 \\le n \\le 10^{18}$).",
     "output": "Ha bo‘lsa `YES`, aks holda `NO`."},
    {"slug": "p2-takrorlarni-olib-tashlash", "title": "Takrorlarni olib tashlash", "difficulty": "beginner",
     "tags": ["arrays", "two-pointers"], "solve": takrorsiz_solve, "tests": takrorsiz_tests,
     "statement": "Kamaymaydigan tartibda saralangan ro‘yxat berilgan. Har bir sonni bir martadan qoldiring.",
     "input": _ARR_IN + " kamaymaydigan tartibda ($1 \\le n \\le 1000$, $|a_i| \\le 1000$).",
     "output": "Birinchi qatorda $k$ — har xil sonlar soni. Ikkinchi qatorda shu $k$ ta son o‘sish tartibida."},
    {"slug": "p2-sozni-topish", "title": "So‘zni topish", "difficulty": "beginner",
     "tags": ["strings"], "solve": topish_solve, "tests": topish_tests,
     "statement": "Matn va qidirilayotgan so‘z berilgan. So‘z matnda birinchi marta qaysi o‘rindan "
                  "boshlanadi? O‘rinlar $1$ dan raqamlanadi.",
     "input": "Birinchi qatorda matn — kichik lotin harflari, uzunligi $1$ dan $10^4$ gacha. Ikkinchi "
              "qatorda so‘z — kichik lotin harflari, uzunligi $1$ dan $100$ gacha.",
     "output": "Birinchi uchragan o‘rinning raqami; so‘z matnda yo‘q bo‘lsa, `-1`."},
    {"slug": "p2-teskari-sozlar", "title": "Teskari so‘zlar", "difficulty": "beginner",
     "tags": ["strings"], "solve": teskari_solve, "tests": teskari_tests,
     "statement": "Gapdagi har bir so‘zni teskari yozing, so‘zlarning tartibi esa o‘zgarmasin.",
     "input": "Bitta qatorda gap: lotin harflaridan iborat so‘zlar bittadan probel bilan ajratilgan, "
              "boshida va oxirida probel yo‘q. Uzunligi $1000$ dan oshmaydi.",
     "output": "O‘zgartirilgan gapni chiqaring."},
    # ---------- Easy ----------
    {"slug": "p2-yoqolgan-son", "title": "Yo‘qolgan son", "difficulty": "easy",
     "tags": ["math", "arrays"], "solve": yoqolgan_solve, "tests": yoqolgan_tests,
     "statement": "$0$ dan $n$ gacha bo‘lgan $n + 1$ ta sondan bittasi yo‘qolib qoldi, qolgan $n$ tasi "
                  "aralash tartibda berilgan. Qaysi son yo‘qolgan?",
     "input": _ARR_IN + " — $0$ dan $n$ gacha bo‘lgan, har xil sonlar ($1 \\le n \\le 10^5$).",
     "output": "Yo‘qolgan sonni chiqaring."},
    {"slug": "p2-katta-songa-bir", "title": "Katta songa bir qo‘shish", "difficulty": "easy",
     "tags": ["strings", "math"], "solve": bir_qosh_solve, "tests": bir_qosh_tests,
     "statement": "Juda katta manfiy bo‘lmagan butun son berilgan. Unga $1$ qo‘shing. Son oddiy butun "
                  "turlarga sig‘maydi: raqamlari bilan ishlash kerak.",
     "input": "Bitta qatorda son: $1$ tadan $1000$ tagacha raqam, ortiqcha bosh nollarsiz.",
     "output": "Son $+ 1$ ni chiqaring."},
    {"slug": "p2-zinapoya", "title": "Zinapoya", "difficulty": "easy",
     "tags": ["dynamic-programming", "math"], "solve": zina_solve, "tests": zina_tests,
     "statement": "Zinapoya $n$ ta pog‘onadan iborat. Bir qadamda $1$ yoki $2$ pog‘ona chiqish mumkin. "
                  "Eng yuqoriga necha xil usulda chiqish mumkin? Masalan, $n = 3$ da: $1+1+1$, $1+2$, $2+1$.",
     "input": "Bitta butun son $n$ ($1 \\le n \\le 80$).",
     "output": "Usullar sonini chiqaring (64-bitli butun songa sig‘adi)."},
    {"slug": "p2-paskal-uchburchagi", "title": "Paskal uchburchagi", "difficulty": "easy",
     "tags": ["arrays", "combinatorics"], "solve": paskal_solve, "tests": paskal_tests,
     "statement": "Paskal uchburchagining birinchi qatori — `1`. Har bir keyingi qator `1` bilan boshlanib, "
                  "`1` bilan tugaydi, o‘rtadagi har bir son esa yuqoridagi qatorning ikki qo‘shni soni "
                  "yig‘indisi. Birinchi $n$ ta qatorni chiqaring.",
     "input": "Bitta butun son $n$ ($1 \\le n \\le 30$).",
     "output": "$n$ ta qator; $i$-qatorda probel bilan $i$ ta son."},
    {"slug": "p2-juftsiz-son", "title": "Juftsiz qolgan son", "difficulty": "easy",
     "tags": ["bit-manipulation", "hash-table"], "solve": juftsiz_solve, "tests": juftsiz_tests,
     "statement": "Ro‘yxatda bitta sondan tashqari har bir son aynan ikki marta uchraydi, u bitta son esa "
                  "bir marta. O‘sha sonni toping.",
     "input": _ARR_IN + " ($1 \\le n < 10^5$, $n$ toq, $|a_i| \\le 10^9$).",
     "output": "Bir marta uchragan sonni chiqaring."},
    {"slug": "p2-kopchilik-ovozi", "title": "Ko‘pchilik ovozi", "difficulty": "easy",
     "tags": ["arrays", "hash-table"], "solve": kopchilik_solve, "tests": kopchilik_tests,
     "statement": "Saylovda $n$ ta ovoz berildi, har bir ovoz — nomzodning raqami. Bitta nomzod "
                  "ovozlarning yarmidan ko‘pini olgani ma’lum. U qaysi nomzod?",
     "input": _ARR_IN + " — nomzodlar raqami ($1 \\le n \\le 10^5$, $|a_i| \\le 10^9$). Bitta son "
              "$n / 2$ martadan ko‘p uchraydi.",
     "output": "Ko‘pchilik ovoz olgan nomzodning raqamini chiqaring."},
    {"slug": "p2-takror-bormi", "title": "Takror bormi?", "difficulty": "easy",
     "tags": ["hash-table", "sorting"], "solve": takror_solve, "tests": takror_tests,
     "statement": "Ro‘yxatda kamida bitta son ikki yoki undan ko‘p marta uchraydimi?",
     "input": _ARR_IN + " ($1 \\le n \\le 10^5$, $|a_i| \\le 10^9$).",
     "output": "Takror bo‘lsa `YES`, barcha sonlar har xil bo‘lsa `NO`."},
    {"slug": "p2-anagramma", "title": "Anagramma", "difficulty": "easy",
     "tags": ["strings", "hash-table"], "solve": anagramma_solve, "tests": anagramma_tests,
     "statement": "Ikki so‘z bir xil harflardan (har bir harf bir xil miqdorda) tuzilgan bo‘lsa, ular "
                  "anagramma. Masalan, `kitob` va `botik`. Berilgan ikki so‘z anagrammami?",
     "input": "Ikki qatorda ikki so‘z — kichik lotin harflari, har birining uzunligi $1$ dan $10^5$ gacha.",
     "output": "Anagramma bo‘lsa `YES`, aks holda `NO`."},
    {"slug": "p2-kerakli-juftlik", "title": "Kerakli juftlik", "difficulty": "easy",
     "tags": ["hash-table", "arrays"], "solve": juftlik_solve, "tests": juftlik_tests,
     "statement": "Ro‘yxatdan yig‘indisi $t$ ga teng bo‘lgan ikki sonni toping: $i < j$ va "
                  "$a_i + a_j = t$. Bunday juftlik aynan bitta ekani kafolatlanadi. Hamma juftlikni "
                  "tekshirish vaqtga sig‘maydi.",
     "input": "Birinchi qatorda $n$ va $t$ ($2 \\le n \\le 10^5$, $|t| \\le 2 \\cdot 10^9$). Ikkinchi "
              "qatorda $n$ ta butun son ($|a_i| \\le 10^9$).",
     "output": "Probel bilan $i$ va $j$ — sonlarning o‘rni ($1$ dan raqamlanadi, $i < j$)."},
    {"slug": "p2-ikki-saralangan-royxat", "title": "Ikki saralangan ro‘yxat", "difficulty": "easy",
     "tags": ["two-pointers", "sorting"], "solve": birlashtir_solve, "tests": birlashtir_tests,
     "statement": "Ikki ro‘yxat kamaymaydigan tartibda saralangan. Ularni bitta saralangan ro‘yxatga "
                  "birlashtiring.",
     "input": "Birinchi qatorda $n$, ikkinchi qatorda $n$ ta son. Uchinchi qatorda $m$, to‘rtinchi qatorda "
              "$m$ ta son ($1 \\le n, m \\le 10^5$, $|a_i|, |b_i| \\le 10^9$). Ikkala ro‘yxat ham "
              "kamaymaydigan tartibda.",
     "output": "Bitta qatorda probel bilan $n + m$ ta son, kamaymaydigan tartibda."},
    {"slug": "p2-rim-raqamlari", "title": "Rim raqamlari", "difficulty": "easy",
     "tags": ["strings", "implementation"], "solve": rim_solve, "tests": rim_tests,
     "statement": "Rim raqamlari: `I` = 1, `V` = 5, `X` = 10, `L` = 50, `C` = 100, `D` = 500, `M` = 1000. "
                  "Odatda belgilar kattadan kichikka yoziladi va qiymatlari qo‘shiladi: `XVI` = 16. Kichik "
                  "belgi kattasidan oldin kelsa, u ayiriladi: `IV` = 4, `IX` = 9, `XL` = 40, `XC` = 90, "
                  "`CD` = 400, `CM` = 900. Rim raqamida yozilgan sonni odatiy ko‘rinishda chiqaring.",
     "input": "Bitta qatorda to‘g‘ri yozilgan rim raqami; uning qiymati $1$ dan $3999$ gacha.",
     "output": "Sonning qiymatini chiqaring."},
    {"slug": "p2-umumiy-boshlanish", "title": "Umumiy boshlanish", "difficulty": "easy",
     "tags": ["strings"], "solve": boshlanish_solve, "tests": boshlanish_tests,
     "statement": "Bir nechta so‘z berilgan. Ularning barchasi qaysi eng uzun qism bilan boshlanadi?",
     "input": "Birinchi qatorda $n$ ($1 \\le n \\le 200$). Keyingi $n$ ta qatorda bittadan so‘z — kichik "
              "lotin harflari, uzunligi $1$ dan $200$ gacha.",
     "output": "Eng uzun umumiy boshlanishni chiqaring; u bo‘sh bo‘lsa, `-`."},
    {"slug": "p2-umumiy-sonlar", "title": "Ikki ro‘yxatning umumiy sonlari", "difficulty": "easy",
     "tags": ["hash-table", "sorting"], "solve": umumiy_solve, "tests": umumiy_tests,
     "statement": "Ikki ro‘yxatning ikkalasida ham uchraydigan sonlarni toping. Har bir sonni bir marta "
                  "chiqaring.",
     "input": "Birinchi qatorda $n$, ikkinchi qatorda $n$ ta son. Uchinchi qatorda $m$, to‘rtinchi qatorda "
              "$m$ ta son ($1 \\le n, m \\le 10^5$, $|a_i|, |b_i| \\le 10^9$).",
     "output": "Birinchi qatorda $k$ — umumiy sonlar soni. $k > 0$ bo‘lsa, ikkinchi qatorda shu sonlar "
               "o‘sish tartibida."},
    {"slug": "p2-baxtli-son", "title": "Baxtli son", "difficulty": "easy",
     "tags": ["math", "hash-table"], "solve": baxtli_solve, "tests": baxtli_tests,
     "statement": "Son o‘rniga uning raqamlari kvadratlari yig‘indisini yozamiz va buni takrorlaymiz. "
                  "Oxiri $1$ ga kelsa, boshlang‘ich son baxtli; $1$ ga hech qachon yetmasa (sonlar aylanib "
                  "qaytaversa) — baxtli emas. Masalan, $7 \\to 49 \\to 97 \\to 130 \\to 10 \\to 1$, demak "
                  "$7$ baxtli.",
     "input": "Bitta butun son $n$ ($1 \\le n \\le 10^9$).",
     "output": "Baxtli bo‘lsa `YES`, aks holda `NO`."},
    {"slug": "p2-jadval-ustuni", "title": "Jadval ustuni raqami", "difficulty": "easy",
     "tags": ["strings", "math"], "solve": ustun_solve, "tests": ustun_tests,
     "statement": "Elektron jadvalda ustunlar harflar bilan nomlanadi: `A`, `B`, …, `Z`, keyin `AA`, `AB`, "
                  "…, `AZ`, `BA`, …, `ZZ`, `AAA` va hokazo. `A` — 1-ustun, `Z` — 26-ustun, `AA` — 27-ustun. "
                  "Berilgan nom nechanchi ustun?",
     "input": "Bitta qatorda ustun nomi — $1$ tadan $7$ tagacha katta lotin harfi.",
     "output": "Ustun raqamini chiqaring (64-bitli butun songa sig‘adi)."},
    {"slug": "p2-yaxshi-juftliklar", "title": "Yaxshi juftliklar", "difficulty": "easy",
     "tags": ["hash-table", "combinatorics"], "solve": yaxshi_solve, "tests": yaxshi_tests,
     "statement": "$i < j$ va $a_i = a_j$ bo‘lgan $(i, j)$ juftlik yaxshi deyiladi. Ro‘yxatda nechta "
                  "yaxshi juftlik bor?",
     "input": _ARR_IN + " ($1 \\le n \\le 10^5$, $1 \\le a_i \\le 100$).",
     "output": "Yaxshi juftliklar sonini chiqaring (64-bitli butun songa sig‘adi)."},
    {"slug": "p2-kvadratlar-tartibi", "title": "Kvadratlar tartibi", "difficulty": "easy",
     "tags": ["two-pointers", "sorting"], "solve": kvadrat_solve, "tests": kvadrat_tests,
     "statement": "Kamaymaydigan tartibda saralangan ro‘yxatdagi har bir sonni kvadratga ko‘taring va "
                  "natijani ham kamaymaydigan tartibda chiqaring. Manfiy sonlar ham bor!",
     "input": _ARR_IN + " kamaymaydigan tartibda ($1 \\le n \\le 10^5$, $|a_i| \\le 10^4$).",
     "output": "Bitta qatorda probel bilan $n$ ta kvadrat, kamaymaydigan tartibda."},
    {"slug": "p2-butun-ildiz", "title": "Butun ildiz", "difficulty": "easy",
     "tags": ["math", "binary-search"], "solve": ildiz_solve, "tests": ildiz_tests,
     "statement": "$x$ ning kvadrat ildizining butun qismini toping: $k^2 \\le x$ bo‘ladigan eng katta "
                  "butun $k$. Ehtiyot bo‘ling: katta sonlarda haqiqiy sonli `sqrt` adashishi mumkin.",
     "input": "Bitta butun son $x$ ($0 \\le x \\le 10^{18}$).",
     "output": "$k$ ni chiqaring."},
    {"slug": "p2-aksiya-savdosi", "title": "Aksiya savdosi", "difficulty": "easy",
     "tags": ["greedy", "arrays"], "solve": aksiya_solve, "tests": aksiya_tests,
     "statement": "$n$ kun davomida bitta aksiyaning narxi ma’lum: $i$-kuni $p_i$. Bir kuni aksiyani "
                  "sotib olib, undan keyingi biror kuni sotmoqchisiz. Eng ko‘p foyda qancha? Foyda "
                  "chiqmasa, hech narsa qilmaysiz va foyda $0$.",
     "input": _ARR_IN + " — narxlar ($1 \\le n \\le 10^5$, $1 \\le p_i \\le 10^4$).",
     "output": "Eng katta foydani chiqaring."},
    {"slug": "p2-gazetadan-xat", "title": "Gazetadan xat", "difficulty": "easy",
     "tags": ["strings", "hash-table"], "solve": gazeta_solve, "tests": gazeta_tests,
     "statement": "Xatni gazetadan qirqib olingan harflardan yopishtirib yasamoqchisiz. Gazetadagi har bir "
                  "harfni faqat bir marta ishlatish mumkin. Xatni yasab bo‘ladimi?",
     "input": "Birinchi qatorda xat matni, ikkinchi qatorda gazeta matni — kichik lotin harflari, "
              "har birining uzunligi $1$ dan $10^5$ gacha.",
     "output": "Yasab bo‘lsa `YES`, aks holda `NO`."},
]


def _unique(tests):
    """Small random cases can repeat a fixed one; each input is judged once."""
    return lambda rng: list(dict.fromkeys(tests(rng)))


for _spec in PROBLEMS:
    _spec["tests"] = _unique(_spec["tests"])


class Command(Pack1Command):
    help = "Adds 30 Beginner/Easy classics (arrays, strings, hash sets, two pointers, bits)."
    problems = PROBLEMS
    ml_mb = 64
