"""The first courses (study plans) and topic theory, built from problems already on the portal.

Plans are matched by slug and their sections rebuilt on every run, so editing this file and
re-running updates them (staff edits to these plans are overwritten; plans with other slugs are
left alone). Problems that don't exist yet are skipped with a note, but their section stays: it
shows its theory and "Masalalar tez orada" until problems arrive. Topics missing from the portal
are created; theory is written only where a topic has none, so text written by staff is never replaced.

    python manage.py add_study_plans [--dry-run]
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.learn.models import PlanItem, PlanSection, StudyPlan
from apps.problems.models import Problem, Tag

from ._more_topics import MORE_TOPICS, SQL_TOPICS

PLANS = [
    {
        "slug": "birinchi-qadam", "title": "Birinchi qadam", "level": "beginner", "icon": "footprints",
        "order": 1, "in_quest": True,
        "summary": "Kirish-chiqish, shartlar va sikllar: dasturlashni noldan boshlaganlar uchun.",
        "description_md": (
            "Bu kurs dasturlashni endi boshlaganlar uchun. Har bo‘lim oddiy masaladan boshlanadi va asta-sekin "
            "qiyinlashadi. Masalani yecha olmasangiz — bo‘lim boshidagi mavzu sahifasini o‘qing, so‘ng qayting.\n\n"
            "Maslahat: har kuni 3–5 ta masala yeching. Bir haftada kurs tugaydi."
        ),
        "sections": [
            {"title": "Kirish va chiqish",
             "intro": "Sonlarni o‘qish, hisoblash va natijani chiqarish. Nazariya: [input-output](/learn/topics/input-output/).",
             "slugs": ["a-plus-b", "rectangle", "last-digit", "digit-sum-3", "reverse-two-digit", "c-sum-product",
                       "c-middle-digit", "seconds-to-hms", "p1-olmalarni-bolish", "p1-kinoteatrda-orin",
                       "p1-poyezd-yoli", "p1-bayram-konfetlari"]},
            {"title": "Shartlar",
             "intro": "`if`, `elif`, `else` bilan qaror qabul qilish. Nazariya: [conditionals](/learn/topics/conditionals/).",
             "slugs": ["even-odd", "max-of-two", "min-of-three", "compare", "sign", "abs", "p1-ish-kunimi",
                       "p1-son-oraliqdami", "leap-year", "divisible-3-5", "grade", "p1-ortancha-son", "sort-three",
                       "triangle", "days-in-month", "p1-svetofor", "p1-tenglama-ildizlari", "p1-nuqta-va-aylana",
                       "p1-shaxmat-katagi", "c-queen"]},
            {"title": "Sikllar",
             "intro": "Bir ishni ko‘p marta takrorlash: `for` va `while`. Nazariya: [loops](/learn/topics/loops/).",
             "slugs": ["p1-faktorial", "p1-raqamlar-soni", "p1-raqamlar-kopaytmasi", "p1-eng-issiq-eng-sovuq",
                       "p1-musbat-manfiy-nol", "p1-yulduzcha-zinapoya", "p1-boluvchilar-soni", "p1-tub-sonmi",
                       "p1-quyonlar-oilasi", "p1-bakteriyalar", "p1-raqamli-ildiz", "p1-jamgarma"]},
            {"title": "Hayotiy masalalar",
             "intro": "Uzun shartli matnni kodga aylantirish. Diqqat bilan o‘qing: har bir chegara muhim.",
             "slugs": ["taxi-fare", "electricity-bill", "walk-or-taxi", "exam-pass", "password-check", "parking-fee",
                       "c2-change", "c2-delivery", "c2-phone-plan", "c2-elevator"]},
        ],
    },
    {
        "slug": "massiv-va-satrlar", "title": "Massiv va satrlar", "level": "easy", "icon": "brackets",
        "order": 2, "in_quest": True,
        "summary": "Ro‘yxatlar, satrlar, hash-jadval va ikki ko‘rsatkich — algoritmlardan oldingi asos.",
        "description_md": (
            "Bu kursda ko‘p sonlar bilan ishlaymiz. Kirish hajmi katta (10⁵ gacha): ikki ichma-ich sikl "
            "vaqtga sig‘maydi, shuning uchun har masalada **chiziqli** yechim izlang."
        ),
        "sections": [
            {"title": "Massivlar",
             "intro": "Ro‘yxatni bir marta aylanib chiqib javob topish. Nazariya: [arrays](/learn/topics/arrays/).",
             "slugs": ["p2-hisobdagi-pul", "p2-eng-boy-mijoz", "p2-ketma-ket-birlar", "p2-yoqolgan-son",
                       "p2-paskal-uchburchagi", "p2-aksiya-savdosi"]},
            {"title": "Satrlar",
             "intro": "Belgilar, so‘zlar va ularni qayta ishlash. Nazariya: [strings](/learn/topics/strings/).",
             "slugs": ["p2-oxirgi-soz-uzunligi", "p2-sozni-topish", "p2-teskari-sozlar", "p2-umumiy-boshlanish",
                       "p2-katta-songa-bir", "p2-rim-raqamlari", "p2-jadval-ustuni"]},
            {"title": "Hash-jadval",
             "intro": "`set` va `dict`: «bormi?» savoliga bir zumda javob. Nazariya: [hash-table](/learn/topics/hash-table/).",
             "slugs": ["p2-qimmatbaho-toshlar", "p2-takror-bormi", "p2-anagramma", "p2-gazetadan-xat",
                       "p2-kerakli-juftlik", "p2-kopchilik-ovozi", "p2-umumiy-sonlar", "p2-yaxshi-juftliklar",
                       "p2-baxtli-son"]},
            {"title": "Ikki ko‘rsatkich",
             "intro": "Ikki indeks bilan ro‘yxatni bir o‘tishda qayta ishlash. Nazariya: [two-pointers](/learn/topics/two-pointers/).",
             "slugs": ["p2-nollarni-oxiriga", "p2-takrorlarni-olib-tashlash", "p2-ikki-saralangan-royxat",
                       "p2-kvadratlar-tartibi"]},
            {"title": "Matematika va bitlar",
             "intro": "Formulalar, XOR va butun ildiz. Nazariya: [bit-manipulation](/learn/topics/bit-manipulation/).",
             "slugs": ["p2-ikkining-darajasi", "p2-juftsiz-son", "p2-butun-ildiz", "p2-zinapoya"]},
        ],
    },
    {
        "slug": "algoritmlarga-kirish", "title": "Algoritmlarga kirish", "level": "medium", "icon": "route",
        "order": 3, "in_quest": True,
        "summary": "Prefiks yig‘indi, ikkilik qidiruv, stek, DP va graflar — har biriga bitta asosiy masala.",
        "description_md": (
            "Har bo‘limda bitta klassik g‘oya. Oddiy yechim vaqt chegarasiga sig‘maydi — avval mavzu sahifasini "
            "o‘qing, keyin yeching. Qiynalsangiz, masala sahifasidagi maslahatlardan foydalaning."
        ),
        "sections": [
            {"title": "Prefiks yig‘indilar",
             "intro": "Oraliq yig‘indisini O(1) da topish. Nazariya: [prefix-sums](/learn/topics/prefix-sums/).",
             "slugs": ["oraliq-yigindilari"]},
            {"title": "Siljuvchi oyna",
             "intro": "Ikki ko‘rsatkich bilan eng uzun mos oraliq. Nazariya: [two-pointers](/learn/topics/two-pointers/).",
             "slugs": ["eng-uzun-oraliq"]},
            {"title": "Ikkilik qidiruv",
             "intro": "Saralangan ro‘yxatda log n qadamda qidirish. Nazariya: [binary-search](/learn/topics/binary-search/).",
             "slugs": ["narxlar-sorovlari"]},
            {"title": "Stek",
             "intro": "Oxirgi kirgan — birinchi chiqadi. Nazariya: [data-structures](/learn/topics/data-structures/).",
             "slugs": ["qavslar-balansi"]},
            {"title": "Dinamik dasturlash",
             "intro": "Katta masalani kichik masalalar javobidan yig‘ish. Nazariya: [dynamic-programming](/learn/topics/dynamic-programming/).",
             "slugs": ["tangalar-bilan-tolash", "eng-uzun-osuvchi"]},
            {"title": "Graflar",
             "intro": "BFS, Dijkstra va minimal skelet daraxt. Nazariya: [graphs](/learn/topics/graphs/).",
             "slugs": ["labirint", "shaharlar-yollari", "yollar-tarmogi"]},
            {"title": "Oraliq so‘rovlari",
             "intro": "Ko‘p so‘rovga tez javob beradigan tuzilma: segmentlar daraxti.",
             "slugs": ["oraliq-minimumi"]},
        ],
    },
    {
        "slug": "malumotlar-tuzilmalari", "title": "Ma’lumotlar tuzilmalari", "level": "medium", "icon": "layers",
        "order": 4, "in_quest": True,
        "summary": "Stek, navbat, lug‘at, uyum, DSU va segmentlar daraxti — qachon qaysi biri kerak.",
        "description_md": (
            "To‘g‘ri tuzilma tanlansa, sekin yechim tezlashadi. Har bo‘limda avval tuzilmaning g‘oyasini o‘qing: "
            "u qaysi amalni tez bajaradi va qaysi masalalarda uchraydi.\n\n"
            "Masalasi hali yo‘q bo‘limlarda nazariya tayyor — masalalar tez orada qo‘shiladi."
        ),
        "sections": [
            {"title": "Stek",
             "intro": "Oxirgi kirgan — birinchi chiqadi: qavslar, monoton stek. Nazariya: [stack](/learn/topics/stack/).",
             "slugs": ["qavslar-balansi"]},
            {"title": "Navbat va deque",
             "intro": "Birinchi kirgan — birinchi chiqadi; oyna maksimumi. Nazariya: [queue](/learn/topics/queue/).",
             "slugs": []},
            {"title": "Lug‘at va to‘plam",
             "intro": "Sanash, juftlik izlash va takrorsiz oraliqlar. Nazariya: [hash-table](/learn/topics/hash-table/).",
             "slugs": ["c3-pair-sum", "c3-top-word", "c3-unique-substring"]},
            {"title": "Uyum (heap)",
             "intro": "Eng kichigini tez olish: ustuvor navbat. Nazariya: [heap](/learn/topics/heap/).",
             "slugs": []},
            {"title": "Bog‘langan ro‘yxat",
             "intro": "Tugunlar va havolalar; sekin va tez ko‘rsatkich. Nazariya: [linked-list](/learn/topics/linked-list/).",
             "slugs": []},
            {"title": "DSU",
             "intro": "Guruhlarni birlashtirish va «bir guruhdami?» savoli. Nazariya: [union-find](/learn/topics/union-find/).",
             "slugs": []},
            {"title": "Segmentlar daraxti",
             "intro": "Oraliq so‘rovlari va o‘zgarishlar O(log n) da. Nazariya: [segment-tree](/learn/topics/segment-tree/).",
             "slugs": ["oraliq-minimumi"]},
        ],
    },
    {
        "slug": "rekursiya-va-qidiruv", "title": "Rekursiya va qidiruv", "level": "medium", "icon": "puzzle",
        "order": 5, "in_quest": True,
        "summary": "Rekursiya, to‘liq perebor, backtracking va ikkilik qidiruv.",
        "description_md": (
            "Ko‘p masalani «hamma variantni tekshir» deb boshlash mumkin. Bu kurs shu fikrni tartibga soladi: "
            "rekursiya bilan variantlarni yozish, keraksiz shoxlarni kesish va javobni ikkilik qidiruv bilan topish."
        ),
        "sections": [
            {"title": "Rekursiya",
             "intro": "Funksiya o‘zini kichikroq kirish bilan chaqiradi. Nazariya: [recursion](/learn/topics/recursion/).",
             "slugs": []},
            {"title": "To‘liq perebor",
             "intro": "Kichik chegaralarda barcha variantlarni tekshirish. Nazariya: [brute-force](/learn/topics/brute-force/).",
             "slugs": []},
            {"title": "Backtracking",
             "intro": "Javobni qadamma-qadam qurish va orqaga qaytish. Nazariya: [backtracking](/learn/topics/backtracking/).",
             "slugs": []},
            {"title": "Ikkilik qidiruv",
             "intro": "Saralangan ro‘yxatda log n qadamda qidirish. Nazariya: [binary-search](/learn/topics/binary-search/).",
             "slugs": ["p2-butun-ildiz", "narxlar-sorovlari"]},
            {"title": "Javob bo‘yicha ikkilik qidiruv",
             "intro": "«X yetarlimi?» monoton bo‘lsa, eng kichik X ni topish. Nazariya: [binary-search](/learn/topics/binary-search/).",
             "slugs": []},
            {"title": "Bo‘l va hukmronlik qil",
             "intro": "Ikkiga bo‘lib, alohida yechib, birlashtirish. Nazariya: [divide-and-conquer](/learn/topics/divide-and-conquer/).",
             "slugs": []},
        ],
    },
    {
        "slug": "graflar", "title": "Graflar", "level": "hard", "icon": "network",
        "order": 6, "in_quest": True,
        "summary": "BFS, DFS, eng qisqa yo‘l, minimal skelet daraxt va daraxtlar.",
        "description_md": (
            "Shaharlar va yo‘llar, labirint kataklari, do‘stlar tarmog‘i — hammasi graf. Avval grafni xotirada "
            "saqlashni o‘rganing, keyin har bo‘limdagi algoritm qaysi savolga javob berishini tushuning."
        ),
        "sections": [
            {"title": "Graf tasviri",
             "intro": "Uchlar, qirralar va qo‘shnilar ro‘yxati. Nazariya: [graphs](/learn/topics/graphs/).",
             "slugs": []},
            {"title": "BFS",
             "intro": "Qatlam-qatlam yurish: vaznsiz grafda eng qisqa yo‘l. Nazariya: [bfs](/learn/topics/bfs/).",
             "slugs": ["labirint"]},
            {"title": "DFS va komponentalar",
             "intro": "Chuqurlik bo‘yicha yurish, komponentalar va sikllar. Nazariya: [dfs](/learn/topics/dfs/).",
             "slugs": []},
            {"title": "Eng qisqa yo‘l",
             "intro": "Vaznli grafda Dijkstra. Nazariya: [shortest-paths](/learn/topics/shortest-paths/).",
             "slugs": ["shaharlar-yollari"]},
            {"title": "Minimal skelet daraxt",
             "intro": "Kruskal va DSU: hamma uchni eng arzon bog‘lash. Nazariya: [union-find](/learn/topics/union-find/).",
             "slugs": ["yollar-tarmogi"]},
            {"title": "Daraxtlar",
             "intro": "Ildiz, chuqurlik, qism daraxt va diametr. Nazariya: [trees](/learn/topics/trees/).",
             "slugs": []},
        ],
    },
    {
        "slug": "dinamik-dasturlash", "title": "Dinamik dasturlash", "level": "hard", "icon": "brain",
        "order": 7, "in_quest": True,
        "summary": "Holat va o‘tish: zinapoya, tangalar, ketma-ketliklar, ryukzak.",
        "description_md": (
            "DP — musobaqalarda eng ko‘p uchraydigan mavzu. Har masalada to‘rt savolga javob bering: holat nima, "
            "o‘tish qanday, boshlang‘ich qiymat va javob qayerda. Nazariya: "
            "[dynamic-programming](/learn/topics/dynamic-programming/)."
        ),
        "sections": [
            {"title": "Asoslar",
             "intro": "Eng oddiy DP: oldingi javoblardan keyingisini yig‘ish. Nazariya: [dynamic-programming](/learn/topics/dynamic-programming/).",
             "slugs": ["p2-zinapoya"]},
            {"title": "Bir o‘lchovli DP",
             "intro": "`dp[i]` — i gacha bo‘lgan eng yaxshi javob. Nazariya: [dynamic-programming](/learn/topics/dynamic-programming/).",
             "slugs": ["tangalar-bilan-tolash"]},
            {"title": "Ketma-ketliklar",
             "intro": "Eng uzun o‘suvchi va umumiy qism ketma-ketliklar. Nazariya: [dynamic-programming](/learn/topics/dynamic-programming/).",
             "slugs": ["eng-uzun-osuvchi"]},
            {"title": "Ryukzak",
             "intro": "Sig‘im chegarasida eng qimmat to‘plam. Nazariya: [dynamic-programming](/learn/topics/dynamic-programming/).",
             "slugs": []},
            {"title": "Ikki o‘lchovli DP",
             "intro": "To‘rdagi yo‘llar va ikki satr bo‘yicha holat. Nazariya: [dynamic-programming](/learn/topics/dynamic-programming/).",
             "slugs": []},
        ],
    },
    {
        "slug": "matematika-va-sonlar", "title": "Matematika va sonlar", "level": "easy", "icon": "sigma",
        "order": 8, "in_quest": False,
        "summary": "Bo‘luvchilar, tub sonlar, kombinatorika, geometriya va bitlar.",
        "description_md": (
            "Ko‘p masalada sikl o‘rniga formula bor. Bu kursda olimpiada matematikasining asosiy vositalari: "
            "bo‘luvchilar, EKUB, modul bo‘yicha hisob, sanash va oddiy geometriya."
        ),
        "sections": [
            {"title": "Bo‘luvchilar va tub sonlar",
             "intro": "√n gacha tekshirish va Eratosfen g‘alviri. Nazariya: [number-theory](/learn/topics/number-theory/).",
             "slugs": ["p1-boluvchilar-soni", "p1-tub-sonmi", "qutilarga-teng-bolish-boluvchilar",
                       "wc1-tub-kopaytuvchilar"]},
            {"title": "EKUB va modul",
             "intro": "EKUB, EKUK va katta javobni `10⁹ + 7` bo‘yicha hisoblash. Nazariya: [number-theory](/learn/topics/number-theory/).",
             "slugs": []},
            {"title": "Kombinatorika",
             "intro": "Tanlashlar va juftliklarni sanash. Nazariya: [combinatorics](/learn/topics/combinatorics/).",
             "slugs": ["p2-paskal-uchburchagi", "p2-yaxshi-juftliklar"]},
            {"title": "Geometriya",
             "intro": "Masofa, yuz va burilish yo‘nalishi. Nazariya: [geometry](/learn/topics/geometry/).",
             "slugs": ["doira-perimetri-va-yuzi", "p1-nuqta-va-aylana"]},
            {"title": "Bitlar",
             "intro": "Ikkilik sanoq va XOR xossalari. Nazariya: [bit-manipulation](/learn/topics/bit-manipulation/).",
             "slugs": ["wc1-ikkilik-son", "p2-ikkining-darajasi", "p2-juftsiz-son"]},
        ],
    },
    {
        "slug": "musobaqaga-tayyorgarlik", "title": "Musobaqaga tayyorgarlik", "level": "medium", "icon": "trophy",
        "order": 9, "in_quest": False,
        "summary": "Murakkablikni baholash, ehtiyotkor kod, perebor, ochko‘z va siljuvchi oyna.",
        "description_md": (
            "Musobaqada g‘oyani bilish yetmaydi: yechim vaqtga sig‘ishini oldindan baholash, chegaraviy holatlarni "
            "unutmaslik va xatoni tez topish kerak. Bu kurs shu ko‘nikmalar uchun."
        ),
        "sections": [
            {"title": "Murakkablik",
             "intro": "Kod yozishdan oldin yechim vaqtga sig‘adimi? Nazariya: [complexity](/learn/topics/complexity/).",
             "slugs": []},
            {"title": "Ehtiyotkor bajarish",
             "intro": "Shartni aniq bajarish va chegaraviy holatlar. Nazariya: [implementation](/learn/topics/implementation/).",
             "slugs": []},
            {"title": "Perebor va stress-test",
             "intro": "Sekin, lekin to‘g‘ri yechim bilan tezini tekshirish. Nazariya: [brute-force](/learn/topics/brute-force/).",
             "slugs": []},
            {"title": "Ochko‘z algoritmlar",
             "intro": "Har qadamda eng yaxshi tanlov — qachon ishlaydi. Nazariya: [greedy](/learn/topics/greedy/).",
             "slugs": []},
            {"title": "Siljuvchi oyna",
             "intro": "Oraliqni ikki ko‘rsatkich bilan surish. Nazariya: [sliding-window](/learn/topics/sliding-window/).",
             "slugs": ["eng-uzun-oraliq"]},
        ],
    },
    {
        "slug": "sql-asoslari", "title": "SQL asoslari", "level": "beginner", "icon": "database",
        "order": 10, "in_quest": False,
        "summary": "SELECT dan oyna funksiyalarigacha: talabalar, mahsulotlar va buyurtmalar jadvallarida.",
        "description_md": (
            "Har masalada jadvallar va kutilgan natija ko‘rsatilgan. So‘rovingiz yashirin ma’lumotlarda ham "
            "tekshiriladi, shuning uchun javobni «qo‘lda» emas, umumiy holda yozing. Nazariya: [sql](/learn/topics/sql/)."
        ),
        "sections": [
            {"title": "SELECT va WHERE",
             "intro": "Kerakli ustun va qatorlarni tanlash. Nazariya: [select](/learn/topics/select/), "
                      "[where](/learn/topics/where/), [distinct](/learn/topics/distinct/), [like](/learn/topics/like/), "
                      "[null-values](/learn/topics/null-values/).",
             "slugs": ["sql-talabalar-royxati", "sql-toshkentlik-talabalar", "sql-alochi-talabalar",
                       "sql-tugilgan-yillar", "sql-a-harfli-ismlar", "sql-telefonsiz-mijozlar",
                       "sql-mijozlar-shaharlari"]},
            {"title": "Saralash va hisoblangan ustunlar",
             "intro": "`ORDER BY`, `LIMIT`, `CASE` va ifodalar. Nazariya: [order-by](/learn/topics/order-by/), "
                      "[limit](/learn/topics/limit/), [case-when](/learn/topics/case-when/), "
                      "[string-functions](/learn/topics/string-functions/).",
             "slugs": ["sql-narx-boyicha-tartib", "sql-eng-qimmat-uchta", "sql-ombordagi-qiymat", "sql-ism-uzunligi",
                       "sql-baho-harfi"]},
            {"title": "Guruhlash",
             "intro": "`GROUP BY`, `COUNT`, `AVG` va `HAVING`. Nazariya: [group-by](/learn/topics/group-by/), "
                      "[aggregation](/learn/topics/aggregation/), [having](/learn/topics/having/), "
                      "[date-functions](/learn/topics/date-functions/).",
             "slugs": ["sql-shahar-boyicha-talabalar", "sql-guruh-ortacha-bali", "sql-kategoriya-narxlari",
                       "sql-ombor-hisoboti", "sql-yaxshi-guruhlar", "sql-yil-boyicha-yollanganlar"]},
            {"title": "JOIN",
             "intro": "Bir nechta jadvalni bog‘lash: `JOIN` va `LEFT JOIN`. Nazariya: [join](/learn/topics/join/), "
                      "[left-join](/learn/topics/left-join/).",
             "slugs": ["sql-buyurtma-egalari", "sql-xodimlar-bolimlari", "sql-mijozlar-xarajati",
                       "sql-kurslar-talabalar-soni", "sql-buyurtmasiz-mijozlar"]},
            {"title": "Murakkab so‘rovlar",
             "intro": "Ichki so‘rovlar va oyna funksiyalari. Nazariya: [subquery](/learn/topics/subquery/), "
                      "[window-functions](/learn/topics/window-functions/).",
             "slugs": ["sql-ortachadan-yuqori-maosh", "sql-bolim-rekordchilari", "sql-bolimdagi-top-2",
                       "sql-oylik-tushum", "sql-ketma-ket-uch-kun"]},
        ],
    },
]

TOPICS = {
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
    "loops": """\
Sikl bir ishni ko‘p marta bajaradi.

```python
for i in range(1, n + 1):   # 1, 2, ..., n
    s += i

while n > 0:                # raqamlarni ajratish
    d = n % 10
    n //= 10
```

## Qachon qaysi biri

- **`for`** — necha marta takrorlanishi oldindan ma’lum bo‘lsa.
- **`while`** — shart bajarilguncha (masalan, son 0 bo‘lguncha).

## Tez-tez uchraydigan andozalar

- Yig‘indi / ko‘paytma: o‘zgaruvchini 0 (yoki 1) dan boshlang.
- Eng katta / eng kichik: birinchi elementdan boshlang, cheksizlikdan emas.
- Bo‘luvchilar: `i * i <= n` gacha yetarli — √n qadam.
""",
    "math": """\
Ko‘p masalada sikl o‘rniga **formula** bor.

- 1 dan n gacha yig‘indi: `n * (n + 1) // 2`.
- Yuqoriga yaxlitlab bo‘lish: `(a + b - 1) // b`.
- EKUB: `math.gcd(a, b)`; EKUK: `a // gcd(a, b) * b`.
- Oxirgi raqam: `n % 10`; raqamlar soni: `len(str(n))`.

Javob juda katta bo‘lsa, masala odatda `10⁹ + 7` ga qoldiqni so‘raydi: har qadamda `% MOD` oling.
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
    "greedy": """\
Ochko‘z (greedy) algoritm har qadamda **hozir eng yaxshi ko‘ringan** tanlovni qiladi va ortga qaytmaydi.

Ishlashi uchun tanlov «xavfsiz» bo‘lishi kerak: hech qachon yomonroq natijaga olib kelmasligi.
Ko‘pincha avval saralash kerak bo‘ladi (eng erta tugaydigan ish, eng arzon narx).

Ishonchingiz komil bo‘lmasa, kichik misollarda to‘liq tanlash (brute force) bilan solishtirib ko‘ring.
""",
    "data-structures": """\
To‘g‘ri tuzilma algoritmni tezlashtiradi.

| Tuzilma | Python | Amal |
|---|---|---|
| Stek | `list`: `append`, `pop` | oxirgisi birinchi chiqadi |
| Navbat | `collections.deque` | birinchisi birinchi chiqadi |
| Uyum | `heapq` | eng kichikni O(log n) da olish |
| To‘plam | `set`, `dict` | «bormi?» O(1) |

**Stek** qavslar balansi uchun klassik: ochilgan qavsni stekka qo‘ying, yopilganda tepasi mos kelishini tekshiring.

**Segmentlar daraxti** — oraliqdagi minimum/yig‘indini O(log n) da beradi va o‘zgarishlarga ham chidaydi.
""",
    "bit-manipulation": """\
Sonlar ikkilik ko‘rinishda saqlanadi; bit amallari juda tez.

- `a & b` (VA), `a | b` (YOKI), `a ^ b` (XOR), `x << k` = x·2ᵏ, `x >> k` = x // 2ᵏ.
- n ikkining darajasimi: `n > 0 and n & (n - 1) == 0`.
- Birlar soni: `bin(n).count("1")`.

**XOR** xossasi: `x ^ x = 0`, `x ^ 0 = x`. Shuning uchun hamma son juft marta uchragan ro‘yxatda
juftsiz sonni barcha elementlarni XOR qilib topish mumkin.
""",
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
}


class Command(BaseCommand):
    help = "Create/refresh the starter study plans and fill empty topic theory."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show what would change, write nothing.")

    def handle(self, *args, dry_run=False, **options):
        with transaction.atomic():
            for spec in PLANS:
                self._plan(spec)
            filled = 0
            for name, text in {**TOPICS, **MORE_TOPICS}.items():
                kind = Tag.Kind.SQL if name in SQL_TOPICS else Tag.Kind.CODE
                tag, _ = Tag.objects.get_or_create(name=name, defaults={"kind": kind})
                if not tag.about_md.strip():
                    tag.about_md = text
                    tag.save(update_fields=["about_md"])
                    filled += 1
            self.stdout.write(f"mavzular: {filled} tasiga nazariya yozildi")
            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write("dry-run: hech narsa saqlanmadi")

    def _plan(self, spec: dict) -> None:
        fields = {k: spec[k] for k in ("title", "level", "icon", "order", "in_quest", "summary", "description_md")}
        plan, created = StudyPlan.objects.update_or_create(slug=spec["slug"], defaults={**fields, "is_public": True})
        plan.sections.all().delete()
        slugs = [s for section in spec["sections"] for s in section["slugs"]]
        found = Problem.objects.filter(slug__in=slugs, status=Problem.Status.APPROVED).in_bulk(field_name="slug")
        n = 0
        for order, section_spec in enumerate(spec["sections"]):
            problems = [found[s] for s in section_spec["slugs"] if s in found]
            section = PlanSection.objects.create(plan=plan, title=section_spec["title"],
                                                 intro_md=section_spec["intro"], order=order)
            PlanItem.objects.bulk_create([PlanItem(section=section, problem=p, order=i) for i, p in enumerate(problems)])
            n += len(problems)
        missing = [s for s in slugs if s not in found]
        self.stdout.write(f"{'yaratildi' if created else 'yangilandi'} {plan.slug}: {n} ta masala")
        if missing:
            self.stdout.write(f"  topilmadi ({len(missing)}): {', '.join(missing)}")
