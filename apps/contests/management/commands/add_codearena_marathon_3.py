"""CodeArena Marathon #3: Marathon #2's format (rated, 120-minute personal clock, Codeforces scoring) with a theme: seven
of the ten hidden problems are about strings (A, C, D, E, G, I, J), three are not (B, F, H). Easy throughout: every
problem is a few lines, small inputs, one small trap each (ties, digits, wrap-around, a boundary), from vowels and upper vs
lower case up to the deciding J (the shortest repeating block of a string). None repeats a problem already on the portal.

Every problem and the contest also get an English version, stored as unconfirmed drafts (an admin confirms them at
/moderation/translations/). Texts that already have a translation are left alone on a re-run.

Every expected output comes from a reference solution here, never typed by hand. Safe to re-run: problems that
already exist (by slug) are reused, not duplicated.

    python manage.py add_codearena_marathon_3 --start "2026-10-23 08:00" --end "2026-10-26 08:00" [--minutes 120]
        [--author admin] [--dry-run]
"""
import string
from math import isqrt

from django.contrib.contenttypes.models import ContentType

from apps.contests.management.commands.add_codearena_marathon_1 import _arr, _size, _uniq
from apps.contests.management.commands.add_codearena_marathon_2 import Command as MarathonCommand
from apps.contests.management.commands.add_weekend_contest_1 import _lines
from apps.contests.models import Contest
from apps.problems.models import Problem
from apps.translations import service
from apps.translations.models import ContentTranslation

TITLE = "CodeArena Marathon #3"
BADGE = "Marathon #3"
DESCRIPTION = """**Marafon #3: 10 ta masala, sizga 120 daqiqa.** Bu safar masalalarning ko‘pchiligi **satrlar** ustida. Musobaqa bir necha kun ochiq, lekin vaqtingiz — **«Boshlash» tugmasini bosgan paytdan 120 daqiqa**. Qulay paytda boshlang, soat to‘xtamaydi va qayta boshlanmaydi.

- **Reytingli**: natija reytingingizga ta’sir qiladi. Reyting musobaqa tugagach hisoblanadi.
- Masalalar «Boshlash»dan keyin ochiladi. Natijalar jadvali musobaqa tugagach ochiladi: hamma o‘z vaqtida boshlaydi, shuning uchun boshqalarning natijasi oldindan ko‘rinmaydi.
- **Codeforces qoidasi**: masala bahosi sizning soatingiz o‘tishi bilan kamayadi (120 daqiqa oxirida taxminan yarmigacha), har bir noto‘g‘ri urinish **−50 ball**, lekin baho boshlang‘ich bahoning 30% idan pastga tushmaydi. Vaqt «Boshlash»dan hisoblanadi. Birinchi testda xato qilish jarima bermaydi.
- **Nishon**: kamida bitta masala yechgan har bir ishtirokchi profiliga «Marathon #3» nishoni qo‘shiladi, birinchi uchtalikka — medal.
- Halollik qoidalari amal qiladi: kod o‘zingizniki bo‘lsin; masalalarni va yechimlarni boshqalarga yubormang, AI yoki boshqa birovning yechimi taqiqlanadi. Shubhali yechimlar diskvalifikatsiyaga olinadi."""
DESCRIPTION_EN = """**Marathon #3: 10 problems, 120 minutes for you.** This time most of the problems are about **strings**. The contest stays open for several days, but your time is **120 minutes from the moment you press "Start"**. Begin whenever suits you: the clock does not stop and cannot be restarted.

- **Rated**: the result affects your rating. Ratings are calculated after the contest ends.
- The problems open after you press "Start". The standings open when the contest ends: everyone starts at their own time, so other people's results are not visible beforehand.
- **Codeforces rules**: a problem's worth decreases as your clock runs (to about half by the end of the 120 minutes), every wrong attempt costs **−50 points**, but the worth never falls below 30% of the starting value. Time is counted from "Start". A mistake on the first test costs nothing.
- **Badge**: everyone who solves at least one problem gets the "Marathon #3" badge on their profile; the top three get a medal.
- The honesty rules apply: the code must be your own; do not send the problems or solutions to others; AI or someone else's solution is forbidden. Suspicious solutions are disqualified."""

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


# ---- D. Beginner (satr): eng uzun so'z ---------------------------------------------------
def longest_word_solve(inp):
    best = ""
    for w in inp.strip().split(" "):
        if len(w) > len(best):  # the first of equally long words stays
            best = w
    return _lines(best)


def longest_word_tests(rng):
    def sentence():
        return " ".join(_text(rng, rng.randint(1, rng.choice([3, 6, 10]))) for _ in range(rng.randint(1, 15)))[:200].strip()
    tests = ["men bugun maktabga bordim", "olma anor nok", "salom", "a", "a b c", "ab cd ef", "ali vali sami", "ali vali ola",
             "bir ikki uch to rt besh", "z" * 100 + " " + "y" * 100, "y" * 100 + " " + "z" * 100, "a " * 99 + "a",
             "kitob daftar qalam", "qalam daftar kitob", "dastur kod"]
    tests += [sentence() for _ in range(12)]
    return _uniq(tests)


# ---- E. Beginner (satr): maxfiy xat ------------------------------------------------------
def caesar_solve(inp):
    k, text = inp.split("\n")[:2]
    k = int(k)
    return _lines("".join(" " if ch == " " else chr((ord(ch) - 97 + k) % 26 + 97) for ch in text))


def caesar_tests(rng):
    def case(k, text):
        return f"{k}\n{text}"
    tests = [case(3, "salom dunyo"), case(25, "abc xyz"), case(1, "z"), case(1, "zzzz zzzz"), case(5, "a"),
             case(25, "a b c"), case(13, "abcdefghijklmnopqrstuvwxyz"), case(1, "abc"), case(2, "xyz"),
             case(12, "x" * 100), case(10, "ab " * 33 + "a"), case(7, "marafon uchun omad"), case(24, "yz"),
             case(3, "a b")]
    for _ in range(10):
        words = [_text(rng, rng.randint(1, 8)) for _ in range(rng.randint(1, 12))]
        tests.append(case(rng.randint(1, 25), " ".join(words)[:100].strip()))
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


# ---- G. Easy (satr): siqish --------------------------------------------------------------
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
             "a" * 1000, "ab" * 500, "a" * 999 + "b", "b" + "a" * 999, "abcdefghijklmnopqrstuvwxyz"]
    for _ in range(12):
        n = _size(rng, 20, 200, 1000)
        runs, total = [], 0
        while total < n:
            r = rng.choice([1, 1, 2, 3, 5, 9, 10, 11, 100])
            runs.append(rng.choice(LOWER[: rng.choice([2, 3, 26])]) * r)
            total += r
        tests.append("".join(runs)[: max(1, n)])
    return _uniq(tests)


# ---- H. Easy: stakan piramidasi ----------------------------------------------------------
def pyramid_solve(inp):
    n = int(inp)
    return _lines((isqrt(8 * n + 1) - 1) // 2)  # the largest k with k(k+1)/2 <= n


def pyramid_tests(rng):
    top = 10**9
    tests = ["10", "20", "1", "2", "3", "4", "5", "6", "7", "15", "21", "55", str(top), str(top - 1)]
    for k in (10, 1000, 31622, 44720, 44719, 44721):
        t = k * (k + 1) // 2
        tests += [str(t - 1), str(t), str(t + 1)]
    for _ in range(8):
        tests.append(str(rng.choice([rng.randint(1, 100), rng.randint(1, 10**4), rng.randint(1, top)])))
    return _uniq([t for t in tests if 1 <= int(t) <= top])


# ---- I. Easy (satr): eng ko'p harf -------------------------------------------------------
def common_solve(inp):
    s = inp.strip()
    count = {}
    for ch in s:
        count[ch] = count.get(ch, 0) + 1
    best = max(count.values())
    letter = min(ch for ch, c in count.items() if c == best)  # the alphabetically first of the most frequent
    return _lines(f"{letter} {best}")


def common_tests(rng):
    tests = ["salom", "banana", "abc", "a", "zzaa", "aazz", "abababc", "mississippi", "xyzxyz", "a" * 1000, "z" * 1000,
             "ab" * 500, "ba" * 500, "q" + "a" * 999, "programmalash", "kitob"]
    for _ in range(12):
        n = _size(rng, 8, 100, 1000)
        tests.append(_text(rng, n, rng.choice(["ab", "abc", "abcde", LOWER, "xyz"])))
    return _uniq(tests)


# ---- J. Medium (hal qiluvchi, satr): naqsh -----------------------------------------------
def pattern_solve(inp):
    s = inp.strip()
    n = len(s)
    for p in range(1, n + 1):
        if n % p == 0 and s[:p] * (n // p) == s:
            return _lines(p)


def pattern_tests(rng):
    tests = ["abcabcabc", "abcd", "aaaa", "abab", "abaaba", "ababab", "abcab", "a", "aa", "ab", "aba", "abcabc", "aabaab",
             "aabaa", "abcabcabcabc", "a" * 1000, "a" * 999 + "b", "ab" * 500, "ab" * 499 + "ba", "abc" * 333 + "a"]
    for _ in range(12):
        size = rng.choice([1, 2, 3, 4, 6, 10, 25, 100])
        block = _text(rng, size, rng.choice(["ab", "abc", LOWER]))
        s = block * rng.randint(1, max(1, 1000 // size))
        if rng.random() < 0.3:  # one letter off: the pattern breaks and the answer jumps up
            i = rng.randrange(len(s))
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
        "en": {
            "title": "Vowels",
            "statement": ("Sardor is writing a Telegram bot. The bot has to tell the user how many **vowels** the word "
                          "they sent contains. The vowels are `a`, `e`, `i`, `o`, `u`. Every other letter, `y` "
                          "included, is a consonant.\n\n"
                          "How many vowels does the word have?"),
            "input": "A single line with a word $s$ of lowercase Latin letters ($1 \\le |s| \\le 100$).",
            "output": "One integer: the number of vowels.",
        },
    },
    {
        "slug": "cam3-eng-arzoni-tekin", "title": "Eng arzoni tekin", "difficulty": "beginner", "points": 200,
        "tags": ["conditionals", "arithmetic"], "solve": free_solve, "tests": free_tests, "samples": 2,
        "statement": ("Do‘konda aksiya: **uchta mahsulot** birga olinsa, ulardan **eng arzoni tekin** beriladi. "
                      "Agar eng arzon narx bir nechta mahsulotda takrorlansa, baribir bittasi tekin bo‘ladi.\n\n"
                      "Mahsulotlarning narxlari $a$, $b$ va $c$ so‘m. Uchalasini birga olgan xaridor necha so‘m to‘laydi?"),
        "input": "Bitta qatorda uchta butun son: $a$, $b$ va $c$ ($1 \\le a, b, c \\le 10^6$).",
        "output": "Bitta butun son: xaridor to‘laydigan summa.",
        "en": {
            "title": "Cheapest for free",
            "statement": ("A shop runs a promotion: if you buy **three items** together, **the cheapest one is free**. "
                          "If the lowest price is shared by several items, only one of them is free all the same.\n\n"
                          "The items cost $a$, $b$ and $c$ soums. How much does a customer pay for all three?"),
            "input": "A single line with three integers: $a$, $b$ and $c$ ($1 \\le a, b, c \\le 10^6$).",
            "output": "One integer: the amount the customer pays.",
        },
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
        "en": {
            "title": "Battle of the letters",
            "statement": ("A password string consists of Latin letters and digits. Among the letters there are **uppercase** "
                          "(`A`–`Z`) and **lowercase** (`a`–`z`) ones; digits do not count.\n\n"
                          "Which kind is more frequent? Print `KATTA` if there are more uppercase letters, `KICHIK` if "
                          "there are more lowercase letters, and `TENG` if the counts are equal."),
            "input": "A single line with a string $s$ ($1 \\le |s| \\le 100$): only Latin letters and digits.",
            "output": "`KATTA`, `KICHIK` or `TENG`.",
        },
    },
    {
        "slug": "cam3-eng-uzun-soz", "title": "Eng uzun so‘z", "difficulty": "beginner", "points": 300,
        "tags": ["strings", "for-loop"], "solve": longest_word_solve, "tests": longest_word_tests, "samples": 2,
        "statement": ("Muharrir gapdagi **eng uzun so‘zni** topmoqchi. Gap kichik lotin harflaridan iborat so‘zlardan "
                      "tuzilgan, so‘zlar orasida bittadan probel bor.\n\n"
                      "Eng uzun so‘zni chiqaring. Agar eng uzun so‘z bir nechta bo‘lsa, **gapda birinchi kelganini** "
                      "chiqaring."),
        "input": ("Bitta qatorda gap ($1 \\le |s| \\le 200$): kichik lotin harflari va probellar, so‘zlar orasida bitta "
                  "probel, boshida va oxirida probel yo‘q."),
        "output": "Bitta qatorda eng uzun so‘z.",
        "en": {
            "title": "Longest word",
            "statement": ("An editor wants to find the **longest word** in a sentence. The sentence is made of words of "
                          "lowercase Latin letters, with a single space between words.\n\n"
                          "Print the longest word. If several words are the longest, print **the one that comes first** "
                          "in the sentence."),
            "input": ("A single line with the sentence ($1 \\le |s| \\le 200$): lowercase Latin letters and spaces, one "
                      "space between words, no space at the start or the end."),
            "output": "One line: the longest word.",
        },
    },
    {
        "slug": "cam3-maxfiy-xat", "title": "Maxfiy xat", "difficulty": "beginner", "points": 350,
        "tags": ["strings", "math"], "solve": caesar_solve, "tests": caesar_tests, "samples": 2,
        "statement": ("Ikki do‘st maxfiy xat yozishadi. Shifrlash oddiy: matndagi **har bir harf** alifboda $k$ qadam "
                      "**oldinga** suriladi (`a` → `b` → … → `z` → yana `a`). Probellar o‘zgarmaydi.\n\n"
                      "Masalan, $k = 3$ bo‘lsa, `xyz` so‘zi `abc` bo‘ladi.\n\n"
                      "Matnni shifrlab bering. Alifbo $26$ ta harfdan iborat."),
        "input": ("* Birinchi qatorda butun son $k$ ($1 \\le k \\le 25$) beriladi.\n"
                  "* Ikkinchi qatorda matn: kichik lotin harflari va probellar, so‘zlar orasida bitta probel, "
                  "boshida va oxirida probel yo‘q ($1 \\le |s| \\le 100$)."),
        "output": "Bitta qatorda shifrlangan matn.",
        "en": {
            "title": "Secret letter",
            "statement": ("Two friends write each other secret letters. The cipher is simple: **every letter** of the text is "
                          "moved **forward** by $k$ steps in the alphabet (`a` → `b` → … → `z` → `a` again). Spaces "
                          "stay as they are.\n\n"
                          "For example, with $k = 3$ the word `xyz` becomes `abc`.\n\n"
                          "Encrypt the text. The alphabet has $26$ letters."),
            "input": ("* The first line contains an integer $k$ ($1 \\le k \\le 25$).\n"
                      "* The second line contains the text: lowercase Latin letters and spaces, one space between "
                      "words, no space at the start or the end ($1 \\le |s| \\le 100$)."),
            "output": "One line: the encrypted text.",
        },
    },
    {
        "slug": "cam3-manfiy-balans", "title": "Manfiy balans", "difficulty": "easy", "points": 400,
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
        "en": {
            "title": "Negative balance",
            "statement": ("The balance on a card is $b$ soums. During the next $n$ days exactly one operation happens each "
                          "day: if $d_i > 0$ the account is topped up, if $d_i < 0$ money is withdrawn, if $d_i = 0$ "
                          "nothing changes. The operations are applied in the order of the days.\n\n"
                          "Find the number of the day on which the balance **first drops below zero** (becomes negative). "
                          "A balance of exactly zero is not negative. If it never becomes negative, print $-1$."),
            "input": ("* The first line contains $n$ and $b$ ($1 \\le n \\le 10^5$, $0 \\le b \\le 10^9$).\n"
                      "* The second line contains $n$ integers $d_1, \\ldots, d_n$ ($|d_i| \\le 10^9$) separated by "
                      "spaces."),
            "output": "One integer: the number of the day the balance first becomes negative, or $-1$.",
        },
    },
    {
        "slug": "cam3-siqish", "title": "Siqish", "difficulty": "easy", "points": 450,
        "tags": ["strings", "implementation"], "solve": runs_solve, "tests": runs_tests, "samples": 2,
        "statement": ("Faks apparati uzun satrlarni siqib yuboradi: bir xil harflarning har bir **ketma-ket guruhi** "
                      "harf va uning guruhdagi soni bilan almashtiriladi. Masalan, `aaabccdd` satri `a3b1c2d2` "
                      "bo‘ladi. Bitta turgan harf ham `1` bilan yoziladi.\n\n"
                      "Berilgan satrning siqilgan ko‘rinishini chiqaring."),
        "input": "Bitta qatorda kichik lotin harflaridan iborat satr $s$ ($1 \\le |s| \\le 1000$).",
        "output": "Bitta qatorda siqilgan satr.",
        "en": {
            "title": "Compression",
            "statement": ("A fax machine compresses long strings: every **consecutive group** of equal letters is replaced "
                          "by the letter and the size of the group. For example, `aaabccdd` becomes `a3b1c2d2`. A "
                          "single letter is written with `1` too.\n\n"
                          "Print the compressed form of the given string."),
            "input": "A single line with a string $s$ of lowercase Latin letters ($1 \\le |s| \\le 1000$).",
            "output": "One line: the compressed string.",
        },
    },
    {
        "slug": "cam3-stakan-piramidasi", "title": "Stakan piramidasi", "difficulty": "easy", "points": 500,
        "tags": ["math", "loops"], "solve": pyramid_solve, "tests": pyramid_tests, "samples": 2,
        "statement": ("Bayramda stakanlardan piramida quriladi: birinchi qatorda $1$ ta, ikkinchisida $2$ ta, "
                      "uchinchisida $3$ ta va hokazo — har keyingi qatorda avvalgisidan bittaga ko‘p stakan.\n\n"
                      "Qatorni **to‘liq** qilib qo‘yish kerak: yarim qator bo‘lmaydi. Omborda $n$ ta stakan bor. "
                      "Ulardan nechta to‘liq qator yasash mumkin?"),
        "input": "Bitta qatorda butun son $n$ ($1 \\le n \\le 10^9$).",
        "output": "Bitta butun son: to‘liq qatorlarning eng ko‘p soni.",
        "en": {
            "title": "Pyramid of glasses",
            "statement": ("For a celebration a pyramid is built from glasses: $1$ glass in the first row, $2$ in the second, "
                          "$3$ in the third, and so on: every next row has one glass more than the previous one.\n\n"
                          "A row has to be **complete**: there are no half rows. The storeroom has $n$ glasses. How many "
                          "complete rows can be built from them?"),
            "input": "A single line with an integer $n$ ($1 \\le n \\le 10^9$).",
            "output": "One integer: the largest number of complete rows.",
        },
    },
    {
        "slug": "cam3-eng-kop-harf", "title": "Eng ko‘p harf", "difficulty": "easy", "points": 600,
        "tags": ["strings", "hash-table"], "solve": common_solve, "tests": common_tests, "samples": 2,
        "statement": ("Kriptograf shifrlangan matnni tahlil qilmoqda: eng ko‘p uchraydigan harf shifrni ochishga "
                      "yordam beradi.\n\n"
                      "Satrda qaysi harf **eng ko‘p** uchraydi va necha marta? Bir nechta harf teng ko‘p uchrasa, "
                      "**alifbo bo‘yicha birinchisini** chiqaring."),
        "input": "Bitta qatorda kichik lotin harflaridan iborat satr $s$ ($1 \\le |s| \\le 1000$).",
        "output": "Bitta qatorda harf va uning soni, bo‘shliq bilan ajratilgan.",
        "en": {
            "title": "Most frequent letter",
            "statement": ("A cryptographer is analysing an encrypted text: the most frequent letter helps to break the "
                          "cipher.\n\n"
                          "Which letter occurs **most often** in the string, and how many times? If several letters are "
                          "equally frequent, print **the first one in alphabetical order**."),
            "input": "A single line with a string $s$ of lowercase Latin letters ($1 \\le |s| \\le 1000$).",
            "output": "One line: the letter and its count, separated by a space.",
        },
    },
    {
        "slug": "cam3-naqsh", "title": "Naqsh", "difficulty": "medium", "points": 800,
        "tags": ["strings", "implementation"], "solve": pattern_solve, "tests": pattern_tests, "samples": 2,
        "statement": ("Gilam to‘quvchi bir xil naqshni qayta-qayta to‘qiydi: bir bo‘lakni yonma-yon necha marta "
                      "takrorlaydi. Gilam $s$ satr bilan berilgan.\n\n"
                      "**Naqsh** — shunday bo‘lakki, uni **butun marta** ketma-ket yozsak, aynan $s$ hosil bo‘ladi "
                      "(bir marta yozish ham mumkin). Eng qisqa naqshning uzunligini toping.\n\n"
                      "Masalan, `abcabcabc` satrida naqsh `abc`, uzunligi $3$. `abcab` satrida takror yo‘q: naqsh "
                      "butun satr, javob $5$."),
        "input": "Bitta qatorda kichik lotin harflaridan iborat satr $s$ ($1 \\le |s| \\le 1000$).",
        "output": "Bitta butun son: eng qisqa naqshning uzunligi.",
        "en": {
            "title": "Pattern",
            "statement": ("A carpet weaver weaves the same pattern over and over: one piece repeated side by side several "
                          "times. The carpet is given as a string $s$.\n\n"
                          "A **pattern** is a piece that, written out a **whole number of times** in a row, gives exactly "
                          "$s$ (writing it once is allowed too). Find the length of the shortest pattern.\n\n"
                          "For example, in `abcabcabc` the pattern is `abc`, of length $3$. In `abcab` there is no "
                          "repetition: the pattern is the whole string, and the answer is $5$."),
            "input": "A single line with a string $s$ of lowercase Latin letters ($1 \\le |s| \\le 1000$).",
            "output": "One integer: the length of the shortest pattern.",
        },
    },
]


class Command(MarathonCommand):
    help = ("Creates CodeArena Marathon #3 (rated, 120-minute personal clock, seven of ten problems on strings) "
            "if needed and attaches its 10 problems (hidden) as A..J, with English drafts.")
    title, badge, description, problems, prefix = TITLE, BADGE, DESCRIPTION, PROBLEMS, "cam3-"

    def handle(self, *args, **opts):
        super().handle(*args, **opts)
        if not opts["dry_run"]:
            self._english(opts["contest"])

    def _draft(self, row, field, text):
        """An English draft (closed to readers until an admin confirms it); a text that has one already is left alone."""
        ct = ContentType.objects.get_for_model(row)
        if ContentTranslation.objects.filter(content_type=ct, object_id=row.pk, lang="en", field=field).exists():
            return 0
        service.save_draft(row, field, "en", text, by_ai=True)
        return 1

    def _english(self, contest_title):
        saved = 0
        contest = Contest.objects.get(title__iexact=contest_title)
        for field, text in (("title", TITLE), ("badge", BADGE), ("description_md", DESCRIPTION_EN)):
            saved += self._draft(contest, field, text)
        for spec in PROBLEMS:
            problem = Problem.objects.get(slug=spec["slug"])
            for field, key in (("title", "title"), ("statement_md", "statement"), ("input_md", "input"),
                               ("output_md", "output")):
                saved += self._draft(problem, field, spec["en"][key])
        self.stdout.write(f"English: {saved} ta qoralama saqlandi (Boshqaruv → Tarjimalar'da tasdiqlanadi).")
