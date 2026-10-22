"""CodeArena Marathon #3: Marathon #2's format (rated, 120-minute personal clock, Codeforces scoring) with a theme: seven
of the ten hidden problems are about strings (A, C, D, E, G, I, J), three are not (B, F, H). From very easy Beginner
(vowels, upper vs lower case) through a Caesar cipher, run-length coding, a stack of adjacent pairs, a sliding window,
to a deciding Medium (the shortest period of a string, prefix function). None repeats a problem already on the portal.

Every expected output comes from a reference solution here, never typed by hand. Safe to re-run: problems that
already exist (by slug) are reused, not duplicated.

    python manage.py add_codearena_marathon_3 --start "2026-10-23 08:00" --end "2026-10-26 08:00" [--minutes 120]
        [--author admin] [--dry-run]
"""
import string
from math import isqrt

from apps.contests.management.commands.add_codearena_marathon_1 import _arr, _size, _uniq
from apps.contests.management.commands.add_codearena_marathon_2 import Command as MarathonCommand
from apps.contests.management.commands.add_weekend_contest_1 import _lines

TITLE = "CodeArena Marathon #3"
BADGE = "Marathon #3"
DESCRIPTION = """**Marafon #3: 10 ta masala, sizga 120 daqiqa.** Bu safar masalalarning ko‘pchiligi **satrlar** ustida. Musobaqa bir necha kun ochiq, lekin vaqtingiz — **«Boshlash» tugmasini bosgan paytdan 120 daqiqa**. Qulay paytda boshlang, soat to‘xtamaydi va qayta boshlanmaydi.

- **Reytingli**: natija reytingingizga ta’sir qiladi. Reyting musobaqa tugagach hisoblanadi.
- Masalalar «Boshlash»dan keyin ochiladi. Natijalar jadvali musobaqa tugagach ochiladi: hamma o‘z vaqtida boshlaydi, shuning uchun boshqalarning natijasi oldindan ko‘rinmaydi.
- **Codeforces qoidasi**: masala bahosi sizning soatingiz o‘tishi bilan kamayadi (120 daqiqa oxirida taxminan yarmigacha), har bir noto‘g‘ri urinish **−50 ball**, lekin baho boshlang‘ich bahoning 30% idan pastga tushmaydi. Vaqt «Boshlash»dan hisoblanadi. Birinchi testda xato qilish jarima bermaydi.
- **Nishon**: kamida bitta masala yechgan har bir ishtirokchi profiliga «Marathon #3» nishoni qo‘shiladi, birinchi uchtalikka — medal.
- Halollik qoidalari amal qiladi: kod o‘zingizniki bo‘lsin; masalalarni va yechimlarni boshqalarga yubormang, AI yoki boshqa birovning yechimi taqiqlanadi. Shubhali yechimlar diskvalifikatsiyaga olinadi."""

LOWER = string.ascii_lowercase


def _text(rng, n, alphabet=LOWER):
    return "".join(rng.choice(alphabet) for _ in range(n))


# ---- A. Juda oson (satr): unli harflar ---------------------------------------------------
def vowels_solve(inp):
    return _lines(sum(1 for ch in inp.strip() if ch in "aeiou"))


def vowels_tests(rng):
    tests = ["salom", "kompyuter", "rhythm", "aeiou", "a", "y", "bcdfg", "yyyyy", "aaaaa", "programmer", "qwrtpsdfghjklzxcvbnm",
             "a" * 100, "b" * 100, "ey", "oyoyoy", "uzbekiston", "xayr", "queue"]
    for _ in range(10):
        n = rng.choice([rng.randint(1, 10), rng.randint(1, 100), 100])
        tests.append(_text(rng, n, rng.choice([LOWER, "aeiouy", "bcdfgaeiou", "xyz"])))
    return _uniq(tests)


# ---- B. Juda oson: eng arzoni tekin ------------------------------------------------------
def free_solve(inp):
    prices = list(map(int, inp.split()))
    return _lines(sum(prices) - min(prices))


def free_tests(rng):
    tests = ["120 80 100", "50 50 50", "1 1 1", "1000000 1000000 1000000", "1 1000000 1000000", "5 3 3", "3 3 5",
             "9 8 7", "7 8 9", "8 7 9", "1 2 3", "100 1 100", "999999 1000000 1"]
    for _ in range(12):
        tests.append(" ".join(str(rng.choice([rng.randint(1, 20), rng.randint(1, 10**6)])) for _ in range(3)))
    return _uniq(tests)


# ---- C. Beginner (satr): harflar jangi ---------------------------------------------------
def duel_solve(inp):
    s = inp.strip()
    big = sum(1 for ch in s if ch.isupper())
    small = sum(1 for ch in s if ch.islower())
    return _lines("KATTA" if big > small else "KICHIK" if small > big else "TENG")


def duel_tests(rng):
    tests = ["Salom2026", "WIFIgo123", "12345", "a", "A", "aA", "Aa1", "ABC123abc", "0", "AAAa", "aaaA", "ZZ99zz",
             "x" * 100, "X" * 100, "7" * 100, "Ab" * 50, "AAb1", "aab1", "QWERTYuiop"]
    for _ in range(10):
        n = rng.choice([rng.randint(1, 8), rng.randint(1, 100), 100])
        alphabet = rng.choice([string.ascii_letters + string.digits, string.ascii_letters, "ABab12", "Aa000000"])
        tests.append(_text(rng, n, alphabet))
    return _uniq(tests)


# ---- D. Beginner (satr): maxfiy xat ------------------------------------------------------
def caesar_solve(inp):
    k, text = inp.split("\n")[:2]
    k = int(k) % 26
    return _lines("".join(" " if ch == " " else chr((ord(ch) - 97 + k) % 26 + 97) for ch in text))


def caesar_tests(rng):
    def case(k, text):
        return f"{k}\n{text}"
    tests = [case(3, "salom dunyo"), case(25, "abc xyz"), case(0, "hello world"), case(26, "hello world"),
             case(52, "abc"), case(13, "abcdefghijklmnopqrstuvwxyz"), case(1, "z"), case(1000, "codearena"),
             case(1, "zzzz zzzz"), case(5, "a"), case(25, "a b c"), case(12, "x" * 100), case(10, "ab " * 33 + "a"),
             case(999, "marafon uchun omad")]
    for _ in range(10):
        words = [_text(rng, rng.randint(1, 8)) for _ in range(rng.randint(1, 12))]
        tests.append(case(rng.choice([rng.randint(0, 25), rng.randint(0, 1000)]), " ".join(words)[:100].strip()))
    return _uniq(tests)


# ---- E. Easy (satr): siqish --------------------------------------------------------------
def runs_solve(inp):
    s = inp.strip()
    out, i = [], 0
    while i < len(s):
        j = i
        while j < len(s) and s[j] == s[i]:
            j += 1
        out.append(f"{s[i]}{j - i}")
        i = j
    return _lines("".join(out))


def runs_tests(rng):
    tests = ["aaabccdd", "abc", "a", "a" * 12, "a" * 9, "a" * 10, "ab" * 5, "zzzzzzzzzzzzzzzzzzzzbzz", "aabbaabb",
             "a" * 100000, "ab" * 50000, "a" * 99999 + "b", "b" + "a" * 99999, "abcdefghijklmnopqrstuvwxyz"]
    for _ in range(12):
        n = _size(rng, 20, 2000, 10**5)
        runs, total = [], 0
        while total < n:
            r = rng.choice([1, 1, 2, 3, 5, 9, 10, 11, 100])
            runs.append(rng.choice(LOWER[: rng.choice([2, 3, 26])]) * r)
            total += r
        tests.append("".join(runs)[: max(1, n)])
    return _uniq(tests)


# ---- F. Easy: manfiy balans --------------------------------------------------------------
def balance_solve(inp):
    lines = inp.split("\n")
    n, bal = map(int, lines[0].split())
    for i, d in enumerate(map(int, lines[1].split()), start=1):
        bal += d
        if bal < 0:
            return _lines(i)
    return _lines(-1)


def balance_tests(rng):
    def case(b, d):
        return f"{len(d)} {b}\n{_arr(d)}"
    tests = [case(100, [-30, -50, 20, -60, 10]), case(50, [-50, 10, -10, 5]), case(0, [-1]), case(0, [1]),
             case(0, [0]), case(5, [-5]), case(5, [-6]), case(10, [-10, -1]), case(10, [-5, -5, 5, 5, -11]),
             case(10**9, [-10**4] * 10**5), case(0, [10**4] * 10**5), case(0, [10**4] * 99999 + [-10**9]),
             case(0, [1] * 99999 + [-100000]), case(7, [3, -10, 4])]
    for _ in range(12):
        n = _size(rng, 8, 500, 10**5)
        start = rng.choice([0, rng.randint(0, 50), rng.randint(0, 10**4)])
        span = rng.choice([3, 20, 10**4])
        tests.append(case(start, [rng.randint(-span, rng.choice([0, 1, span // 2, span])) for _ in range(n)]))
    return _uniq(tests)


# ---- G. Easy (satr): juftlarni o'chirish -------------------------------------------------
def pairs_solve(inp):
    stack = []
    for ch in inp.strip():
        if stack and stack[-1] == ch:
            stack.pop()
        else:
            stack.append(ch)
    return _lines("".join(stack) or "EMPTY")


def pairs_tests(rng):
    def nested(n):
        half = _text(rng, n, "abc")
        return half + half[::-1]
    tests = ["abbac", "abccba", "a", "aa", "aaa", "ab", "abab", "aabb", "abba", "abbabba", "aabcc", "baab",
             "a" * 200000, "a" * 199999, "ab" * 100000, "z" + "ab" * 99999 + "z", nested(100000), nested(100000)[:-1] + "x"]
    tests = [t if len(t) <= 2 * 10**5 else t[: 2 * 10**5] for t in tests]
    for _ in range(12):
        n = _size(rng, 10, 1000, 2 * 10**5)
        kind = rng.choice(["rand2", "rand3", "nested", "rand26"])
        if kind == "nested":
            s = nested(max(1, n // 2))
            if rng.random() < 0.5:
                i = rng.randrange(len(s))
                s = s[:i] + rng.choice("abcd") + s[i:]
        else:
            s = _text(rng, n, {"rand2": "ab", "rand3": "abc", "rand26": LOWER}[kind])
        tests.append(s[: 2 * 10**5])
    return _uniq(tests)


# ---- H. Easy: stakan piramidasi (64-bit) -------------------------------------------------
def pyramid_solve(inp):
    n = int(inp)
    return _lines((isqrt(8 * n + 1) - 1) // 2)  # the largest k with k(k+1)/2 <= n


def pyramid_tests(rng):
    top = 10**18
    tests = ["10", "20", "1", "2", "3", "4", "5", "6", "7", "15", "21", "55", str(top), str(top - 1)]
    for k in (10**4, 10**6, 10**9, 1414213561, 1414213560, 1414213559):
        t = k * (k + 1) // 2
        tests += [str(t - 1), str(t), str(t + 1)]
    for _ in range(8):
        tests.append(str(rng.choice([rng.randint(1, 10**4), rng.randint(1, 10**9), rng.randint(1, top)])))
    return _uniq([t for t in tests if 1 <= int(t) <= top])


# ---- I. Easy-medium (satr): eng uzun tasma -----------------------------------------------
def ribbon_solve(inp):
    k, s = inp.split("\n")[:2]
    k, s = int(k), s.strip()
    count, left, best = {}, 0, 0
    for right, ch in enumerate(s):
        count[ch] = count.get(ch, 0) + 1
        while len(count) > k:
            count[s[left]] -= 1
            if count[s[left]] == 0:
                del count[s[left]]
            left += 1
        best = max(best, right - left + 1)
    return _lines(best)


def ribbon_tests(rng):
    def case(k, s):
        return f"{k}\n{s}"
    tests = [case(2, "abcba"), case(3, "abcd"), case(1, "a"), case(1, "aabbbc"), case(26, "abcdefghijklmnopqrstuvwxyz"),
             case(26, "ab" * 10), case(2, "abababab"), case(2, "aabcccddd"), case(3, "abcabcabc"),
             case(1, "a" * 200000), case(1, "ab" * 100000), case(2, "ab" * 100000), case(3, "ab" * 99999 + "cd"),
             case(5, "abcdefghij" * 20000), case(26, LOWER * 7000), case(4, "z" + "a" * 199998 + "y")]
    for _ in range(12):
        n = _size(rng, 12, 1500, 2 * 10**5)
        alphabet = rng.choice([2, 3, 5, 26])
        tests.append(case(rng.randint(1, min(26, alphabet + 1)), _text(rng, n, LOWER[:alphabet])))
    return _uniq(tests)


# ---- J. Medium (hal qiluvchi, satr): naqsh -----------------------------------------------
def period_solve(inp):
    s = inp.strip()
    n = len(s)
    pi = [0] * n
    for i in range(1, n):
        j = pi[i - 1]
        while j and s[i] != s[j]:
            j = pi[j - 1]
        pi[i] = j + (s[i] == s[j])
    return _lines(n - pi[-1])  # the border of the whole string decides the shortest shift


def period_tests(rng):
    def repeated(block, n):
        return (block * (n // len(block) + 1))[:n]
    tests = ["abcabcab", "abcd", "a", "aa", "ab", "aba", "abab", "ababa", "aabaab", "aabaa", "abcabc", "abaab", "xyzxyzxy",
             "a" * 200000, "a" * 199999 + "b", "b" + "a" * 199999, "ab" * 100000, "ab" * 99999 + "a",
             repeated("abc", 200000), repeated("abcab", 199999), repeated(_text(rng, 777), 200000)]
    for _ in range(12):
        n = _size(rng, 12, 1500, 2 * 10**5)
        block = _text(rng, rng.randint(1, max(1, n // rng.choice([1, 2, 3, 10]))), rng.choice(["ab", "abc", LOWER]))
        s = repeated(block, n)
        if rng.random() < 0.4:  # one letter off: the pattern breaks and the period jumps up
            i = rng.randrange(n)
            s = s[:i] + ("b" if s[i] == "a" else "a") + s[i + 1:]
        tests.append(s)
    return _uniq(tests)


PROBLEMS = [
    {
        "slug": "cam3-unlilar", "title": "Unlilar", "difficulty": "beginner", "points": 200,
        "tags": ["strings", "for-loop"], "solve": vowels_solve, "tests": vowels_tests, "samples": 2,
        "statement": ("Sardor Telegram uchun bot yozmoqchi. Bot foydalanuvchi yuborgan so‘zdagi **unli harflar** "
                      "sonini aytishi kerak. Unli harflar: `a`, `e`, `i`, `o`, `u`. Qolgan hamma harf, jumladan `y` ham, "
                      "undosh hisoblanadi.\n\n"
                      "So‘zda nechta unli harf bor?"),
        "input": "Bitta qatorda kichik lotin harflaridan iborat so‘z $s$ ($1 \\le |s| \\le 100$).",
        "output": "Bitta butun son: unli harflar soni.",
    },
    {
        "slug": "cam3-eng-arzoni-tekin", "title": "Eng arzoni tekin", "difficulty": "beginner", "points": 200,
        "tags": ["conditionals", "arithmetic"], "solve": free_solve, "tests": free_tests, "samples": 2,
        "statement": ("Do‘konda aksiya: **uchta mahsulot** birga olinsa, ulardan **eng arzoni tekin** beriladi. "
                      "Agar eng arzon narx bir nechta mahsulotda takrorlansa, baribir bittasi tekin bo‘ladi.\n\n"
                      "Mahsulotlarning narxlari $a$, $b$ va $c$ so‘m. Uchalasini birga olgan xaridor necha so‘m to‘laydi?"),
        "input": "Bitta qatorda uchta butun son: $a$, $b$ va $c$ ($1 \\le a, b, c \\le 10^6$).",
        "output": "Bitta butun son: xaridor to‘laydigan summa.",
    },
    {
        "slug": "cam3-harflar-jangi", "title": "Harflar jangi", "difficulty": "beginner", "points": 250,
        "tags": ["strings", "conditionals"], "solve": duel_solve, "tests": duel_tests, "samples": 2,
        "statement": ("Parol qatori lotin harflari va raqamlardan iborat. Harflar orasida **katta** (`A`–`Z`) va "
                      "**kichik** (`a`–`z`) harflar bor; raqamlar hisobga kirmaydi.\n\n"
                      "Qaysi biri ko‘p? Katta harflar ko‘p bo‘lsa `KATTA`, kichiklari ko‘p bo‘lsa `KICHIK`, "
                      "teng bo‘lsa `TENG` chiqaring."),
        "input": "Bitta qatorda satr $s$ ($1 \\le |s| \\le 100$): faqat lotin harflari va raqamlar.",
        "output": "`KATTA`, `KICHIK` yoki `TENG`.",
    },
    {
        "slug": "cam3-maxfiy-xat", "title": "Maxfiy xat", "difficulty": "beginner", "points": 300,
        "tags": ["strings", "math"], "solve": caesar_solve, "tests": caesar_tests, "samples": 2,
        "statement": ("Ikki do‘st maxfiy xat yozishadi. Shifrlash oddiy: matndagi **har bir harf** alifboda $k$ qadam "
                      "**oldinga** suriladi (`a` → `b` → … → `z` → yana `a`). Probellar o‘zgarmaydi.\n\n"
                      "Masalan, $k = 3$ bo‘lsa, `xyz` so‘zi `abc` bo‘ladi.\n\n"
                      "Matnni shifrlab bering. Alifbo $26$ ta harfdan iborat."),
        "input": ("* Birinchi qatorda butun son $k$ ($0 \\le k \\le 1000$) beriladi.\n"
                  "* Ikkinchi qatorda matn: kichik lotin harflari va probellar, so‘zlar orasida bitta probel, "
                  "boshida va oxirida probel yo‘q ($1 \\le |s| \\le 100$)."),
        "output": "Bitta qatorda shifrlangan matn.",
    },
    {
        "slug": "cam3-siqish", "title": "Siqish", "difficulty": "easy", "points": 400,
        "tags": ["strings", "implementation"], "solve": runs_solve, "tests": runs_tests, "samples": 2,
        "statement": ("Faks apparati uzun satrlarni siqib yuboradi: bir xil harflarning har bir **ketma-ket guruhi** "
                      "harf va uning guruhdagi soni bilan almashtiriladi. Masalan, `aaabccdd` satri `a3b1c2d2` "
                      "bo‘ladi. Bitta turgan harf ham `1` bilan yoziladi.\n\n"
                      "Berilgan satrning siqilgan ko‘rinishini chiqaring."),
        "input": "Bitta qatorda kichik lotin harflaridan iborat satr $s$ ($1 \\le |s| \\le 10^5$).",
        "output": "Bitta qatorda siqilgan satr.",
    },
    {
        "slug": "cam3-manfiy-balans", "title": "Manfiy balans", "difficulty": "easy", "points": 500,
        "tags": ["arrays", "simulation"], "solve": balance_solve, "tests": balance_tests, "samples": 2,
        "statement": ("Kartadagi balans $b$ so‘m. Keyingi $n$ kun davomida har kuni bitta amal bo‘ladi: $d_i > 0$ bo‘lsa "
                      "hisob to‘ldiriladi, $d_i < 0$ bo‘lsa pul yechiladi, $d_i = 0$ bo‘lsa hech narsa o‘zgarmaydi. "
                      "Amallar kun tartibida bajariladi.\n\n"
                      "Balans **birinchi marta noldan kichik** (manfiy) bo‘lgan kunning raqamini toping. "
                      "Balans aynan nolga teng bo‘lsa, u manfiy emas. Hech qachon manfiy bo‘lmasa, $-1$ chiqaring."),
        "input": ("* Birinchi qatorda $n$ va $b$ ($1 \\le n \\le 10^5$, $0 \\le b \\le 10^9$) beriladi.\n"
                  "* Ikkinchi qatorda $n$ ta butun son $d_1, \\ldots, d_n$ ($|d_i| \\le 10^9$) bo‘shliq bilan "
                  "ajratilgan holda beriladi."),
        "output": "Bitta butun son: balans birinchi marta manfiy bo‘lgan kun raqami yoki $-1$.",
    },
    {
        "slug": "cam3-juftlarni-ochirish", "title": "Juftlarni o‘chirish", "difficulty": "easy", "points": 650,
        "tags": ["strings", "stack"], "solve": pairs_solve, "tests": pairs_tests, "samples": 2,
        "statement": ("Matn terish dasturida g‘alati xato bor: yonma-yon turgan **ikkita bir xil harf** bir-birini "
                      "yo‘q qiladi. Shundan keyin ularning ikki yonidagi harflar yonma-yon bo‘lib qolishi mumkin va "
                      "ular ham bir xil bo‘lsa, yana yo‘q bo‘ladi. Bu jarayon boshqa yo‘q bo‘ladigan juft qolmaguncha "
                      "davom etadi.\n\n"
                      "Masalan, `abbac` → `aac` → `c`.\n\n"
                      "Oxirida qanday satr qoladi? Hech narsa qolmasa, `EMPTY` chiqaring."),
        "input": "Bitta qatorda kichik lotin harflaridan iborat satr $s$ ($1 \\le |s| \\le 2 \\cdot 10^5$).",
        "output": "Bitta qatorda qolgan satr yoki `EMPTY`.",
    },
    {
        "slug": "cam3-stakan-piramidasi", "title": "Stakan piramidasi", "difficulty": "easy", "points": 750,
        "tags": ["math", "binary-search"], "solve": pyramid_solve, "tests": pyramid_tests, "samples": 2,
        "statement": ("Bayramda stakanlardan piramida quriladi: birinchi qatorda $1$ ta, ikkinchisida $2$ ta, "
                      "uchinchisida $3$ ta va hokazo — har keyingi qatorda avvalgisidan bittaga ko‘p stakan.\n\n"
                      "Qatorni **to‘liq** qilib qo‘yish kerak: yarim qator bo‘lmaydi. Omborda $n$ ta stakan bor. "
                      "Ulardan nechta to‘liq qator yasash mumkin?"),
        "input": "Bitta qatorda butun son $n$ ($1 \\le n \\le 10^{18}$).",
        "output": "Bitta butun son: to‘liq qatorlarning eng ko‘p soni.",
    },
    {
        "slug": "cam3-eng-uzun-tasma", "title": "Eng uzun tasma", "difficulty": "easy", "points": 900,
        "tags": ["strings", "two-pointers"], "solve": ribbon_solve, "tests": ribbon_tests, "samples": 2,
        "statement": ("Bayroqlar tasmasi $s$ satr ko‘rinishida: har bir kichik lotin harfi bir rangni bildiradi. "
                      "Dizayner tasmadan **ketma-ket** bo‘lakni kesib olmoqchi, lekin unda **ko‘pi bilan $k$ xil rang** "
                      "bo‘lishi kerak (bir rang bir necha marta uchrashi mumkin).\n\n"
                      "Kesib olinadigan bo‘lakning eng katta uzunligi qancha?"),
        "input": ("* Birinchi qatorda butun son $k$ ($1 \\le k \\le 26$) beriladi.\n"
                  "* Ikkinchi qatorda kichik lotin harflaridan iborat satr $s$ ($1 \\le |s| \\le 2 \\cdot 10^5$)."),
        "output": "Bitta butun son: bo‘lakning eng katta uzunligi.",
    },
    {
        "slug": "cam3-naqsh", "title": "Naqsh", "difficulty": "medium", "points": 1100,
        "tl_ms": 1000, "tags": ["strings", "prefix-function"], "solve": period_solve, "tests": period_tests, "samples": 2,
        "statement": ("Gilam to‘quvchi bir xil naqshni qayta-qayta to‘qiydi: ma’lum uzunlikdagi bo‘lakni yonma-yon "
                      "takrorlaydi. Lekin gilam qirqib olinganda oxirgi takror **chala qolishi mumkin**.\n\n"
                      "Gilam $s$ satr bilan berilgan. **Naqsh uzunligi** — shunday eng kichik $p$ ($1 \\le p \\le |s|$)ki, "
                      "satrning hamma joyida $s_i = s_{i+p}$ bo‘lsin (ikkala indeks ham satr ichida bo‘lganda).\n\n"
                      "Masalan, `abcabcab` satrida naqsh `abc`, uzunligi $3$. `abcd` satrida takror yo‘q: naqsh "
                      "butun satr, javob $4$.\n\n"
                      "Naqsh uzunligini toping."),
        "input": "Bitta qatorda kichik lotin harflaridan iborat satr $s$ ($1 \\le |s| \\le 2 \\cdot 10^5$).",
        "output": "Bitta butun son: naqsh uzunligi $p$.",
    },
]


class Command(MarathonCommand):
    help = ("Creates CodeArena Marathon #3 (rated, 120-minute personal clock, seven of ten problems on strings) "
            "if needed and attaches its 10 problems (hidden) as A..J.")
    title, badge, description, problems, prefix = TITLE, BADGE, DESCRIPTION, PROBLEMS, "cam3-"
