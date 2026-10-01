# O'rganish: "1 mavzu = 1 kurs" — yakuniy taklif

**Holat:** muhokama uchun qoralama (2026-10-01). Hali hech narsa amalga oshirilmagan.
**Asos:** `~/Downloads/claude-code-prompt-learn.md` va prod ma'lumotlari (2026-10-01 da tekshirildi).

## 1. Qisqa xulosa

G'oya to'g'ri: "Kurslar" va "Qo'llanma" bitta tushunchaga birlashadi, har mavzu bitta kurs bo'ladi (nazariya va masalalar).
Buni quyidagi tuzatishlar bilan qilishni taklif qilaman:

1. Masala kursga **teg orqali** kiradi, qo'lda tuzilgan ro'yxat orqali emas. Shunda masalalar soni hamma joyda bir xil
   ko'rinadi va yangi masala kursga o'zi tushadi.
2. **SQL** alohida bosqich bo'lib qoladi (5 kurs). Aks holda 29 ta masala va 18 ta mavzu yo'qoladi.
3. Kurslar soni yana 38 ta, lekin tarkibi boshqacha: 5 ta dasturlash kursi birlashtiriladi yoki keyinga suriladi,
   o'rniga 5 ta SQL kursi keladi.
4. Masalasi yo'q kurslar yo'lda ko'rinadi, lekin progressga va "Davom ettirish"ga xalaqit bermaydi.
5. Foydalanuvchi ma'lumoti xavf ostida emas: progress saqlanmaydi, har safar yechimlardan hisoblanadi.

## 2. Hozirgi holat (prod, 2026-10-01)

| | |
|---|---|
| Ochiq masalalar | 193 (164 ta dasturlash + 29 ta SQL) |
| Qiyinlik bo'yicha | beginner 106 · easy 64 · medium 15 · hard 8 |
| Kurslar | 10 ta; 193 masaladan 128 tasi biror kursda |
| Qo'llanma mavzulari | 54 ta (36 ta dasturlash + 18 ta SQL); nazariya `Tag.about_md` da |
| Staff tahrirlagan nazariya | yo'q (prod matni repodagi bilan bir xil) |
| Kurs nishonini olgan foydalanuvchilar | 0 |
| Yechimi bor foydalanuvchilar | 81 |

Eng katta teglar: `math` 54, `conditionals` 52, `loops` 50, `strings` 25, `input-output` 21, `implementation` 20,
`arrays` 16, `hash-table` 14. Qolgan barcha dasturlash teglarida 0–5 tadan masala bor.

Ikki muhim xulosa:

- **Progress xavfsiz.** Yechimlar `UserProblemSolved` da saqlanadi. Kurs progressi, "Davom ettirish" va nishonlar
  undan har safar hisoblanadi. Kurslarni qayta qurish yechim, urinish, reyting va ballarga tegmaydi. Hali hech kim
  kurs nishonini olmagan, shuning uchun yo'qoladigan nishon ham yo'q.
- **Masala tanqis.** Medium va hard masalalar jami 23 ta. Qayta tuzish bu muammoni hal qilmaydi: 10-kursdan keyingi
  kurslarda 0–5 tadan masala bo'ladi.

## 3. Asl promptdagi kamchiliklar

1. Kontekst eskirgan: kurslar 3 ta emas, 10 ta; mavzular 54 ta. Moslik jadvali ularning hammasini qamrashi kerak (§6).
2. Alohida "Qo'llanma modeli" yo'q: nazariya `Tag` ichida turadi. `Tag` o'chmaydi, chunki masalalar filtri,
   moderatsiya va profildagi ko'nikmalar xaritasi unga bog'liq.
3. SQL umuman tushib qolgan.
4. `Advanced` darajasi yo'q. Kurs darajasi masala bilan umumiy ro'yxatdan olinadi: beginner, easy, medium, hard.
5. `/learn/<slug>/` band URL lar bilan to'qnashadi: `lists` ("Ro'yxatlarim"; 8-kurs slugi ham `lists`), `topics`,
   `plans`, `save`.
6. Faqat mavjud kurslardagi masalalar taqsimlanadi. Natijada 65 ta masala chetda qoladi.
7. "Masalalarga tegma" cheklovi "`loops` ni ikkiga bo'l" talabiga zid: bo'lish masalalarning teglarini o'zgartiradi.
8. Staff uchun kursni tahrirlash sahifasi aytilmagan. Django admin ishlatilmaydi, hammasi sayt ichida bo'lishi kerak.
9. Kurs kontenti migratsiya ichida emas, qayta ishga tushiriladigan buyruqda bo'lishi kerak
   (hozirgi `add_study_plans` kabi).
10. Ctrl K qidiruvi `apps/problems/views.py` da. Bu faylda commit qilinmagan katta o'zgarishlaringiz bor.
11. Ba'zi kurslarga judge masala bera olmaydi. `functions` va `tuples-sets`: judge faqat stdin/stdout ni tekshiradi,
    funksiya yoki tuple ishlatilganini bilmaydi. `complexity` esa tabiatan faqat nazariya.
12. Bosqichlar aralash: "Ma'lumot tuzilmalari"da funksiyalar va rekursiya turibdi, stek va uyum esa "Texnikalar"da.
    `recursion` (Medium) Easy kurslar orasida joylashgan.

## 4. Taklif: qanday ishlaydi

### 4.1 Ma'lumotlar modeli

- `StudyPlan` kursga aylanadi. Xohlasangiz nomi `Course` ga o'zgartiriladi (`RenameModel`, qaytariladi).
  Maydonlar: `slug`, `title`, `stage`, `order`, `level`, `summary`, `theory_md`, `tags` (M2M → `Tag`), `is_public`.
- Kurs masalalari: kurs teglaridan **istalgan biri** qo'yilgan ochiq masalalar. Bitta kursga bir nechta teg
  ulanishi mumkin (masalan, graflar kursi = `bfs` + `dfs`).
- Kurs ichidagi tartib: qiyinlik bo'yicha, keyin qo'shilgan tartibda.
- `Tag` qoladi, masalalar filtri uchun. Kursga ulanmagan teglar (`implementation`, `simulation`) oddiy teg bo'lib qoladi.
- Keyingi bosqichda (§7) o'chiriladi: `PlanSection`, `PlanItem`, `StudyPlan.in_quest`, `Tag.about_md`. Ularda faqat
  kontent bor, foydalanuvchi ma'lumoti yo'q (hech qaysi foydalanuvchi modeli ularga bog'lanmagan).
- `ProblemList` ("Ro'yxatlarim") o'zgarmaydi.

### 4.2 Promptdagi uchta savolga javobim

1. **Bitta masala bir nechta kursda bo'la oladimi?** Ha. Hozir ham shunday: `eng-uzun-osuvchi` masalasida
   `binary-search` va `dynamic-programming` teglari bor. Progress masala bo'yicha hisoblanadi, shuning uchun bir marta
   yechilgan masala ikkala kursda ham sanaladi.
2. **Kurs ichida bo'lim qoladimi?** Qo'lda tuzilgan bo'lim yo'q. Kurs sahifasida masalalar qiyinlik bo'yicha
   avtomatik guruhlanadi: Beginner, Easy, Medium, Hard. Guruhlar uchun mavjud `.ca-sec` qutilari ishlatiladi.
3. **Masalasi yo'q kurslar qanday ko'rinadi?** Ko'rinadi, nazariyasi ochiq, kartochkada "Tayyorlanmoqda" belgisi
   turadi. Bunday kurslar progressga, "Davom ettirish"ga va nishonga kirmaydi. Faqat nazariya uchun mo'ljallangan
   kursda (`complexity`) belgi "Nazariya" bo'ladi.

### 4.3 Daraja

`Advanced` o'rniga `Hard`. Shunda yangi daraja qiymati ham, yangi rang ham kerak bo'lmaydi, masalalar filtri
o'zgarmaydi. Agar 5 ta daraja muhim bo'lsa, kursga o'z darajalar ro'yxatini berish mumkin. Bu masalalarga ta'sir
qilmaydi, lekin dizaynga yangi rang qo'shiladi.

### 4.4 Interfeys

- **`/learn/`:** bosqichlar bo'yicha guruhlangan yo'l. Mavjud kurs kartochkasida tartib raqami, nom, daraja,
  masalalar soni va progress ko'rinadi.
- **"Davom ettirish":** foydalanuvchi eng oxirgi masala yechgan, hali tugallanmagan kurs. Bunday kurs bir nechta
  bo'lsa, tartibda birinchisi olinadi. Bunday kurs yo'q bo'lsa, tartibdagi birinchi tugallanmagan va masalasi bor
  kurs olinadi. Keyingi masala — o'sha kursdagi birinchi yechilmagan masala.
- **`/learn/<slug>/`:** kurs sahifasi. Tepada "Nazariya", pastda qiyinlik guruhlari bilan "Masalalar". Mavjud hero,
  halqa va nishon bloklari qayta ishlatiladi.
- **"Qo'llanma" tabi** olib tashlanadi.
- **Ctrl K:** kurs nomi va nazariya matni bo'yicha ham qidiradi. Buning uchun `learn` ilovasida alohida endpoint
  qilinadi, `apps/problems/views.py` ga tegilmaydi. 38 ta qator uchun oddiy `icontains` yetadi.
- **Staff:** sayt ichida kurs formasi (`plan_form` o'rnida). Unda nom, slug, bosqich, tartib, daraja, tavsif,
  nazariya va teglar bo'ladi. Teg formasidan nazariya maydoni olib tashlanadi.
- **Masala sahifasi:** kurs navigatsiyasi (oldingi/keyingi) yangi kurslar bilan ishlaydi.
- **Profil:** kurs nishonlari yangi kurslardan hisoblanadi. Ko'nikmalar xaritasi teglardan olinadi, shuning uchun
  qayta teglashdan keyin u yangi teg nomlarini ko'rsatadi.

### 4.5 URL

- Kurs manzili: `/learn/<slug>/`. Band nomlar (`lists`, `topics`, `plans`, `save`, `search`) slug sifatida
  taqiqlanadi. Bu forma va buyruqda tekshiriladi. 8-kurs slugi `lists` emas, `arrays` bo'ladi.
- Eski URL lar §6 dagi jadval bo'yicha yo'naltiriladi. Avval 302, moslik barqarorlashgach 301. Sababi: 301
  brauzerda abadiy keshlanadi, keyin xatoni tuzatib bo'lmaydi.

## 5. Kurslar ro'yxati (taklif)

Asl 38 talik ro'yxatdan farqi: 5 ta dasturlash kursi birlashtirildi yoki keyinga surildi, 5 ta SQL kursi qo'shildi.
"Masala" ustuni prod teglaridan olingan taxmin, qayta teglashdan (§5.1) keyingi holat uchun.
Birlashtirilgan kurslarning slugi kelajakka mo'ljallangan (`dp-intro`, `graph-traversal`): masala ko'paygach kurs
ajratilsa, eski manzil o'zgarmaydi.

| № | slug | Kurs | Daraja | Manba teglar | Masala | O'zgarish |
|---|---|---|---|---|---|---|
| | **Asoslar** | | | | | |
| 1 | `input-output` | Kiritish va chiqarish | Beginner | input-output | 21 | |
| 2 | `arithmetic` | Arifmetika | Beginner | arithmetic (yangi) | `math` ning 54 tasidan | `math` ikkiga bo'linadi |
| 3 | `conditionals` | Shartlar | Beginner | conditionals | 52 | |
| 4 | `for-loop` | `for` sikli | Beginner | for-loop (yangi) | `loops` ning 50 tasidan | `loops` ikkiga bo'linadi |
| 5 | `while-loop` | `while` sikli | Easy | while-loop (yangi) | `loops` ning 50 tasidan | |
| 6 | `nested-loops` | Ichma-ich sikllar | Easy | nested-loops (yangi) | `loops` ichidan | |
| 7 | `number-basics` | Sonlar bilan ishlash | Easy | number-basics (yangi) | `math` ning 54 tasidan | |
| | **Python vositalari** | | | | | bosqich nomi o'zgardi |
| 8 | `arrays` | Ro'yxatlar | Easy | arrays | 16 | slug `lists` → `arrays` |
| 9 | `strings` | Satrlar | Easy | strings | 25 | |
| 10 | `matrices` | Matritsalar | Easy | matrices (yangi) | 0 | |
| 11 | `dictionaries` | Lug'at va to'plam | Easy | hash-table | 14 | `tuples-sets` qo'shildi |
| 12 | `functions` | Funksiyalar va rekursiya | Medium | recursion | 0 | `recursion` qo'shildi |
| | **Algoritmlar** | | | | | |
| 13 | `complexity` | Murakkablik | Medium | complexity | — | faqat nazariya |
| 14 | `sorting` | Saralash | Medium | sorting, divide-and-conquer | 5 | |
| 15 | `binary-search` | Ikkilik qidirish | Medium | binary-search | 3 | |
| | **Texnikalar** | | | | | |
| 16 | `prefix-sums` | Prefiks yig'indilar | Medium | prefix-sums | 2 | |
| 17 | `two-pointers` | Ikki ko'rsatkich | Medium | two-pointers | 5 | |
| 18 | `sliding-window` | Sirpanuvchi oyna | Medium | sliding-window | 1 | |
| 19 | `greedy` | Ochko'z algoritmlar | Medium | greedy | 2 | |
| 20 | `bit-manipulation` | Bit amallari | Medium | bit-manipulation | 2 | |
| 21 | `backtracking` | To'liq qidiruv va backtracking | Hard | backtracking, brute-force | 0 | |
| | **Ma'lumot tuzilmalari** | | | | | stek va uyum shu yerga ko'chdi |
| 22 | `stack-queue` | Stek va navbat | Medium | stack, queue | 1 | |
| 23 | `heap` | Ustuvor navbat | Medium | heap | 0 | |
| | **Matematika** | | | | | |
| 24 | `number-theory` | Sonlar nazariyasi | Hard | number-theory | 0 | |
| 25 | `combinatorics` | Kombinatorika | Hard | combinatorics | 2 | |
| | **Dinamik dasturlash** | | | | | |
| 26 | `dp-intro` | Dinamik dasturlash | Hard | dynamic-programming | 3 | `dp-classic` 10+ masaladan keyin ajratiladi |
| | **Graflar** | | | | | |
| 27 | `graph-traversal` | Graflar: DFS va BFS | Hard | bfs, dfs | 1 | topologik saralash shu kurs ichida |
| 28 | `shortest-paths` | Eng qisqa yo'llar | Hard | shortest-paths | 1 | |
| 29 | `dsu-mst` | DSU va karkas daraxt | Hard | union-find | 1 | |
| 30 | `trees` | Daraxtlar | Hard | trees | 0 | |
| | **Ilg'or** | | | | | |
| 31 | `range-queries` | Oraliq so'rovlar | Hard | segment-tree | 1 | |
| 32 | `string-algorithms` | Satr algoritmlari | Hard | string-algorithms (yangi) | 0 | |
| 33 | `geometry` | Geometriya | Hard | geometry | 1 | |
| — | `game-theory` | O'yinlar nazariyasi | — | — | — | masala paydo bo'lganda qo'shiladi |
| | **SQL** | | | | | yangi bosqich |
| 34 | `sql-select` | SELECT va WHERE | Beginner | select, where, distinct, like, null-values | 9 | |
| 35 | `sql-sorting` | Saralash va ifodalar | Beginner | order-by, limit, case-when, string-functions | 5 | |
| 36 | `sql-grouping` | Guruhlash | Easy | aggregation, group-by, having, date-functions | 10 | |
| 37 | `sql-join` | JOIN | Medium | join, left-join | 8 | |
| 38 | `sql-advanced` | Ichki so'rov va oyna funksiyalari | Hard | subquery, window-functions | 5 | |

Natija: 7 ta kursda 0 masala (ularga qo'shimcha `complexity` — faqat nazariya), 13 ta kursda 1–3 tadan masala. Yo'l shunga moslab ko'rsatiladi (§4.2, 3-savol).

**Yangi nazariya kerak** (~7 ta maqola): `for` sikli, `while` sikli, ichma-ich sikllar, sonlar asoslari, matritsalar,
funksiyalar, satr algoritmlari. Bundan tashqari, graflar kursiga topologik saralash bo'limi qo'shiladi.
Qolgan kurslarning nazariyasi mavjud 54 ta matndan yig'iladi:

- `brute-force` → `backtracking`
- `divide-and-conquer` → `sorting`
- `linked-list` → `stack-queue` (ilova sifatida)
- `implementation` → `complexity` ("Ehtiyotkor bajarish" bo'limi)
- 18 ta SQL matni → 5 ta SQL kursi

### 5.1 Qayta teglash

Bu masalalarning teglarini o'zgartiradi, shuning uchun sizning ruxsatingiz kerak. Promptdagi "masalalarga tegma"
cheklovi bunga zid.

| Hozir | Nima bo'ladi | Masalalar |
|---|---|---|
| `loops` | `for-loop` yoki `while-loop` bilan almashtiriladi, kerak bo'lsa `nested-loops` qo'shiladi. Qoida: takrorlar soni oldindan ma'lum bo'lsa `for`; shart bilan takrorlansa ("raqamlarni ajratish", "… bo'lguncha") `while` | 50 |
| `math` | `arithmetic` yoki `number-basics` bilan almashtiriladi. Qoida: bo'luvchi, tub son, EKUB/EKUK, sanoq sistemasi bo'lsa `number-basics`, qolgani `arithmetic` | 54 |
| `number-theory` | `qutilarga-teng-bolish-boluvchilar` (easy) → `number-basics` | 1 |
| `data-structures` | `qavslar-balansi` ga `stack`, `oraliq-minimumi` ga `segment-tree` qo'shiladi | 2 |
| `graphs` | `labirint` ga `bfs`, `shaharlar-yollari` ga `shortest-paths`, `yollar-tarmogi` ga `union-find` qo'shiladi | 3 |
| `two-pointers` | `eng-uzun-oraliq` ga `sliding-window` qo'shiladi | 1 |
| tegsiz | `older-than-21` (SQL) ga `where` qo'shiladi | 1 |

Qayta teglash buyruq bilan bajariladi. Masala → teglar jadvali repoda saqlanadi. `--dry-run` o'zgarishlarni
ko'rsatadi, teskari jadval bilan hammasi qaytariladi. `loops` va `math` dagi 104 ta masala bo'yicha jadvalni
ishga tushirishdan oldin sizga ko'rsataman.

## 6. Eski URL → yangi (redirect jadvali)

**Qo'llanma** (`/learn/topics/<nom>/`, 54 ta):

| Eski nom | Yangi kurs |
|---|---|
| input-output | `input-output` |
| math | `arithmetic` |
| conditionals | `conditionals` |
| loops | `for-loop` |
| arrays | `arrays` |
| strings | `strings` |
| hash-table | `dictionaries` |
| recursion | `functions` |
| complexity | `complexity` |
| implementation | `/problems/?tag=implementation` (teg bo'lib qoladi) |
| sorting, divide-and-conquer | `sorting` |
| binary-search | `binary-search` |
| prefix-sums | `prefix-sums` |
| two-pointers | `two-pointers` |
| sliding-window | `sliding-window` |
| greedy | `greedy` |
| bit-manipulation | `bit-manipulation` |
| backtracking, brute-force | `backtracking` |
| stack, queue, data-structures, linked-list | `stack-queue` |
| heap | `heap` |
| number-theory | `number-theory` |
| combinatorics | `combinatorics` |
| geometry | `geometry` |
| dynamic-programming | `dp-intro` |
| graphs, bfs, dfs | `graph-traversal` |
| shortest-paths | `shortest-paths` |
| union-find | `dsu-mst` |
| trees | `trees` |
| segment-tree | `range-queries` |
| select, where, distinct, like, null-values, sql | `sql-select` |
| order-by, limit, case-when, string-functions | `sql-sorting` |
| aggregation, group-by, having, date-functions | `sql-grouping` |
| join, left-join | `sql-join` |
| subquery, window-functions | `sql-advanced` |

`/learn/topics/` → `/learn/`. Jadvalda yo'q nom → 404 (redirect emas).

**Eski kurslar** (`/learn/plans/<slug>/`):

| Eski kurs | Yangi kurs |
|---|---|
| birinchi-qadam | `input-output` |
| massiv-va-satrlar | `arrays` |
| algoritmlarga-kirish | `complexity` |
| malumotlar-tuzilmalari | `stack-queue` |
| rekursiya-va-qidiruv | `functions` |
| graflar | `graph-traversal` |
| dinamik-dasturlash | `dp-intro` |
| matematika-va-sonlar | `number-basics` |
| musobaqaga-tayyorgarlik | `complexity` |
| sql-asoslari | `sql-select` |

## 7. Migratsiya va xavfsizlik

Ish uch qadamda boradi: avval kengaytirish, keyin ko'chirish, eng oxirida eskisini o'chirish.

1. **Sxema migratsiyasi** (qaytariladi): kursga `stage`, `theory_md` va `tags` qo'shiladi. Eski jadvallar va
   `Tag.about_md` hali o'chirilmaydi, shuning uchun eski kodga qaytish mumkin.
2. **Kontent buyrug'i** (`add_study_plans` o'rnida, qayta ishga tushirsa bo'ladi): 38 ta kursni slug bo'yicha
   yaratadi yoki yangilaydi. Nazariya repodagi matnlardan olinadi; prodda staff tahrirlari yo'qligi tekshirilgan.
   Kontent migratsiya ichiga yozilmaydi.
3. **Qayta teglash buyrug'i** (§5.1).
4. **Eskisini o'chirish** (keyingi deploy, tekshiruvdan keyin): `PlanSection`, `PlanItem`, `in_quest`,
   `Tag.about_md` o'chiriladi.

Prodda:

- Deploydan oldin `pg_dump` olinadi.
- Prod nusxasidagi tekshiruv **VPS ichida**, vaqtinchalik bazada o'tkaziladi. Foydalanuvchi ma'lumoti noutbukka
  ko'chirilmaydi. Tartib: migrate, buyruqlar, keyin invariantlar tekshiriladi. Invariantlar: `UserProblemSolved`
  soni, har bir foydalanuvchining yechgan masalalari, reyting va ballar oldin va keyin bir xil bo'lishi kerak.
- Toza baza testlarda tekshiriladi: `migrate`, `seed`, keyin buyruqlar.

## 8. Ish tartibi (commitlar)

0. Sizning commit qilinmagan o'zgarishlaringiz (`apps/problems/*`, `apps/submissions/models.py`,
   `apps/integrity/urls.py`, `config/settings/prod.py`) commit yoki stash qilinadi. Aks holda Ctrl K va teg ishlari
   ular bilan to'qnashadi.
1. Model, sxema migratsiyasi va testlar.
2. Qayta teglash jadvali: avval sizga ko'rsatiladi, keyin buyruq yoziladi.
3. Kurslar buyrug'i va yangi nazariya matnlari.
4. View, URL va redirectlar, testlar bilan.
5. Shablonlar (bosqichlar bo'yicha yo'l, kurs sahifasi) va CSS build.
6. Ctrl K qidiruvi va staff uchun kurs formasi.
7. Prod: `pg_dump`, VPS ichida tekshiruv, deploy, buyruqlar, smoke-test.
8. Keyingi deploy: eski jadval va maydonlarni o'chirish.

## 9. Xavflar

- **`loops` va `math` ni bo'lish sub'ektiv.** Bu 104 ta masala bo'yicha qaror. Jadvalni siz ko'rib chiqasiz.
- **Katta kurslar.** "Shartlar" 52 ta masala, "Arifmetika" `math` ning katta qismi. Sahifa uzun bo'ladi, qiyinlik
  guruhlari yordam beradi. Bunday kursni tugatib nishon olish ham qiyinlashadi.
- **Yo'l bo'sh ko'rinishi mumkin.** 38 kursdan 21 tasida 0–3 tadan masala bor. Yangi tuzilma bu kamchilikni ochiq
  ko'rsatadi, lekin hal qilmaydi. Keyingi ish: 10–33-kurslar uchun masala yozish, ayniqsa medium va hard
  (hozir jami 23 ta).
- **Bugungi 6 ta kurs** yangi kurslar bilan almashadi. Ularning nazariya matnlari qayta ishlatiladi, hech narsa
  yo'qolmaydi.
- **301 keshi:** shuning uchun avval 302 ishlatiladi.

## 10. Sizdan kerak bo'lgan qarorlar

| # | Savol | Tavsiyam |
|---|---|---|
| 1 | Kursga masala qanday kiradi? | Teg orqali |
| 2 | Bitta masala bir nechta kursda bo'la oladimi? | Ha |
| 3 | Kurs ichida bo'limlar bo'ladimi? | Qiyinlik guruhlari; qo'lda tuzilgan bo'lim yo'q |
| 4 | Masalasi yo'q kurslar qanday ko'rinadi? | Ko'rinadi, "Tayyorlanmoqda" belgisi bilan, progressga kirmaydi |
| 5 | SQL nima bo'ladi? | Alohida bosqich, 5 ta kurs |
| 6 | `Advanced` darajasi? | `Hard` ga birlashtiriladi |
| 7 | Kurs URL i? | `/learn/<slug>/`, band nomlar taqiqlanadi, `lists` → `arrays` |
| 8 | §5 dagi birlashtirishlar | Har biri bo'yicha ha yoki yo'q |
| 9 | `loops`/`math` ni bo'lish uchun masala teglarini o'zgartirishga ruxsat bormi? | Ha, jadval sizga ko'rsatilgandan keyin |
| 10 | Model nomi `StudyPlan` → `Course`? | Ixtiyoriy; foydalanuvchiga ko'rinmaydi |
| 11 | Commit qilinmagan o'zgarishlaringiz nima bo'ladi? | Avval commit yoki stash |
