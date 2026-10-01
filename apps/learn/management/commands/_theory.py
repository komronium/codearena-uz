"""Theory texts, one per topic, in path order. add_courses builds each course's theory from one
or more of them; staff edit the result on the course form."""

TEXTS = {
    # ---- dasturlash ---------------------------------------------------------------------------------
    "input-output": """\
Har bir masala **kirish ma’lumotlarini** o‘qiydi va **javobni chiqaradi**. Tekshiruvchi faqat chiqishni
solishtiradi, shuning uchun ortiqcha matn («Javob:», «Son kiriting») yozmang.

## Python

```python
a, b = map(int, input().split())   # bir qatorda ikki son
n = int(input())                   # alohida qatorda bitta son
nums = list(map(int, input().split()))
print(a + b)
print(*nums)                       # ro‘yxatni bo‘sh joy bilan
```

## C++

```cpp
long long a, b;
cin >> a >> b;
cout << a + b << "\\n";
```

## Diqqat

- Sonlar katta bo‘lsa, C++ da `long long` ishlating (10⁹ dan katta yig‘indi `int` ga sig‘maydi).
- Butun bo‘lish: Python’da `//`, qoldiq: `%`.
- Ko‘p qatorli kirishda C++ da `ios::sync_with_stdio(false); cin.tie(nullptr);` tezlashtiradi.
""",
    "arithmetic": """\
Ko‘p masala — formula: sonlarni o‘qish, hisoblash va chiqarish. Sikl kerak bo‘lmasligi ham mumkin.

| Amal | Python | Misol |
|---|---|---|
| Butun bo‘lish | `a // b` | `17 // 5` → `3` |
| Qoldiq | `a % b` | `17 % 5` → `2` |
| Daraja | `a ** b` | `2 ** 10` → `1024` |
| Haqiqiy bo‘lish | `a / b` | `7 / 2` → `3.5` |

## Foydali formulalar

- 1 dan n gacha yig‘indi: `n * (n + 1) // 2`.
- Yuqoriga yaxlitlab bo‘lish (nechta quti, nechta parta): `(a + b - 1) // b`.
- Juft yoki toq: `n % 2 == 0`.
- Oxirgi raqam: `n % 10`; oxirgi raqamsiz son: `n // 10`.
- Soniyadan soat, daqiqa, soniya: `t // 3600`, `t % 3600 // 60`, `t % 60`.

## Kasr sonlar

```python
avg = total / n
print(f"{avg:.2f}")      # verguldan keyin 2 ta raqam
```

- Iloji bo‘lsa butun sonlarda hisoblang: `0.1 + 0.2` aniq `0.3` emas.
- Foiz: `s * p // 100` — butun natija; `s * p / 100` — kasr.
- `round(2.5)` Python’da `2` beradi (juftga yaxlitlash). Masala boshqacha yaxlitlashni so‘rasa,
  formulani o‘zingiz yozing.
""",
    "conditionals": """\
Shart dastur qaysi yo‘ldan borishini hal qiladi.

```python
if x > 0:
    print("musbat")
elif x < 0:
    print("manfiy")
else:
    print("nol")
```

## Maslahatlar

- Avval **chegaralarni** yozib chiqing: `<` mi yoki `<=` mi? Ko‘p xato aynan shu yerda.
- Murakkab shartni bo‘lib yozing: `kabisa = (y % 4 == 0 and y % 100 != 0) or y % 400 == 0`.
- Uchta sonni solishtirishda barcha holatlarni (teng sonlar ham!) sinab ko‘ring.
""",
    "for-loop": """\
`for` sikli bir ishni **oldindan ma’lum** marta takrorlaydi: n ta sonni o‘qish, 1 dan n gacha yurish,
satrning har bir belgisi.

```python
for i in range(n):            # 0, 1, ..., n-1
    ...
for i in range(1, n + 1):     # 1, 2, ..., n
    ...
for i in range(n, 0, -1):     # n, n-1, ..., 1
    ...
for ch in s:                  # satrning har bir belgisi
    ...
```

## Andozalar

```python
n = int(input())
total, count, best = 0, 0, None
for _ in range(n):
    x = int(input())
    total += x                      # yig‘indi
    if x < 0:
        count += 1                  # shartga moslarini sanash
    if best is None or x > best:
        best = x                    # eng kattasi
```

- Yig‘indi `0` dan, ko‘paytma (masalan, faktorial) `1` dan boshlanadi.
- Eng katta yoki eng kichikni `0` dan boshlamang: hamma son manfiy bo‘lsa, javob noto‘g‘ri chiqadi.
- O‘rtacha qiymat: yig‘indini sikldan keyin bir marta bo‘ling.

## Diqqat

- `range(a, b)` ga `b` kirmaydi: 1 dan n gacha — `range(1, n + 1)`.
- Indeks ham, qiymat ham kerak bo‘lsa: `for i, x in enumerate(a):`.
""",
    "while-loop": """\
`while` sikli **shart bajarilguncha** takrorlanadi. Necha marta aylanishi oldindan ma’lum bo‘lmasa,
shuni tanlang: «nechta raqam bor», «necha yilda yetadi», «0 kelguncha».

```python
count = 0
while n > 0:          # raqamlarni ajratish
    d = n % 10        # oxirgi raqam
    n //= 10          # uni olib tashlaymiz
    count += 1
```

## Andozalar

Maqsadga yetguncha:

```python
years = 0
while s < t:
    s += s * p // 100
    years += 1
```

Kirish tugaguncha (masalan, 0 kelguncha):

```python
x = int(input())
while x != 0:
    ...
    x = int(input())
```

## Diqqat

- Sikl ichida shartdagi qiymat o‘zgarishi kerak. Aks holda sikl to‘xtamaydi va yechim vaqt chegarasidan oshadi.
- `n = 0` ni alohida tekshiring: `while n > 0` bir marta ham aylanmaydi, lekin 0 da bitta raqam bor.
- `break` siklni darhol to‘xtatadi, `continue` keyingi aylanishga o‘tadi.
""",
    "nested-loops": """\
Sikl ichidagi sikl: tashqi siklning **har bir** qadamida ichki sikl boshidan oxirigacha aylanadi.
Jadvallar, juftliklar va naqshlar shunday chiziladi.

```python
for i in range(1, n + 1):          # qatorlar
    for j in range(1, i + 1):      # shu qatordagi ustunlar
        print("*", end="")
    print()                        # qator oxiri
```

## Andozalar

- **Barcha juftliklar** (har juft bir marta): tashqi `for i in range(n)`, ichki `for j in range(i + 1, n)`.
- **Jadval** (ko‘paytirish jadvali, matritsa): tashqi sikl — qatorlar, ichki — ustunlar.
- **Ichida `while`**: masalan, raqamli ildiz — son bir xonali bo‘lguncha raqamlarini qo‘shib boring.

## Murakkablik

Ikki ichma-ich sikl taxminan `n × n` marta aylanadi. n = 10⁴ bo‘lsa, bu 10⁸ amal — vaqt chegarasiga
yaqin. n bundan katta bo‘lsa, ichki siklni formula, prefiks yig‘indi yoki lug‘at bilan almashtiring.

## Diqqat

- Ichki va tashqi sikl o‘zgaruvchilari har xil nomlansin (`i` va `j`).
- `break` faqat **ichki** siklni to‘xtatadi. Ikkalasidan chiqish uchun bayroq o‘zgaruvchi ishlating
  yoki kodni funksiyaga olib, `return` qiling.
""",
    "number-basics": """\
Sonning xossalari: bo‘linish, bo‘luvchilar, tub sonlar, EKUB va EKUK, sanoq sistemalari.

## Bo‘luvchilar

`n % i == 0` bo‘lsa, `i` — `n` ning bo‘luvchisi. Bo‘luvchilarni √n gacha izlash yetarli: `i` bo‘luvchi
bo‘lsa, `n // i` ham bo‘luvchi.

```python
count = 0
i = 1
while i * i <= n:
    if n % i == 0:
        count += 1 if i * i == n else 2
    i += 1
```

## Tub sonlar

Tub son 1 dan katta va faqat 1 ga va o‘ziga bo‘linadi: 2, 3, 5, 7, 11, …

```python
def is_prime(n):
    if n < 2:
        return False
    i = 2
    while i * i <= n:
        if n % i == 0:
            return False
        i += 1
    return True
```

Tub ko‘paytuvchilarga ajratish ham shunday ishlaydi: `n` ni `i` ga bo‘linguncha bo‘lib boring. Oxirida
`n > 1` qolsa, u ham tub ko‘paytuvchi.

## EKUB va EKUK

```python
from math import gcd
g = gcd(a, b)          # Evklid: gcd(a, b) = gcd(b, a % b)
lcm = a // g * b
```

## Sanoq sistemalari

```python
bin(13)                # '0b1101'
int("1101", 2)         # 13
digits = []
while n > 0:           # istalgan asosga: qoldiqlar teskari tartibda chiqadi
    digits.append(n % base)
    n //= base
```

Butun kvadrat ildiz uchun `math.isqrt(x)` ishlating. `int(x ** 0.5)` katta sonlarda xato beradi.
""",
    "arrays": """\
Massiv (Python’da ro‘yxat) — bir xil turdagi qiymatlar ketma-ketligi, indeks 0 dan boshlanadi.

```python
a = list(map(int, input().split()))
print(max(a), min(a), sum(a))
for i, x in enumerate(a):
    ...
```

## Chiziqli fikrlash

n ≤ 10⁵ bo‘lsa, ikki ichma-ich sikl (n² = 10¹⁰ amal) vaqtga sig‘maydi. Ro‘yxatni **bir marta** aylanib,
kerakli ma’lumotni yo‘l-yo‘lakay saqlang: joriy yig‘indi, hozirgacha eng kichik qiymat va hokazo.

Masalan, aksiyani eng yaxshi sotish: har kun uchun «shu kungacha eng arzon narx»ni eslab boring.
""",
    "strings": """\
Satr — belgilar ketma-ketligi. Python’da satr **o‘zgarmas**: yangi satr yasaladi.

```python
s = input().strip()
words = s.split()          # so‘zlarga bo‘lish
t = s[::-1]                # teskari
s.lower(), s.upper()
"".join(parts)             # ro‘yxatdan satr — += dan ancha tez
```

## Maslahatlar

- Belgining kodi: `ord("a")`, aksi: `chr(97)`.
- Sikl ichida `s += c` uzun satrda sekin; belgilarni ro‘yxatga yig‘ib, oxirida `join` qiling.
- Bo‘sh joylar va qator oxiri (`strip()`) ni unutmang.
""",
    "matrices": """\
Matritsa — ro‘yxatlar ro‘yxati: `a[i][j]` — `i`-qator, `j`-ustun.

```python
n, m = map(int, input().split())
a = [list(map(int, input().split())) for _ in range(n)]
grid = [input() for _ in range(n)]     # belgilar jadvali: grid[i][j] — bitta belgi
```

## Andozalar

```python
row_sums = [sum(row) for row in a]
col_sums = [sum(a[i][j] for i in range(n)) for j in range(m)]
diag = sum(a[i][i] for i in range(n))      # bosh diagonal (n × n)
t = [list(col) for col in zip(*a)]         # transponirlash
```

Qo‘shni kataklar (labirint, «mina» o‘yini):

```python
for di, dj in ((-1, 0), (1, 0), (0, -1), (0, 1)):
    ni, nj = i + di, j + dj
    if 0 <= ni < n and 0 <= nj < m:
        ...
```

## Diqqat

`[[0] * m] * n` — bitta qatorning n ta nusxasi emas, n ta havolasi: bittasini o‘zgartirsangiz,
hammasi o‘zgaradi. To‘g‘risi: `[[0] * m for _ in range(n)]`.
""",
    "hash-table": """\
Hash-jadval «bu element bormi?» savoliga o‘rtacha **O(1)** vaqtda javob beradi.

```python
seen = set()
for x in a:
    if x in seen:
        print("YES"); break
    seen.add(x)

from collections import Counter
cnt = Counter(s)           # har belgi necha marta
```

## Qachon ishlatiladi

- Takrorlarni topish, juftlik izlash (`target - x` oldin uchraganmi?).
- Sanash: anagramma, ko‘pchilik ovozi, harflar yetarlimi.

`list` da `x in a` — O(n), `set` da — O(1). Katta kirishda farq hal qiluvchi.
""",
    "tuples-sets": """\
**Kortej** (`tuple`) — o‘zgarmas ro‘yxat. U `set` elementi va `dict` kaliti bo‘la oladi, ro‘yxat esa bo‘la olmaydi.

```python
visited = {(0, 0)}
dist = {(0, 0): 0}
a, b = b, a                 # o‘rin almashtirish ham kortej orqali ishlaydi
```

**To‘plam** (`set`) — takrorsiz elementlar.

```python
a, b = {1, 2, 3}, {2, 3, 4}
a | b, a & b, a - b         # birlashma, kesishma, ayirma
len(set(nums))              # nechta turli son
sorted(set(nums))           # turli sonlar o‘sish tartibida
```

`set` tartibni saqlamaydi: chiqarishdan oldin saralang.
""",
    "functions": """\
Funksiya — nomlangan kod bo‘lagi: bir marta yoziladi, ko‘p marta chaqiriladi. Masalani kichik va
alohida tekshiriladigan qismlarga bo‘lishning eng yaxshi yo‘li.

```python
def area(w, h):
    return w * h

def min_max(a):
    return min(a), max(a)          # bir nechta qiymat — kortej

lo, hi = min_max([3, 1, 4])
print(area(3, 4))                  # 12
```

## Qoidalar

- `return` funksiyadan darhol chiqadi. `return` bo‘lmasa, funksiya `None` qaytaradi.
- Funksiya ichida yaratilgan o‘zgaruvchi tashqarida ko‘rinmaydi. Kerakli qiymatni parametr orqali bering.
- Ro‘yxatni funksiyaga bersangiz, funksiya **o‘sha** ro‘yxatni o‘zgartiradi, nusxasini emas.
- `def f(a=[])` deb yozmang: bu ro‘yxat barcha chaqiruvlarda bitta bo‘lib qoladi. `a=None` qo‘yib, ichida yarating.
""",
    "recursion": """\
**Rekursiya** — funksiya o‘zini kichikroq kirish bilan chaqiradi. Har rekursiyada ikki qism bo‘ladi:
**to‘xtash sharti** (baza) va **kichraytirish qadami**.

```python
def factorial(n):
    if n == 0:              # baza
        return 1
    return n * factorial(n - 1)

def digits_sum(n):
    return n if n < 10 else n % 10 + digits_sum(n // 10)
```

## Qanday o‘ylash kerak

«Kichikroq masala yechilgan deb faraz qilaman. Undan kattasini qanday yasayman?» — shu savolga javob
rekursiv qadam bo‘ladi.

## Diqqat

- Python’da chuqurlik chegarasi ~1000: chuqur rekursiyada `sys.setrecursionlimit(10**6)` yoki siklga o‘tkazing.
- Bir xil argument qayta-qayta hisoblansa — eslab qoling (`functools.lru_cache`), bu allaqachon DP.

```python
from functools import lru_cache

@lru_cache(maxsize=None)
def fib(n):
    return n if n < 2 else fib(n - 1) + fib(n - 2)
```
""",
    "complexity": """\
Algoritm qancha **vaqt** va **xotira** olishini kirish hajmi `n` orqali baholaymiz. Bu O-belgisi
(«katta O») bilan yoziladi va kodni yozishdan **oldin** to‘g‘ri yo‘lni tanlashga yordam beradi.

## Taxminiy jadval

Server sekundiga taxminan **10⁸** oddiy amal bajaradi. Vaqt chegarasi 1 sekund bo‘lsa:

| n gacha | Mos murakkablik | Misol |
|---|---|---|
| 10–20 | O(2ⁿ), O(n!) | barcha qism to‘plamlar, perestanovkalar |
| 500 | O(n³) | uch ichma-ich sikl |
| 5 000 | O(n²) | ikki ichma-ich sikl |
| 10⁵–10⁶ | O(n log n) | saralash, ikkilik qidiruv |
| 10⁷–10⁸ | O(n) | bitta o‘tish |
| 10¹⁸ | O(log n), O(1) | formula, ikkilik daraja |

## Qanday sanash

```python
for i in range(n):          # n marta
    for j in range(n):      # har biriga n marta  ->  O(n²)
        ...
nums.sort()                 # O(n log n)
x in my_set                 # o‘rtacha O(1)
x in my_list                # O(n) — katta siklda ehtiyot bo‘ling!
```

## Diqqat

- Sikl ichida `list.index`, `in list`, satr qo‘shish (`s += ...`) — yashirin O(n).
- Python C++ dan ~10–50 marta sekin: chegaraga yaqin bo‘lsa, tezroq g‘oya izlang.
""",
    "implementation": """\
Ba’zi masalalarda maxsus algoritm kerak emas — shartni **aniq va ehtiyotkorlik bilan** bajarish kerak.
Bunday masalalarda xato odatda chegaraviy holatlarda bo‘ladi.

## Ish tartibi

1. Shartni oxirigacha o‘qing, misollarni qo‘lda hisoblab ko‘ring.
2. Barcha holatlarni ro‘yxat qiling: 0, 1, eng katta qiymat, teng qiymatlar, bo‘sh satr.
3. Kodni kichik funksiyalarga bo‘ling — har birini alohida tekshirish oson.

```python
def price(minutes):
    if minutes <= 0:
        return 0
    hours = (minutes + 59) // 60      # yuqoriga yaxlitlash, float’siz
    return min(hours * 3000, 20000)   # kunlik chegara
```

## Ko‘p uchraydigan xatolar

- `<` va `<=` chalkashligi.
- Yaxlitlash: yuqoriga yaxlitlash uchun `(a + b - 1) // b`.
- Chiqish formati: bo‘sh joy, qator oxiri, katta-kichik harf.
""",
    "sorting": """\
Saralash ko‘p masalani soddalashtiradi: tenglar yonma-yon, eng kichiklar boshida.

```python
a.sort()                           # o‘sish tartibida
a.sort(reverse=True)
people.sort(key=lambda p: (-p.score, p.name))
```

Python’ning `sort` — O(n log n) va **barqaror** (teng elementlar tartibi saqlanadi).

Saralangandan keyin: ikki ko‘rsatkich, ikkilik qidiruv, qo‘shni elementlarni solishtirish.
""",
    "divide-and-conquer": """\
**Bo‘l va hukmronlik qil**: masalani ikki (yoki bir nechta) teng qismga bo‘lamiz, har birini rekursiv
yechamiz, so‘ng natijalarni birlashtiramiz.

## Birlashtirib saralash (merge sort) — O(n log n)

```python
def merge_sort(a):
    if len(a) <= 1:
        return a
    mid = len(a) // 2
    left, right = merge_sort(a[:mid]), merge_sort(a[mid:])
    out, i, j = [], 0, 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            out.append(left[i]); i += 1
        else:
            out.append(right[j]); j += 1
    return out + left[i:] + right[j:]
```

## Boshqa misollar

- Ikkilik daraja: `aⁿ = (a^(n/2))²` — O(log n).
- Inversiyalar sonini sanash (merge sort ichida).
- Ikkilik qidiruv ham shu g‘oyaning bir turi.
""",
    "binary-search": """\
Ikkilik qidiruv saralangan ro‘yxatda qidiruv oralig‘ini har qadamda **ikki baravar** qisqartiradi: log₂(10⁹) ≈ 30 qadam.

```python
from bisect import bisect_left, bisect_right
k = bisect_right(a, x)     # x dan katta bo‘lmaganlar soni

lo, hi = 0, 10**9          # javob bo‘yicha qidiruv
while lo < hi:
    mid = (lo + hi) // 2
    if ok(mid): hi = mid
    else: lo = mid + 1
```

## Javob bo‘yicha qidiruv

Agar «X yetarlimi?» savoli monoton bo‘lsa (X ishlasa, kattaroq ham ishlaydi), eng kichik X ni ikkilik
qidiruv bilan toping. Chegaralar va `mid` ni yaxlitlashga ehtiyot bo‘ling — cheksiz sikl shu yerdan chiqadi.
""",
    "prefix-sums": """\
Prefiks yig‘indi: `p[i] = a[0] + ... + a[i-1]`. Shunda `[l, r]` oraliq yig‘indisi bir amalda:

```python
p = [0]
for x in a:
    p.append(p[-1] + x)
# a[l..r] (0 dan, ikkala chegara kiradi):
s = p[r + 1] - p[l]
```

Q ta so‘rovda har birini sikl bilan hisoblash O(n·q), prefiks bilan — O(n + q).

Kengaytmalar: ikki o‘lchovli prefiks (to‘g‘ri to‘rtburchak yig‘indisi), farq massivi (oraliqqa qo‘shish).
""",
    "two-pointers": """\
Ikki ko‘rsatkich — ro‘yxat bo‘ylab ikki indeksni bir vaqtda yuritish. Ko‘pincha O(n²) ni O(n) ga tushiradi.

```python
i, j = 0, len(a) - 1
while i < j:
    if a[i] + a[j] == target: ...
    elif a[i] + a[j] < target: i += 1
    else: j -= 1
```

## Andozalar

- **Qarama-qarshi uchlar**: saralangan ro‘yxatda juftlik izlash, kvadratlarni tartiblash.
- **Bir yo‘nalishda (siljuvchi oyna)**: `j` oldinga yuradi, shart buzilsa `i` ni suramiz.
- **Yozish ko‘rsatkichi**: nollarni oxiriga surish, takrorlarni o‘chirish — joyida.
""",
    "sliding-window": """\
**Siljuvchi oyna** — massivda ketma-ket oraliqni ikki ko‘rsatkich (`left`, `right`) bilan ushlab,
uni o‘ngga suramiz. Har element oynaga bir marta kiradi va bir marta chiqadi — jami O(n).

## Belgilangan uzunlikdagi oyna

```python
window = sum(a[:k])
best = window
for i in range(k, len(a)):
    window += a[i] - a[i - k]     # yangisi kiradi, eskisi chiqadi
    best = max(best, window)
```

## O‘zgaruvchan oyna: shartga mos eng uzun oraliq

```python
left = total = best = 0
for right, x in enumerate(a):
    total += x
    while total > limit:          # shart buzildi — chapdan qisqartiramiz
        total -= a[left]
        left += 1
    best = max(best, right - left + 1)
```

Takrorlanmas belgili eng uzun qism satr kabi masalalarda oyna ichidagi belgilar `dict`/`set` da saqlanadi.
""",
    "greedy": """\
Ochko‘z (greedy) algoritm har qadamda **hozir eng yaxshi ko‘ringan** tanlovni qiladi va ortga qaytmaydi.

Ishlashi uchun tanlov «xavfsiz» bo‘lishi kerak: hech qachon yomonroq natijaga olib kelmasligi.
Ko‘pincha avval saralash kerak bo‘ladi (eng erta tugaydigan ish, eng arzon narx).

Ishonchingiz komil bo‘lmasa, kichik misollarda to‘liq tanlash (brute force) bilan solishtirib ko‘ring.
""",
    "bit-manipulation": """\
Sonlar ikkilik ko‘rinishda saqlanadi; bit amallari juda tez.

- `a & b` (VA), `a | b` (YOKI), `a ^ b` (XOR), `x << k` = x·2ᵏ, `x >> k` = x // 2ᵏ.
- n ikkining darajasimi: `n > 0 and n & (n - 1) == 0`.
- Birlar soni: `bin(n).count("1")`.

**XOR** xossasi: `x ^ x = 0`, `x ^ 0 = x`. Shuning uchun hamma son juft marta uchragan ro‘yxatda
juftsiz sonni barcha elementlarni XOR qilib topish mumkin.
""",
    "brute-force": """\
**To‘liq perebor** — barcha variantlarni tekshirib, mosini tanlash. Eng oddiy va eng ishonchli yechim:
agar `n` kichik bo‘lsa (masalan, 10–20 gacha), ko‘pincha shuning o‘zi yetadi.

```python
from itertools import combinations, permutations, product

best = max(sum(c) for c in combinations(nums, 3) if sum(c) <= limit)   # 3 tadan tanlash
for p in permutations(range(n)): ...                                    # barcha tartiblar
for bits in product([0, 1], repeat=n): ...                              # barcha qism to‘plamlar
```

## Qachon ishlatiladi

1. Chegaralar kichik — to‘g‘ridan-to‘g‘ri yechim.
2. Tez yechimni **tekshirish** uchun: kichik testlarda ikkalasining javobini solishtiring (stress-test).
3. Naqsh izlash: kichik `n` lar uchun javoblarni chiqarib, formulani ko‘rish.

Avval variantlar sonini hisoblang: `2²⁰ ≈ 10⁶` — bemalol, `2⁴⁰` — yo‘q.
""",
    "backtracking": """\
**Backtracking (orqaga qaytish)** — javobni qadamma-qadam quramiz; yo‘l noto‘g‘ri bo‘lib chiqsa,
oxirgi tanlovni bekor qilib, boshqasini sinaymiz. Bu aqlli to‘liq perebor.

```python
def subsets(nums):
    result, cur = [], []

    def go(i):
        if i == len(nums):
            result.append(cur[:])
            return
        go(i + 1)              # nums[i] ni olmaymiz
        cur.append(nums[i])    # olamiz
        go(i + 1)
        cur.pop()              # bekor qilamiz — orqaga qaytish

    go(0)
    return result
```

## Klassik masalalar

- Barcha qism to‘plamlar, perestanovkalar, kombinatsiyalar.
- N ta farzin (queen), sudoku, labirintdan barcha yo‘llar.

## Kesish (pruning)

Javob bo‘lishi mumkin bo‘lmagan shoxni erta to‘xtating: masalan, yig‘indi allaqachon chegaradan
oshgan bo‘lsa, chuqurroq kirmang. Bu vaqtni ko‘p marta qisqartiradi.
""",
    "stack": """\
**Stek** — «oxirgi kirgan birinchi chiqadi» (LIFO). Python’da oddiy ro‘yxat: `append` — qo‘shish,
`pop` — olish, `st[-1]` — tepadagi element. Hammasi O(1).

## Qavslar balansi

```python
pairs = {")": "(", "]": "[", "}": "{"}
st = []
for ch in s:
    if ch in "([{":
        st.append(ch)
    elif not st or st.pop() != pairs[ch]:
        print("NO"); break
else:
    print("YES" if not st else "NO")
```

## Monoton stek

Har element uchun «o‘ngdagi birinchi katta element»ni O(n) da topish:

```python
ans, st = [-1] * n, []          # st — indekslar, qiymatlari kamayuvchi
for i, x in enumerate(a):
    while st and a[st[-1]] < x:
        ans[st.pop()] = x
    st.append(i)
```

Qo‘llanishi: ifodalarni hisoblash, «undo», DFS ni rekursiyasiz yozish.
""",
    "queue": """\
**Navbat** — «birinchi kirgan birinchi chiqadi» (FIFO). Python’da `collections.deque` ishlating:
ro‘yxatdan `pop(0)` O(n), `deque.popleft()` esa O(1).

```python
from collections import deque

q = deque()
q.append(5)        # oxiriga
q.appendleft(1)    # boshiga
x = q.popleft()    # boshidan olish
```

## Qayerda kerak

- **BFS** (kenglik bo‘yicha qidiruv) — navbatsiz bo‘lmaydi.
- Jarayonlarni kelish tartibida qayta ishlash (simulyatsiya).
- **Oyna maksimumi**: deque’da indekslarni kamayish tartibida saqlab, har oyna maksimumini O(1) da olish.

```python
dq, out = deque(), []
for i, x in enumerate(a):
    while dq and a[dq[-1]] <= x:
        dq.pop()
    dq.append(i)
    if dq[0] <= i - k:
        dq.popleft()
    if i >= k - 1:
        out.append(a[dq[0]])
```
""",
    "linked-list": """\
**Bog‘langan ro‘yxat** — har tugun qiymat va keyingi tugunga havola saqlaydi. Boshiga qo‘shish O(1),
lekin `i`-elementga borish O(n).

```python
class Node:
    def __init__(self, val, nxt=None):
        self.val, self.next = val, nxt

def reverse(head):
    prev = None
    while head:
        head.next, prev, head = prev, head, head.next
    return prev
```

## Tez-tez uchraydigan usullar

- **Sekin va tez ko‘rsatkich**: o‘rtani topish, sikl borligini aniqlash (Floyd).
- **Soxta bosh tugun** (`dummy`) — boshini o‘chirishda alohida holatlarni yo‘qotadi.

Musobaqa masalalarida bog‘langan ro‘yxat kamdan-kam kerak bo‘ladi — odatda massiv yoki `deque` yetadi.
Lekin intervyularda klassik mavzu.
""",
    "heap": """\
**Uyum (heap, ustuvor navbat)** — eng kichik elementni O(1) da ko‘rsatadi, qo‘shish va olish O(log n).
Python’da `heapq` (min-heap).

```python
import heapq

h = []
heapq.heappush(h, 7)
heapq.heappush(h, 2)
smallest = heapq.heappop(h)      # 2
heapq.heappush(h, -x)            # max-heap kerak bo‘lsa — manfiy qiymat saqlang
top3 = heapq.nlargest(3, nums)
```

## Klassik qo‘llanishlar

- **Dijkstra** algoritmi (eng qisqa yo‘l).
- Har qadamda eng kichik ikkitasini birlashtirish (Huffman, «arqonlarni ulash»).
- Oqimdagi `k` ta eng katta element: hajmi `k` bo‘lgan min-heap saqlang.
- Vazifalarni ustuvorlik bo‘yicha bajarish (simulyatsiya).

C++: `priority_queue<int>` — max-heap, `priority_queue<int, vector<int>, greater<int>>` — min-heap.
""",
    "number-theory": """\
## Bo‘luvchilar — O(√n)

```python
divs = []
i = 1
while i * i <= n:
    if n % i == 0:
        divs.append(i)
        if i != n // i:
            divs.append(n // i)
    i += 1
```

## Tub sonlar — Eratosfen g‘alviri, O(n log log n)

```python
is_prime = [True] * (n + 1)
is_prime[0] = is_prime[1] = False
for i in range(2, int(n ** 0.5) + 1):
    if is_prime[i]:
        is_prime[i * i::i] = [False] * len(range(i * i, n + 1, i))
```

## EKUB va EKUK

```python
from math import gcd
lcm = a // gcd(a, b) * b         # avval bo‘lib, keyin ko‘paytiring — toshib ketmaydi
```

## Modul bo‘yicha arifmetika

Javob «10⁹ + 7 ga bo‘lgandagi qoldiq» bo‘lsa, har qo‘shish va ko‘paytirishdan keyin `% MOD` qiling.
Daraja: `pow(a, n, MOD)` — O(log n). Bo‘lish o‘rniga teskari element: `pow(b, MOD - 2, MOD)` (MOD tub bo‘lsa).
""",
    "combinatorics": """\
Nechta usulda tanlash yoki joylashtirish mumkinligini sanash.

| Nima | Formula | Python |
|---|---|---|
| tartiblash | n! | `math.factorial(n)` |
| k tasini tartib bilan | n! / (n−k)! | `math.perm(n, k)` |
| k tasini tartibsiz | n! / (k!(n−k)!) | `math.comb(n, k)` |

## Paskal uchburchagi

`C(n, k) = C(n−1, k−1) + C(n−1, k)` — modul bo‘yicha ko‘p `C` kerak bo‘lsa, jadvalni shunday to‘ldiring.

## Juftliklarni sanash

Bir xil elementlardan juftliklar: har qiymat `c` marta uchrasa, `c·(c−1)/2` juftlik.

```python
from collections import Counter
pairs = sum(c * (c - 1) // 2 for c in Counter(nums).values())
```

## Katta n va modul

Faktoriallarni va ularning teskarisini oldindan hisoblang: `fact[i]`, `inv_fact[i]`, so‘ng
`C(n, k) = fact[n] · inv_fact[k] · inv_fact[n−k] mod p`.
""",
    "dynamic-programming": """\
Dinamik dasturlash (DP): katta masalaning javobini **kichik masalalar javobidan** yig‘ish va har birini
bir marta hisoblash.

1. **Holat**: `dp[i]` nimani bildiradi? (masalan, i summani to‘lash uchun eng kam tanga)
2. **O‘tish**: `dp[i] = min(dp[i - c] + 1 for c in coins)`
3. **Boshlang‘ich**: `dp[0] = 0`
4. **Javob**: `dp[n]`

```python
INF = float("inf")
dp = [0] + [INF] * n
for i in range(1, n + 1):
    for c in coins:
        if c <= i:
            dp[i] = min(dp[i], dp[i - c] + 1)
```

Zinapoya masalasi — eng oddiy DP: `dp[i] = dp[i-1] + dp[i-2]`.
""",
    "graphs": """\
Graf — uchlar va ularni bog‘lovchi qirralar (shaharlar va yo‘llar, labirint kataklari).

```python
g = [[] for _ in range(n + 1)]
for _ in range(m):
    u, v = map(int, input().split())
    g[u].append(v); g[v].append(u)
```

## Asosiy algoritmlar

- **BFS** (`collections.deque`): og‘irliksiz grafda eng qisqa yo‘l, labirint.
- **DFS**: bog‘langanlik, komponentlar.
- **Dijkstra** (`heapq`): musbat og‘irlikli eng qisqa yo‘l, O(m log n).
- **Kruskal + DSU**: minimal skelet daraxt.

Chuqur rekursiyada Python to‘xtaydi — DFS ni stek bilan yozing yoki BFS ishlating.
""",
    "bfs": """\
**BFS (kenglik bo‘yicha qidiruv)** — boshlang‘ich uchdan qatlam-qatlam yuradi: avval masofasi 1
bo‘lganlar, keyin 2… Shuning uchun **qirralar vazni bir xil** bo‘lsa, eng qisqa yo‘lni beradi. O(V + E).

```python
from collections import deque

dist = [-1] * n
dist[s] = 0
q = deque([s])
while q:
    v = q.popleft()
    for to in g[v]:
        if dist[to] == -1:
            dist[to] = dist[v] + 1
            q.append(to)
```

## To‘rda (labirint)

```python
for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
    nr, nc = r + dr, c + dc
    if 0 <= nr < R and 0 <= nc < C and grid[nr][nc] != "#" and dist[nr][nc] == -1:
        ...
```

## Diqqat

- Uchni navbatga **qo‘shganda** belgilang, olganda emas — aks holda bir uch ko‘p marta kiradi.
- Bir nechta boshlang‘ich nuqta bo‘lsa (masalan, bir nechta olov manbai), hammasini birdan navbatga qo‘ying.
""",
    "dfs": """\
**DFS (chuqurlik bo‘yicha qidiruv)** — bir yo‘ldan oxirigacha boradi, keyin orqaga qaytadi. O(V + E).

```python
import sys
sys.setrecursionlimit(10**6)

seen = [False] * n
def dfs(v):
    seen[v] = True
    for to in g[v]:
        if not seen[to]:
            dfs(to)

components = 0
for v in range(n):
    if not seen[v]:
        components += 1
        dfs(v)
```

## Nimalarni topadi

- **Bog‘lanish komponentalari** soni (yuqoridagi kod).
- **Sikl** borligi: yo‘naltirilgan grafda «hozir stekda turgan» uchga qaytish — sikl.
- **Topologik tartib**: DFS tugagan tartibni teskari aylantiring.
- To‘rdagi «orollar» soni.

Katta grafda rekursiya chuqurligi muammo bo‘lsa, DFS ni oddiy stek bilan yozing.
""",
    "topological-sort": """\
Yo‘naltirilgan, sikli yo‘q grafda uchlarni shunday tartiblaymizki, har bir `u → v` qirrada `u` oldin
keladi. Masalan, fanlar ketma-ketligi yoki bir-biriga bog‘liq vazifalar.

**Kan algoritmi**: kiruvchi qirrasi yo‘q uchlardan boshlab, ularni navbat bilan olib tashlaymiz.

```python
from collections import deque

indeg = [0] * (n + 1)
for u in range(1, n + 1):
    for v in g[u]:
        indeg[v] += 1
q = deque(u for u in range(1, n + 1) if indeg[u] == 0)
order = []
while q:
    u = q.popleft()
    order.append(u)
    for v in g[u]:
        indeg[v] -= 1
        if indeg[v] == 0:
            q.append(v)
```

`len(order) < n` bo‘lsa, grafda sikl bor va bunday tartib mavjud emas.
""",
    "shortest-paths": """\
Vaznli grafda eng qisqa yo‘l. Qaysi algoritm — qirralarga bog‘liq:

| Holat | Algoritm | Murakkablik |
|---|---|---|
| vaznlar bir xil | BFS | O(V + E) |
| vaznlar ≥ 0 | Dijkstra | O(E log V) |
| manfiy vaznlar bor | Bellman–Ford | O(V·E) |
| barcha juftliklar, n ≤ 400 | Floyd–Warshall | O(n³) |

## Dijkstra

```python
import heapq

dist = [float("inf")] * n
dist[s] = 0
h = [(0, s)]
while h:
    d, v = heapq.heappop(h)
    if d > dist[v]:
        continue                     # eskirgan yozuv
    for to, w in g[v]:
        if d + w < dist[to]:
            dist[to] = d + w
            heapq.heappush(h, (dist[to], to))
```

Yo‘lning o‘zini tiklash uchun `parent[to] = v` saqlang va oxiridan orqaga yuring.
""",
    "union-find": """\
**DSU (birlashtiriladigan to‘plamlar)** — «`a` va `b` bir guruhdami?» va «guruhlarni birlashtir»
so‘rovlariga deyarli O(1) da javob beradi.

```python
parent = list(range(n))
size = [1] * n

def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]   # yo‘lni qisqartirish
        x = parent[x]
    return x

def union(a, b):
    a, b = find(a), find(b)
    if a == b:
        return False
    if size[a] < size[b]:
        a, b = b, a
    parent[b] = a
    size[a] += size[b]
    return True
```

## Qo‘llanishi

- **Kruskal** — minimal skelet daraxt: qirralarni vazn bo‘yicha saralab, sikl hosil qilmaganlarini olish.
- Dinamik bog‘lanish: «qirralar qo‘shilib boradi, nechta komponenta qoldi?»
- Ekvivalent elementlarni guruhlash (bir xil email’li akkauntlar va h.k.).
""",
    "trees": """\
**Daraxt** — sikli yo‘q bog‘langan graf: `n` ta uch va `n − 1` ta qirra. Bitta uchni **ildiz** deb
tanlasak, har uchning ota-onasi va bolalari bo‘ladi.

## Saqlash va aylanish

```python
g = [[] for _ in range(n)]
for _ in range(n - 1):
    u, v = map(int, input().split())
    g[u - 1].append(v - 1); g[v - 1].append(u - 1)

def dfs(v, parent):
    size = 1
    for to in g[v]:
        if to != parent:
            size += dfs(to, v)          # qism daraxt hajmi
    return size
```

## Asosiy tushunchalar

- **Chuqurlik** — ildizdan masofa; **balandlik** — eng uzoq bargcha.
- **Ikkilik qidiruv daraxti**: chapda kichiklar, o‘ngda kattalar.
- **Diametr**: istalgan uchdan eng uzoq `a` ni toping, `a` dan eng uzoq `b` — `a–b` diametr (ikki marta BFS/DFS).

Daraxtda DP ko‘p uchraydi: har uch uchun javob bolalarining javobidan yig‘iladi.
""",
    "segment-tree": """\
**Segmentlar daraxti** — massivda ikki xil amalni O(log n) da bajaradi: elementni **o‘zgartirish** va
oraliq bo‘yicha **so‘rov** (yig‘indi, minimum, maksimum). Prefiks yig‘indi faqat o‘zgarmas massivda ishlaydi;
o‘zgarishlar bo‘lsa — segmentlar daraxti.

```python
size = 1
while size < n:
    size *= 2
t = [float("inf")] * (2 * size)
t[size:size + n] = a
for i in range(size - 1, 0, -1):
    t[i] = min(t[2 * i], t[2 * i + 1])

def update(i, x):
    i += size; t[i] = x
    while i > 1:
        i //= 2
        t[i] = min(t[2 * i], t[2 * i + 1])

def query(l, r):                 # [l, r)
    res, l, r = float("inf"), l + size, r + size
    while l < r:
        if l & 1: res = min(res, t[l]); l += 1
        if r & 1: r -= 1; res = min(res, t[r])
        l //= 2; r //= 2
    return res
```

Faqat yig‘indi va nuqtali o‘zgarish kerak bo‘lsa, qisqaroq **Fenwick daraxti** ham yetadi.
""",
    "string-algorithms": """\
Matnda andoza qidirish va qism satrlarni tez solishtirish. Oddiy qidiruv `O(n · m)` vaqt oladi,
quyidagi usullar esa `O(n + m)`.

## Prefiks-funksiya (KMP)

`pi[i]` — `s[:i + 1]` ning eng uzun xos prefiksi uzunligi, bu prefiks ayni paytda suffiks ham bo‘lishi kerak.

```python
def prefix_function(s):
    pi = [0] * len(s)
    for i in range(1, len(s)):
        k = pi[i - 1]
        while k and s[i] != s[k]:
            k = pi[k - 1]
        if s[i] == s[k]:
            k += 1
        pi[i] = k
    return pi
```

`p` andozani `t` ichidan izlash: `p + "#" + t` uchun hisoblang. `pi` qiymati `len(p)` ga teng bo‘lgan
joyda andoza tugaydi.

## Z-funksiya

`z[i]` — `s` va `s[i:]` ning eng uzun umumiy prefiksi.

```python
def z_function(s):
    n = len(s)
    z = [0] * n
    l = r = 0
    for i in range(1, n):
        if i < r:
            z[i] = min(r - i, z[i - l])
        while i + z[i] < n and s[z[i]] == s[i + z[i]]:
            z[i] += 1
        if i + z[i] > r:
            l, r = i, i + z[i]
    return z
```

## Polinomial hash

Har prefiks uchun hash hisoblansa, istalgan ikki qism satrni `O(1)` da solishtirish mumkin.

```python
MOD, B = (1 << 61) - 1, 131
h, pw = [0] * (n + 1), [1] * (n + 1)
for i, ch in enumerate(s):
    h[i + 1] = (h[i] * B + ord(ch)) % MOD
    pw[i + 1] = pw[i] * B % MOD

def get(l, r):                     # s[l:r] ning hashi
    return (h[r] - h[l] * pw[r - l]) % MOD
```

Hashlar teng bo‘lsa, satrlar deyarli albatta teng. To‘qnashuv ehtimoli juda kichik, lekin nol emas.
""",
    "geometry": """\
## Asosiy formulalar

- Doira: yuzi `π·r²`, perimetri `2·π·r` (`math.pi`).
- Ikki nuqta orasidagi masofa: `math.dist((x1, y1), (x2, y2))`.
- Uchburchak yuzi (koordinatalar bilan): `abs((x2−x1)(y3−y1) − (x3−x1)(y2−y1)) / 2`.

## Vektor ko‘paytma — burilish yo‘nalishi

```python
def cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
# > 0 — chapga burilish, < 0 — o‘ngga, = 0 — bir chiziqda
```

## Diqqat

- Mumkin bo‘lsa **butun sonlarda** hisoblang: kvadrat masofalarni solishtiring, ildiz olmang.
- Haqiqiy sonlarni `==` bilan solishtirmang: `abs(a - b) < 1e-9`.
- Chiqishda kerakli aniqlik: `print(f"{x:.2f}")`.
""",
    # ---- SQL ----------------------------------------------------------------------------------------
    "sql": """\
SQL so‘rovi qaysi ma’lumot kerakligini aytadi, qanday topishni emas.

```sql
SELECT name, score
FROM students
WHERE city = 'Toshkent'
ORDER BY score DESC
LIMIT 3;
```

## Bajarilish tartibi

`FROM` → `WHERE` → `GROUP BY` → `HAVING` → `SELECT` → `ORDER BY` → `LIMIT`. Shuning uchun `WHERE` da
`COUNT(*)` ishlatib bo‘lmaydi — guruh shartini `HAVING` ga yozing.

## JOIN

```sql
SELECT c.name, SUM(o.amount) AS total
FROM customers c
LEFT JOIN orders o ON o.customer_id = c.id
GROUP BY c.id, c.name;
```

`LEFT JOIN` buyurtmasiz mijozlarni ham qoldiradi (ularda `o.amount` — `NULL`). `NULL` bilan solishtirish
`IS NULL` orqali, `= NULL` emas.
""",
    "select": """\
`SELECT` jadvaldan kerakli **ustunlarni** oladi.

```sql
SELECT name, age FROM students;          -- ikki ustun
SELECT * FROM students;                  -- hamma ustunlar
SELECT name, price * qty AS total        -- hisoblangan ustun, AS — nom berish
FROM order_items;
```

## Maslahatlar

- Masala so‘ragan ustunlarni **o‘sha tartibda** chiqaring — `*` ko‘pincha xato javob beradi.
- Ustun nomi masalada ko‘rsatilgan bo‘lsa, `AS` bilan aynan shunday nom bering.
- SQL kalit so‘zlari katta-kichik harfga sezgir emas, lekin o‘qish uchun katta harfda yozish odat.
""",
    "where": """\
`WHERE` faqat shartga mos **qatorlarni** qoldiradi.

```sql
SELECT name FROM students WHERE city = 'Toshkent';
SELECT * FROM products WHERE price BETWEEN 1000 AND 5000;
SELECT * FROM students WHERE grade >= 4 AND city <> 'Samarqand';
SELECT * FROM orders WHERE status IN ('new', 'paid');
```

## Diqqat

- Satrlar **bitta** qo‘shtirnoqda: `'Toshkent'`.
- `AND` `OR` dan oldin bajariladi — aralash shartlarni qavsga oling: `(a OR b) AND c`.
- `NULL` bilan `=` ishlamaydi: `IS NULL` / `IS NOT NULL` ishlating.
""",
    "distinct": """\
`DISTINCT` takrorlangan qatorlarni olib tashlaydi.

```sql
SELECT DISTINCT city FROM students;                 -- har shahar bir marta
SELECT DISTINCT city, faculty FROM students;        -- juftliklar bo‘yicha takrorsiz
SELECT COUNT(DISTINCT city) FROM students;          -- nechta turli shahar
```

`DISTINCT` butun qatorga ta’sir qiladi, bitta ustunga emas: `SELECT DISTINCT a, b` — `(a, b)` juftliklari takrorsiz.
""",
    "like": """\
`LIKE` satrni andoza bo‘yicha qidiradi: `%` — istalgan uzunlikdagi belgilar, `_` — bitta belgi.

```sql
SELECT name FROM students WHERE name LIKE 'A%';      -- A bilan boshlanadi
SELECT name FROM students WHERE name LIKE '%ova';    -- -ova bilan tugaydi
SELECT name FROM students WHERE name LIKE '%li%';    -- ichida "li" bor
SELECT code FROM rooms WHERE code LIKE 'A_1';        -- A, istalgan bitta belgi, 1
```

SQLite’da `LIKE` lotin harflari uchun katta-kichik harfni farqlamaydi. Aniq moslik kerak bo‘lsa — `=`.
""",
    "null-values": """\
`NULL` — «qiymat yo‘q». U hech narsaga teng emas, hatto o‘ziga ham.

```sql
SELECT name FROM customers WHERE phone IS NULL;
SELECT name, COALESCE(phone, 'yo‘q') AS phone FROM customers;   -- NULL o‘rniga qiymat
```

## Diqqat

- `WHERE phone = NULL` **hech qachon** ishlamaydi.
- `COUNT(*)` barcha qatorlarni, `COUNT(phone)` faqat `NULL` bo‘lmaganlarini sanaydi.
- `AVG`, `SUM` `NULL` larni o‘tkazib yuboradi.
- `LEFT JOIN` dan keyin moslik topilmagan ustunlar `NULL` bo‘ladi — «buyurtmasi yo‘q mijozlar» shundan topiladi.
""",
    "order-by": """\
`ORDER BY` natijani saralaydi: `ASC` — o‘sish (standart), `DESC` — kamayish.

```sql
SELECT name, price FROM products ORDER BY price DESC;
SELECT name, grade FROM students ORDER BY grade DESC, name ASC;   -- teng bo‘lsa — ism bo‘yicha
```

## Maslahatlar

- Masalada «teng bo‘lsa…» degan qoida bo‘lsa, uni **ikkinchi kalit** sifatida qo‘shing — aks holda
  tartib tasodifiy bo‘lib, javob noto‘g‘ri chiqishi mumkin.
- Hisoblangan ustun yoki uning `AS` nomi bo‘yicha ham saralash mumkin.
""",
    "limit": """\
`LIMIT` natijadan faqat dastlabki `n` qatorni qoldiradi. Deyarli doim `ORDER BY` bilan birga ishlatiladi.

```sql
SELECT name, price FROM products ORDER BY price DESC LIMIT 3;          -- eng qimmat 3 ta
SELECT name FROM students ORDER BY id LIMIT 10 OFFSET 20;              -- 21–30-qatorlar
```

## Diqqat

«Eng katta» chegarada teng qiymatlar bo‘lsa, `LIMIT` ulardan birini tasodifiy kesib tashlaydi.
Masala tenglarni ham so‘rasa, ichki so‘rov ishlating: `WHERE price = (SELECT MAX(price) FROM products)`.
""",
    "case-when": """\
`CASE` — SQL ichidagi `if/elif/else`. Yangi hisoblangan ustun yasash uchun.

```sql
SELECT name,
       CASE
           WHEN grade >= 90 THEN 'A'
           WHEN grade >= 75 THEN 'B'
           WHEN grade >= 60 THEN 'C'
           ELSE 'F'
       END AS letter
FROM students;
```

## Shartli sanash

```sql
SELECT faculty,
       SUM(CASE WHEN grade >= 4 THEN 1 ELSE 0 END) AS good,
       COUNT(*) AS total
FROM students GROUP BY faculty;
```

Shartlar yuqoridan pastga tekshiriladi — birinchi mos kelgani olinadi.
""",
    "string-functions": """\
Satrlar bilan ishlash (SQLite):

```sql
SELECT LENGTH(name) FROM students;                  -- uzunlik
SELECT UPPER(name), LOWER(name) FROM students;      -- katta / kichik harf
SELECT SUBSTR(name, 1, 3) FROM students;            -- 1-belgidan 3 ta
SELECT first_name || ' ' || last_name AS full_name FROM students;   -- birlashtirish
SELECT TRIM(name) FROM students;                    -- chetdagi bo‘sh joylar
SELECT REPLACE(phone, '-', '') FROM customers;
SELECT INSTR(email, '@') FROM customers;            -- belgining o‘rni
```

`SUBSTR` da sanash **1** dan boshlanadi. Domen: `SUBSTR(email, INSTR(email, '@') + 1)`.
""",
    "aggregation": """\
Agregat funksiyalar ko‘p qatorni **bitta qiymatga** aylantiradi.

```sql
SELECT COUNT(*) FROM students;                  -- qatorlar soni
SELECT AVG(grade), MAX(grade), MIN(grade) FROM students;
SELECT SUM(price * qty) AS revenue FROM order_items;
SELECT ROUND(AVG(grade), 2) FROM students;      -- 2 xonagacha yaxlitlash
```

## Diqqat

- `GROUP BY` siz agregat butun jadval uchun **bitta** qator qaytaradi.
- Agregat bilan birga oddiy ustun tanlash (`SELECT name, MAX(grade)`) — `GROUP BY` siz noaniq natija beradi.
- Butun sonlarni bo‘lishda butun natija chiqishi mumkin: `AVG` yoki `1.0 * a / b` ishlating.
""",
    "group-by": """\
`GROUP BY` qatorlarni bir xil qiymat bo‘yicha guruhlarga bo‘ladi; agregat funksiya **har guruh uchun** hisoblanadi.

```sql
SELECT city, COUNT(*) AS n
FROM students
GROUP BY city
ORDER BY n DESC;

SELECT faculty, ROUND(AVG(grade), 2) AS avg_grade
FROM students
GROUP BY faculty;
```

## Qoida

`SELECT` dagi har bir oddiy (agregat bo‘lmagan) ustun `GROUP BY` da ham bo‘lishi kerak.

Bajarilish tartibi: `FROM → WHERE → GROUP BY → HAVING → SELECT → ORDER BY → LIMIT`.
""",
    "having": """\
`HAVING` — guruhlar uchun `WHERE`. U `GROUP BY` dan **keyin** ishlaydi va agregatlar bilan shart qo‘yadi.

```sql
SELECT faculty, AVG(grade) AS avg_grade
FROM students
GROUP BY faculty
HAVING AVG(grade) >= 4;          -- o‘rtachasi 4 dan yuqori fakultetlar

SELECT customer_id FROM orders
GROUP BY customer_id
HAVING COUNT(*) >= 3;            -- kamida 3 ta buyurtma
```

Farqi: `WHERE` alohida qatorlarni guruhlashdan **oldin** filtrlaydi, `HAVING` tayyor guruhlarni.
""",
    "date-functions": """\
SQLite’da sanalar matn sifatida saqlanadi: `'2026-10-01'` yoki `'2026-10-01 14:30:00'`.

```sql
SELECT strftime('%Y', hired_at) AS year FROM employees;          -- yil
SELECT strftime('%Y-%m', created_at) AS month, SUM(amount)
FROM orders GROUP BY month;                                      -- oylik tushum
SELECT date('2026-10-01', '+7 days');                            -- sana arifmetikasi
SELECT julianday(end_date) - julianday(start_date) AS days FROM trips;   -- kunlar farqi
```

## Diqqat

- `strftime` matn qaytaradi: son bilan solishtirsangiz `CAST(strftime('%Y', d) AS INTEGER)`.
- `'YYYY-MM-DD'` formatidagi sanalarni oddiy `<`, `>` bilan solishtirish mumkin.
""",
    "join": """\
`JOIN` ikki jadval qatorlarini umumiy ustun bo‘yicha birlashtiradi. `INNER JOIN` (yoki shunchaki `JOIN`)
faqat **ikkala** jadvalda mosligi bor qatorlarni qoldiradi.

```sql
SELECT o.id, c.name
FROM orders o
JOIN customers c ON c.id = o.customer_id;

SELECT s.name, c.title
FROM enrollments e
JOIN students s ON s.id = e.student_id
JOIN courses c ON c.id = e.course_id;
```

## Maslahatlar

- Jadvallarga qisqa nom bering (`o`, `c`) va ustunlarni shu bilan yozing — bir xil nomli ustunlar chalkashmaydi.
- `ON` shartini unutsangiz, har qator har qator bilan juftlanadi (n·m qator).
""",
    "left-join": """\
`LEFT JOIN` chap jadvalning **barcha** qatorlarini qoldiradi; o‘ngda mosi bo‘lmasa, o‘ng ustunlar `NULL` bo‘ladi.

```sql
-- har mijoz va buyurtmalari soni (buyurtmasizlar ham, 0 bilan)
SELECT c.name, COUNT(o.id) AS orders
FROM customers c
LEFT JOIN orders o ON o.customer_id = c.id
GROUP BY c.id, c.name;

-- hech buyurtma bermagan mijozlar
SELECT c.name
FROM customers c
LEFT JOIN orders o ON o.customer_id = c.id
WHERE o.id IS NULL;
```

Diqqat: `COUNT(*)` emas, `COUNT(o.id)` — aks holda buyurtmasiz mijoz ham 1 deb sanaladi.
""",
    "subquery": """\
**Ichki so‘rov** — boshqa so‘rov ichidagi `SELECT`. Natijasi qiymat, ro‘yxat yoki jadval bo‘lishi mumkin.

```sql
-- o‘rtachadan yuqori maosh
SELECT name, salary FROM employees
WHERE salary > (SELECT AVG(salary) FROM employees);

-- buyurtma bergan mijozlar
SELECT name FROM customers
WHERE id IN (SELECT customer_id FROM orders);

-- har bo‘lim rekordchisi (bog‘liq ichki so‘rov)
SELECT name, department_id, salary FROM employees e
WHERE salary = (SELECT MAX(salary) FROM employees WHERE department_id = e.department_id);
```

Ko‘p qadamli so‘rovlarni `WITH` (CTE) bilan o‘qilishi oson qilib yozing:

```sql
WITH totals AS (SELECT customer_id, SUM(amount) AS s FROM orders GROUP BY customer_id)
SELECT * FROM totals WHERE s > 100000;
```
""",
    "window-functions": """\
**Oyna funksiyalari** qatorlarni guruhlamasdan, har qator yonida guruh bo‘yicha hisob qiladi.

```sql
-- bo‘lim ichida maosh bo‘yicha o‘rin
SELECT name, department_id, salary,
       RANK() OVER (PARTITION BY department_id ORDER BY salary DESC) AS rnk
FROM employees;

-- har bo‘limda top-2
SELECT * FROM (
    SELECT name, department_id, salary,
           DENSE_RANK() OVER (PARTITION BY department_id ORDER BY salary DESC) AS r
    FROM employees
) WHERE r <= 2;

-- yig‘ilib boruvchi yig‘indi va oldingi qiymat
SELECT day, amount,
       SUM(amount) OVER (ORDER BY day) AS running,
       LAG(amount) OVER (ORDER BY day) AS prev
FROM sales;
```

`ROW_NUMBER` — tenglarga ham turli raqam, `RANK` — teng o‘rin va keyin bo‘shliq (1, 1, 3),
`DENSE_RANK` — bo‘shliqsiz (1, 1, 2).
""",
}
