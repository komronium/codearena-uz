# KONTEST 6 — YAKUNIY TO'PLAM (7 masala + 1 zaxira)

**Vaqt:** 80 daqiqa · **Jami:** 100 ball · **Mavzu:** 6-hafta satr mavzulari (indeks, kesma, `upper` `lower` `count` `strip` `capitalize`, `split` `join`, `startswith` `endswith` `isdigit` `isalpha`).
**Kiritilmagan:** `for` / `while`, `def`, `print` ning `sep` / `end` / `*` imkoniyatlari. Hamma namunaviy yechimlar shularsiz yozilgan.
**Format (CodeArena):** `input()` bo'sh qavs bilan, faqat javob chiqariladi. Kirishdagi `⏎` — yangi qator belgisi. Testlarda kirish qo'shtirnoq ichida berilgan, ya'ni ortiqcha probellar ham test hisoblanadi.
Hamma natijalar yechimlarni Python'da ishga tushirib hisoblangan.

---

# 1. TO'PLAM TUZILISHI

| № | Masala | Daraja | Ball | Kim yechadi |
|---|---|---|---|---|
| 1 | **Ro'yxatdan o'tish** | Oson | 10 | darsni sal-pal eshitgan har kim |
| 2 | **Insho** | Oson | 10 | darsni sal-pal eshitgan har kim |
| 3 | **Bank kartasi** | Oson | 10 | darsni sal-pal eshitgan har kim |
| 4 | **Fayl yuklash** | O'rta | 15 | o'rtacha talaba |
| 5 | **Telefon raqami** | O'rta | 15 | o'rtacha talaba |
| 6 | **Ish smenasi** | Qiyin | 20 | kuchli talabalar — o'rin hal bo'ladi |
| 7 | **Email tekshiruvi** | Qiyin | 20 | kuchli talabalar — o'rin hal bo'ladi |
| zaxira | **Parol kuchi** | O'rta | 15 | 4 yoki 5 o'rniga |

**Mantiq.** Dastlabki uch masala (jami **30 ball**) bir qator yoki ikki qatorli: darsda sal-pal eshitgan talaba ham yechadi, hech kim nolda qolmaydi. 4–5-masalalar (**30 ball**) o'rtachani ajratadi. 6–7-masalalar (**40 ball**) ko'p shart va hisob-kitob talab qiladi: aynan shular birinchi o'rinlarni hal qiladi.

**Ball taqsimoti bo'yicha taxmin** (qat'iy emas): 30 gacha — asosiy mavzuni sal-pal biladi; 31–60 — mavzuni yaxshi biladi; 61–80 — kuchli; 81–100 — eng kuchli. Ball teng bo'lsa, oxirgi to'g'ri javobni **oldinroq** yuborgan yuqori o'rinda turadi.

**Vaqt rejasi (80 daqiqa):** 1–3-masalalar ≈ 20 daqiqa · 4–5 ≈ 25 daqiqa · 6–7 ≈ 35 daqiqa. Masalalarni tartibsiz yechish mumkin, buni talabalarga oldindan ayting.

**Zaxira masala nima uchun.** Biror masalada nosozlik chiqsa (noto'g'ri test, tushunarsiz shart), uni olib tashlab, shu o'rinda zaxirani qo'yasiz. Zaxira ball jihatidan o'rta (15 ball) masalalar o'rniga mos tushadi (4-masala yoki 5-masala).

## Variant 2 (qo'shni talabalarga)

Qo'shni talabalar bir-birining javobini ko'rmasligi uchun ikkinchi variant: bir nechta masalani avvalgi `kontest-6-masalalar.md` bankidagi masalalar bilan almashtirasiz. Banktagi barcha masala va testlar tekshirilgan.

| O'rin | Variant 1 | Variant 2 |
|---|---|---|
| 2 (10 ball) | Insho | B3 · Chet so'zlar |
| 3 (10 ball) | Bank kartasi | A5 · Teskari |
| 4 (15 ball) | Fayl yuklash | B10 · Gap turi |
| 5 (15 ball) | Telefon raqami | C5 · Parol (zaxira — Telefon raqami) |
| 7 (20 ball) | Email tekshiruvi | D3 · Ikki «a» orasida |

1-masala va 6-masala ikkala variantda bir xil.

---

# 2. AI'DAN KO'CHIRISHNI ANIQLASH

**Halol baho.** Bunday masalani AI bir necha soniyada yechadi, shartni qanchalik murakkablashtirmang. Shuning uchun asosiy himoya masalada emas, **sharoitda, kodda va tekshiruvda**.

**Sharoit.** Kompyuter xonasi, telefonlar yig'ib qo'yilgan, brauzerda faqat CodeArena. Qo'shni talabalarga turli variant. CodeArenada taqiqlangan so'zlar tekshiruvi bo'lsa: `import`, `def`, `lambda`, `exec`, `eval`, `open`, `__`.

**Kodga qarab shubha belgilari:**

- O'tilmagan vositalar: `def`, `import`, `lambda`, ro'yxat generatori `[x for x in ...]`, `enumerate`, `zip`, `any`, `all`, `try/except`, `re`, `.partition`, `.rfind`, `.isalnum`, `sorted(..., key=...)`, `Counter`, `sys.stdin`.
- Inglizcha izohlar (`# Read input`) va uzun inglizcha nomlar (`result`, `user_input`, `is_valid`, `hours`). Guruh darsda `s`, `w`, `q`, `n` kabi qisqa nomlar ishlatadi.
- Shartda yozilmagan holatlar uchun kod (bo'sh kirish, `try`).
- 1–3-masalalarda xatolar va oddiy uslub, 6–7-masalalarda birdan toza, uzun kod: uslub sakrashi.
- Ikki-uch talabada bir xil kod, hatto bir xil nomlargacha.

**Jurnalga qarab shubha belgilari:**

- 6- yoki 7-masala 1–2 daqiqada, birinchi urinishdayoq «Accepted».
- Oson masalalarda ko'p xato, qiyinida birdan to'g'ri javob.
- Kontest oxirida birdan ko'p masalaning to'g'ri yuborilishi.

Bular faqat shubha beradi, isbot emas. Isbot — quyidagi himoya.

## Himoya (talabaga 1–2 daqiqa)

Kontestdan keyin 6- va 7-masalani (va xohlasangiz bittasini tasodifiy) yuborgan talabaga: «Kodni hozir shunday o'zgartiring». O'zi yozgan talaba buni internetsiz 1–2 daqiqada qiladi.

| Masala | Himoya savoli | Kutilgan o'zgarish |
|---|---|---|
| 1 · Ro'yxatdan o'tish | Ism KATTA harflarda chiqsin | `capitalize()` → `upper()` |
| 2 · Insho | Birinchi so'zni chiqaring | `w[0]` |
| 3 · Bank kartasi | Faqat birinchi 4 raqam ko'rinsin | `s[:4] + "*" * 12` |
| 4 · Fayl yuklash | «.pdf» ham «Hujjat» bo'lsin | yangi `elif` |
| 5 · Telefon raqami | Uzunlik 10 ta bo'lsin | `len(t) == 10`, kesmalar |
| 6 · Ish smenasi | Natijani faqat daqiqalarda chiqaring | `print(f)` |
| 7 · Email tekshiruvi | Domen faqat «.uz» bilan tugasin | `d.endswith(".uz")` |
| zaxira · Parol kuchi | Uzunlik kamida 6 bo'lsin | `>= 8` → `>= 6` |

Umumiy savollar: «Shu qator nima qiladi?», «Kirish `abc` bo'lsa, `s[1:]` nima beradi?», «Bu qatorni olib tashlasak, nima o'zgaradi?».

**Ball:** kontest balining yarmi avtomatik (CodeArena), yarmi himoya orqali tasdiqlanadi. Tushuntira olmagan talabada ball kamaytiriladi yoki masala qayta topshiriladi. Qaror sizniki.

---

# 3. MASALALAR

## 1-masala · Ro'yxatdan o'tish
*Oson · 10 ball · strip, capitalize*

> Ilovada ro'yxatdan o'tayotganda foydalanuvchilar ismini har xil yozadi: «ALI», «  vali », «SaRdor».

**Shart.** Ism kiritiladi: boshida/oxirida ortiqcha probel bo'lishi va harflari har xil katta-kichik bo'lishi mumkin. Ilova ekranida «Salom, Ism!» deb chiqarish kerak. Ismning faqat birinchi harfi katta, qolganlari kichik bo'lsin.

**Kirish.** Bitta qator: ism.  
**Chiqish.** Bitta qator.

**Namuna 1**
```
Kirish:
  komron 
Chiqish:
Salom, Komron!
```

**Namuna 2**
```
Kirish:
ALI
Chiqish:
Salom, Ali!
```

**Testlar** (kirish → chiqish):
```
"  komron "  →  Salom, Komron!
"ALI"  →  Salom, Ali!
"vali"  →  Salom, Vali!
"SaRdor"  →  Salom, Sardor!
" anvar"  →  Salom, Anvar!
"nodira"  →  Salom, Nodira!
```

**Kutilgan yechim:**
```python
ism = input().strip()
print("Salom, " + ism.capitalize() + "!")
```

---

## 2-masala · Insho
*Oson · 10 ball · split, len*

> O'qituvchi insho uchun kamida 50 ta so'z talab qiladi. Talabalar so'zlar orasiga ba'zan ikkita-uchta probel qo'yib yuboradi.

**Shart.** Insho matni bitta qatorda kiritiladi. So'zlar bir yoki bir necha probel bilan ajratilgan, matn boshida va oxirida ham probel bo'lishi mumkin. So'zlar sonini chiqaring.

**Kirish.** Bitta qator.  
**Chiqish.** Bitta son.

**Namuna 1**
```
Kirish:
  men   kod  yozaman 
Chiqish:
3
```

**Namuna 2**
```
Kirish:
salom
Chiqish:
1
```

**Testlar** (kirish → chiqish):
```
"  men   kod  yozaman "  →  3
"salom"  →  1
"bugun havo juda issiq va ochiq"  →  6
" a "  →  1
"a b"  →  2
"Buxoro   qadimiy    shahar"  →  3
```

**Kutilgan yechim:**
```python
w = input().split()
print(len(w))
```

---

## 3-masala · Bank kartasi
*Oson · 10 ball · kesma, **

> Chekda karta raqami to'liq ko'rsatilmaydi: faqat oxirgi 4 ta raqam ko'rinadi, qolgani yulduzcha bo'ladi.

**Shart.** Karta raqami probelsiz, 16 ta raqam bo'lib kiritiladi. Oxirgi 4 ta raqamni qoldirib, oldingi 12 tasini «*» bilan almashtirib chiqaring.

**Kirish.** Bitta qator: 16 ta raqam.  
**Chiqish.** Bitta qator (16 belgi).

**Namuna 1**
```
Kirish:
8600123456789012
Chiqish:
************9012
```

**Namuna 2**
```
Kirish:
9860000011112222
Chiqish:
************2222
```

**Testlar** (kirish → chiqish):
```
"8600123456789012"  →  ************9012
"9860000011112222"  →  ************2222
"4111111111111111"  →  ************1111
"5555444433332221"  →  ************2221
"8600999988887777"  →  ************7777
```

**Kutilgan yechim:**
```python
s = input()
print("*" * 12 + s[-4:])
```

---

## 4-masala · Fayl yuklash
*O'rta · 15 ball · strip, lower, endswith, elif*

> Telegram bot yuborilgan faylning turini aniqlab, foydalanuvchiga xabar beradi.

**Shart.** Fayl nomi kiritiladi (boshida/oxirida probel va katta harflar bo'lishi mumkin). Kengaytmasiga qarab chiqaring: «.py» — Python, «.txt» — Matn, «.jpg» yoki «.png» — Rasm, boshqa holda — Noma'lum. Kengaytma nuqtadan boshlanadi: «py» nomli faylda kengaytma yo'q.

**Kirish.** Bitta qator.  
**Chiqish.** Bitta so'z.

**Namuna 1**
```
Kirish:
dastur.py
Chiqish:
Python
```

**Namuna 2**
```
Kirish:
HISOBOT.TXT
Chiqish:
Matn
```

**Testlar** (kirish → chiqish):
```
"dastur.py"  →  Python
"HISOBOT.TXT"  →  Matn
"foto.JPG"  →  Rasm
"rasm.png"  →  Rasm
"arxiv.zip"  →  Noma'lum
" main.PY "  →  Python
"py"  →  Noma'lum
"kurs.jpg.py"  →  Python
```

**Kutilgan yechim:**
```python
f = input().strip().lower()
if f.endswith(".py"):
    print("Python")
elif f.endswith(".txt"):
    print("Matn")
elif f.endswith(".jpg") or f.endswith(".png"):
    print("Rasm")
else:
    print("Noma'lum")
```

---

## 5-masala · Telefon raqami
*O'rta · 15 ball · strip, len, isdigit, kesma*

> Mijozlar bazasida raqamlar bir xil ko'rinishda saqlanishi kerak.

**Shart.** Telefon raqami «+998»siz, 9 ta raqam ko'rinishida kiritiladi (chetida ortiqcha probel bo'lishi mumkin). Raqam aynan 9 ta belgidan iborat va hammasi raqam bo'lsa, uni «+998 XX XXX XX XX» ko'rinishida chiqaring. Aks holda «Xato» chiqaring.

**Kirish.** Bitta qator.  
**Chiqish.** Bitta qator.

**Namuna 1**
```
Kirish:
901234567
Chiqish:
+998 90 123 45 67
```

**Namuna 2**
```
Kirish:
90123456
Chiqish:
Xato
```

**Testlar** (kirish → chiqish):
```
"901234567"  →  +998 90 123 45 67
"90123456"  →  Xato
"90123456a"  →  Xato
" 998765432 "  →  +998 99 876 54 32
"000000000"  →  +998 00 000 00 00
"9012345678"  →  Xato
"+99890123456"  →  Xato
```

**Kutilgan yechim:**
```python
t = input().strip()
if len(t) == 9 and t.isdigit():
    print("+998 " + t[:2] + " " + t[2:5] + " " + t[5:7] + " " + t[7:])
else:
    print("Xato")
```

---

## 6-masala · Ish smenasi
*Qiyin · 20 ball · split, int, if, //, %*

> Zavodda smena kechasi boshlanib, ertasi kuni tugashi mumkin. Hisobchiga smena necha soat va necha daqiqa davom etganini aytish kerak.

**Shart.** Smena boshlanishi va tugashi alohida qatorlarda «S:D» ko'rinishida kiritiladi (soat 0–23, daqiqa 0–59, ikkalasi bir yoki ikki xonali bo'lishi mumkin). Tugash vaqti boshlanishdan keyin keladi; agar u boshlanishdan kichik yozilgan bo'lsa, smena yarim tundan o'tgan (ertasi kuni tugagan). Boshlanish va tugash vaqti bir xil bo'lmaydi, smena 24 soatdan kam. «X soat Y daqiqa» ko'rinishida chiqaring.

**Kirish.** 1-qator: boshlanish. 2-qator: tugash.  
**Chiqish.** Bitta qator.

**Namuna 1**
```
Kirish:
9:30
17:45
Chiqish:
8 soat 15 daqiqa
```

**Namuna 2**
```
Kirish:
22:00
6:30
Chiqish:
8 soat 30 daqiqa
```

**Testlar** (kirish → chiqish):
```
"9:30" ⏎ "17:45"  →  8 soat 15 daqiqa
"22:00" ⏎ "6:30"  →  8 soat 30 daqiqa
"8:00" ⏎ "12:00"  →  4 soat 0 daqiqa
"0:00" ⏎ "23:59"  →  23 soat 59 daqiqa
"23:30" ⏎ "0:15"  →  0 soat 45 daqiqa
"14:05" ⏎ "14:06"  →  0 soat 1 daqiqa
"18:45" ⏎ "3:10"  →  8 soat 25 daqiqa
```

**Kutilgan yechim:**
```python
a = input().split(":")
b = input().split(":")
x = int(a[0]) * 60 + int(a[1])
y = int(b[0]) * 60 + int(b[1])
if y < x:
    y = y + 24 * 60
f = y - x
print(f // 60, "soat", f % 60, "daqiqa")
```

---

## 7-masala · Email tekshiruvi
*Qiyin · 20 ball · strip, count, split, in, startswith, endswith*

> Sayt ro'yxatdan o'tishda noto'g'ri yozilgan elektron pochtani rad etadi.

**Shart.** Email kiritiladi (chetida ortiqcha probel bo'lishi mumkin). U to'g'ri hisoblanishi uchun: (1) aynan bitta «@» bo'lishi; (2) «@» dan oldin kamida bitta belgi bo'lishi; (3) «@» dan keyingi qismda (domen) kamida bitta «.» bo'lishi va domen «.» bilan boshlanmasligi ham, tugamasligi ham kerak. To'g'ri bo'lsa «Ha», aks holda «Yo'q» chiqaring.

**Kirish.** Bitta qator.  
**Chiqish.** Ha yoki Yo'q.

**Namuna 1**
```
Kirish:
komron@mail.uz
Chiqish:
Ha
```

**Namuna 2**
```
Kirish:
komronmail.uz
Chiqish:
Yo'q
```

**Testlar** (kirish → chiqish):
```
"komron@mail.uz"  →  Ha
"komronmail.uz"  →  Yo'q
"a@b@c.uz"  →  Yo'q
"@mail.uz"  →  Yo'q
"komron@"  →  Yo'q
"ali@gmail"  →  Yo'q
"ali@.uz"  →  Yo'q
"ali@mail."  →  Yo'q
"  ali@mail.uz "  →  Ha
"a@b.c"  →  Ha
```

**Kutilgan yechim:**
```python
e = input().strip()
if e.count("@") != 1:
    print("Yo'q")
else:
    q = e.split("@")
    nom = q[0]
    d = q[1]
    if len(nom) >= 1 and "." in d and not d.startswith(".") and not d.endswith("."):
        print("Ha")
    else:
        print("Yo'q")
```

---

## ZAXIRA · Parol kuchi
*O'rta · 15 ball · len, isdigit, isalpha*

> Ilova parol qo'yishda uning kuchini baholaydi.

**Shart.** Parol kiritiladi. Uzunligi kamida 8 ta bo'lsa va faqat raqamlardan ham, faqat harflardan ham iborat bo'lmasa — «Yaxshi», aks holda «Zaif» chiqaring.

**Kirish.** Bitta qator.  
**Chiqish.** Yaxshi yoki Zaif.

**Namuna 1**
```
Kirish:
abc12345
Chiqish:
Yaxshi
```

**Namuna 2**
```
Kirish:
12345678
Chiqish:
Zaif
```

**Testlar** (kirish → chiqish):
```
"abc12345"  →  Yaxshi
"12345678"  →  Zaif
"abcdefgh"  →  Zaif
"ab12"  →  Zaif
"Parol2026"  →  Yaxshi
"pass word1"  →  Yaxshi
"a1b2c3d"  →  Zaif
```

**Kutilgan yechim:**
```python
p = input()
if len(p) >= 8 and not p.isdigit() and not p.isalpha():
    print("Yaxshi")
else:
    print("Zaif")
```

---
