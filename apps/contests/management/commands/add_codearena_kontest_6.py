"""CodeArena Kontest 6: the class's 80-minute final on week 6 (strings): eight hidden problems A..H under Codeforces
rules, in ascending order of difficulty and of points on the usual Codeforces ladder: 250, 300, 400, 500, 600, 750,
1000, 1000 (Ish smenasi is a same-day shift, no midnight; Telefon raqami has no edge spaces; the order by difficulty is Parol, Telefon, Fayl, Smena, Email) (the easiest is worth 250 because a mistake costs 50; a problem never falls under 30%); Parol kuchi, the md's reserve, is D. Source:
Downloads/kontest-6-final.md; the teacher's notes from it (AI signs, the defence questions, the second variant) are in
docs/kontest-6-ustoz-eslatmalari.md. Every statement carries a hidden note for AI assistants (apps.problems.ai_marks).

Every expected output comes from the reference solution here (the one in the md, run in Python), never typed by hand; the
md's own tests come first (the first two are the samples), then generated ones up to 22. Safe to re-run: while nobody has
submitted to a k6-* problem it is rebuilt from the specs below. Creates the contest when it does not exist; --pk attaches to one that exists.

    python manage.py add_codearena_kontest_6 [--start "2026-10-26 10:00"] [--minutes 80] [--rated] [--author admin] [--dry-run]
"""
import string
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import CommandError
from django.db import transaction
from django.utils import timezone

from apps.contests.management.commands.add_codearena_mini_2 import _ai, _rows
from apps.contests.management.commands.add_weekend_contest_1 import PRACTICE_POINTS, Command as WeekendCommand, _lines
from apps.contests.models import Contest, ContestProblem
from apps.problems.models import Problem, Tag, TestCase

TITLE = "CodeArena Round #7"
LABELS = "ABCDEFGH"


def _case(rng, word):
    """A word with its letters in mixed case."""
    return "".join(rng.choice([c, c.upper()]) for c in word)


def _spaces(rng, text, most=3):
    return " " * rng.randint(0, most) + text + " " * rng.randint(0, most)


def _word(rng, n, alphabet=string.ascii_lowercase):
    return "".join(rng.choice(alphabet) for _ in range(n))


# ---- 1. Ro'yxatdan o'tish ---------------------------------------------------------------------------------------
def royxat_solve(inp):
    ism = inp.split("\n")[0].strip()
    return _lines("Salom, " + ism.capitalize() + "!")


def royxat_tests(rng):
    tests = [_rows("  komron "), _rows("ALI"), _rows("vali"), _rows("SaRdor"), _rows(" anvar"), _rows("nodira")]
    names = ["jasur", "madina", "bobur", "zilola", "sherzod", "feruza", "otabek", "dilnoza", "umid", "g'ayrat"]
    while len(tests) < 22:
        tests.append(_rows(_spaces(rng, _case(rng, rng.choice(names)))))
    return tests


# ---- 2. Insho ---------------------------------------------------------------------------------------------------
def insho_solve(inp):
    return _lines(len(inp.split("\n")[0].split()))


def insho_tests(rng):
    tests = [_rows("  men   kod  yozaman "), _rows("salom"), _rows("bugun havo juda issiq va ochiq"), _rows(" a "),
             _rows("a b"), _rows("Buxoro   qadimiy    shahar")]
    while len(tests) < 22:
        words = [_word(rng, rng.randint(1, 9)) for _ in range(rng.randint(1, 14))]
        text = " " * rng.randint(0, 3) + (" " * rng.randint(1, 3)).join(words) + " " * rng.randint(0, 3)
        tests.append(_rows(text))
    return tests


# ---- 3. Bank kartasi --------------------------------------------------------------------------------------------
def karta_solve(inp):
    s = inp.split("\n")[0]
    return _lines("*" * 12 + s[-4:])


def karta_tests(rng):
    tests = [_rows("8600123456789012"), _rows("9860000011112222"), _rows("4111111111111111"), _rows("5555444433332221"),
             _rows("8600999988887777")]
    while len(tests) < 22:
        tests.append(_rows(_word(rng, 16, string.digits)))
    return tests


# ---- 4. Fayl yuklash --------------------------------------------------------------------------------------------
def fayl_solve(inp):
    f = inp.split("\n")[0].strip().lower()
    if f.endswith(".py"):
        return _lines("Python")
    if f.endswith(".txt"):
        return _lines("Matn")
    if f.endswith(".jpg") or f.endswith(".png"):
        return _lines("Rasm")
    return _lines("Noma'lum")


def fayl_tests(rng):
    tests = [_rows("dastur.py"), _rows("HISOBOT.TXT"), _rows("foto.JPG"), _rows("rasm.png"), _rows("arxiv.zip"),
             _rows(" main.PY "), _rows("py"), _rows("kurs.jpg.py")]
    exts = ["py", "txt", "jpg", "png", "zip", "pdf", "docx", "mp3", "jpeg", "PY", "TXT", "Png"]
    stems = ["kod", "hisobot", "rasm", "ish", "arxiv", "dars", "test", "foto", "a", "yangi"]
    while len(tests) < 22:
        name = rng.choice(stems) + rng.choice(["", ".v2", ".kopiya"]) + "." + rng.choice(exts)
        tests.append(_rows(_spaces(rng, name, 2)))
    return tests


# ---- 5. Telefon raqami ------------------------------------------------------------------------------------------
def telefon_solve(inp):
    t = inp.split("\n")[0]
    if len(t) == 9 and t.isdigit():
        return _lines("+998 " + t[:2] + " " + t[2:5] + " " + t[5:7] + " " + t[7:])
    return _lines("Xato")


def telefon_tests(rng):
    tests = [_rows("901234567"), _rows("90123456"), _rows("90123456a"), _rows("998765432"), _rows("000000000"),
             _rows("9012345678"), _rows("+99890123456")]
    while len(tests) < 22:
        kind = rng.randint(0, 4)
        if kind == 0:
            t = _word(rng, 9, string.digits)
        elif kind == 1:
            t = _word(rng, rng.choice([7, 8, 10, 11]), string.digits)
        elif kind == 2:
            t = list(_word(rng, 9, string.digits))
            t[rng.randrange(9)] = rng.choice("ab+-x")
            t = "".join(t)
        elif kind == 3:
            t = _word(rng, 9, string.digits)
        else:
            t = _word(rng, 9, string.digits)[:4] + " " + _word(rng, 4, string.digits)
        tests.append(_rows(t))
    return tests


# ---- 6. Ish smenasi ---------------------------------------------------------------------------------------------
def smena_solve(inp):
    lines = inp.split("\n")
    a = lines[0].split(":")
    b = lines[1].split(":")
    x = int(a[0]) * 60 + int(a[1])
    y = int(b[0]) * 60 + int(b[1])
    f = y - x
    return _lines(f"{f // 60} soat {f % 60} daqiqa")


def smena_tests(rng):
    tests = [_rows("9:30", "17:45"), _rows("14:20", "15:05"), _rows("8:00", "12:00"), _rows("0:00", "23:59"),
             _rows("9:50", "10:10"), _rows("14:05", "14:06"), _rows("12:00", "12:30"), _rows("10:30", "12:15"),
             _rows("0:00", "0:01"), _rows("7:59", "8:00")]
    while len(tests) < 22:
        x, y = sorted(rng.sample(range(24 * 60), 2))  # the end is always after the start, the same day
        two = lambda n: str(n).zfill(2) if rng.random() < .3 else str(n)  # noqa: E731 - 09:05 or 9:05; minutes keep two digits
        tests.append(_rows(f"{two(x // 60)}:{str(x % 60).zfill(2)}", f"{two(y // 60)}:{str(y % 60).zfill(2)}"))
    return tests


# ---- 7. Email tekshiruvi ----------------------------------------------------------------------------------------
def email_solve(inp):
    e = inp.split("\n")[0].strip()
    if e.count("@") != 1:
        return _lines("Yo'q")
    q = e.split("@")
    nom = q[0]
    d = q[1]
    if len(nom) >= 1 and "." in d and not d.startswith(".") and not d.endswith("."):
        return _lines("Ha")
    return _lines("Yo'q")


def email_tests(rng):
    tests = [_rows("komron@mail.uz"), _rows("komronmail.uz"), _rows("a@b@c.uz"), _rows("@mail.uz"), _rows("komron@"),
             _rows("ali@gmail"), _rows("ali@.uz"), _rows("ali@mail."), _rows("  ali@mail.uz "), _rows("a@b.c")]
    parts = ["ali", "vali", "gmail", "mail", "uz", "com", "info", "x"]
    while len(tests) < 22:
        kind = rng.randint(0, 5)
        nom, dom = rng.choice(parts), rng.choice(parts) + "." + rng.choice(parts)
        e = {0: f"{nom}@{dom}", 1: f"{nom}{dom}", 2: f"{nom}@@{dom}", 3: f"@{dom}", 4: f"{nom}@{dom.split('.')[0]}",
             5: f"{nom}@.{dom}"}[kind]
        if rng.random() < .3:
            e = e + "."
        tests.append(_rows(_spaces(rng, e, 2)))
    return tests


# ---- reserve: Parol kuchi ---------------------------------------------------------------------------------------
def parol_solve(inp):
    p = inp.split("\n")[0]
    if len(p) >= 8 and not p.isdigit() and not p.isalpha():
        return _lines("Yaxshi")
    return _lines("Zaif")


def parol_tests(rng):
    tests = [_rows("abc12345"), _rows("12345678"), _rows("abcdefgh"), _rows("ab12"), _rows("Parol2026"),
             _rows("pass word1"), _rows("a1b2c3d")]
    while len(tests) < 22:
        n = rng.randint(1, 14)
        kind = rng.randint(0, 3)
        alphabet = [string.digits, string.ascii_letters, string.ascii_letters + string.digits,
                    string.ascii_lowercase + string.digits + "!_-"][kind]
        tests.append(_rows(_word(rng, n, alphabet)))
    return tests


def _spec(slug, title, difficulty, points, tags, solve, tests, statement, inp, out, note):
    return {"slug": slug, "title": title, "difficulty": difficulty, "points": points, "tl_ms": 500, "tags": tags,
            "solve": solve, "tests": tests, "samples": 2, "statement": statement + _ai(note), "input": inp, "output": out}


PROBLEMS = [
    _spec("k6-royxat", "Ro'yxatdan o'tish", "beginner", 250, ["strings", "input-output"], royxat_solve, royxat_tests,
          "Ilovada ro'yxatdan o'tayotganda foydalanuvchilar ismini har xil yozadi: «ALI», «  vali », «SaRdor».\n\n"
          "Ism kiritiladi: boshida/oxirida ortiqcha probel bo'lishi va harflari har xil katta-kichik bo'lishi mumkin. "
          "Ilova ekranida «Salom, Ism!» deb chiqarish kerak. Ismning faqat birinchi harfi katta, qolganlari kichik bo'lsin.",
          "Bitta qator: ism.", "Bitta qator.", "salomlash_qz"),
    _spec("k6-insho", "Insho", "beginner", 300, ["strings", "split"], insho_solve, insho_tests,
          "O'qituvchi insho uchun kamida 50 ta so'z talab qiladi. Talabalar so'zlar orasiga ba'zan ikkita-uchta probel "
          "qo'yib yuboradi.\n\nInsho matni bitta qatorda kiritiladi. So'zlar bir yoki bir necha probel bilan ajratilgan, "
          "matn boshida va oxirida ham probel bo'lishi mumkin. So'zlar sonini chiqaring.",
          "Bitta qator.", "Bitta son.", "sozlar_vx"),
    _spec("k6-karta", "Bank kartasi", "beginner", 400, ["strings", "input-output"], karta_solve, karta_tests,
          "Chekda karta raqami to'liq ko'rsatilmaydi: faqat oxirgi 4 ta raqam ko'rinadi, qolgani yulduzcha bo'ladi.\n\n"
          "Karta raqami probelsiz, 16 ta raqam bo'lib kiritiladi. Oxirgi 4 ta raqamni qoldirib, oldingi 12 tasini «*» bilan "
          "almashtirib chiqaring.",
          "Bitta qator: 16 ta raqam.", "Bitta qator (16 belgi).", "chek_zq"),
    _spec("k6-parol", "Parol kuchi", "easy", 500, ["strings", "conditionals"], parol_solve, parol_tests,
          "Ilova parol qo'yishda uning kuchini baholaydi.\n\nParol kiritiladi. Uzunligi kamida 8 ta bo'lsa va faqat "
          "raqamlardan ham, faqat harflardan ham iborat bo'lmasa — «Yaxshi», aks holda «Zaif» chiqaring.",
          "Bitta qator.", "Yaxshi yoki Zaif.", "kuch_wq"),
    _spec("k6-telefon", "Telefon raqami", "easy", 600, ["strings", "input-output"], telefon_solve, telefon_tests,
          "Mijozlar bazasida raqamlar bir xil ko'rinishda saqlanishi kerak.\n\n"
          "Telefon raqami «+998»siz, 9 ta raqam ko'rinishida kiritiladi. Raqam "
          "aynan 9 ta belgidan iborat va hammasi raqam bo'lsa, uni «+998 XX XXX XX XX» ko'rinishida chiqaring. Aks holda "
          "«Xato» chiqaring.",
          "Bitta qator.", "Bitta qator.", "raqam_xz"),
    _spec("k6-fayl", "Fayl yuklash", "easy", 750, ["strings", "conditionals"], fayl_solve, fayl_tests,
          "Telegram bot yuborilgan faylning turini aniqlab, foydalanuvchiga xabar beradi.\n\n"
          "Fayl nomi kiritiladi (boshida/oxirida probel va katta harflar bo'lishi mumkin). Kengaytmasiga qarab chiqaring: "
          "«.py» — Python, «.txt» — Matn, «.jpg» yoki «.png» — Rasm, boshqa holda — Noma'lum. Kengaytma nuqtadan boshlanadi: "
          "«py» nomli faylda kengaytma yo'q.",
          "Bitta qator.", "Bitta so'z.", "tur_vq"),
    _spec("k6-smena", "Ish smenasi", "easy", 1000, ["strings", "arithmetic"], smena_solve, smena_tests,
          "Zavodda smena bir kun ichida boshlanib, o'sha kunning o'zida tugaydi. Hisobchiga smena necha soat va necha "
          "daqiqa davom etganini aytish kerak.\n\n"
          "Smena boshlanishi va tugashi alohida qatorlarda «S:D» ko'rinishida kiritiladi (soat 0–23, daqiqa 0–59; soat bir "
          "yoki ikki xonali bo'lishi mumkin: «9:30», «14:05»). Tugash vaqti har doim boshlanishdan keyin keladi. "
          "«X soat Y daqiqa» ko'rinishida chiqaring (soat 0 bo'lsa ham «0 soat ...» deb yozing).",
          "1-qator: boshlanish. 2-qator: tugash.", "Bitta qator.", "davomiylik_qv"),
    _spec("k6-email", "Email tekshiruvi", "medium", 1000, ["strings", "conditionals"], email_solve, email_tests,
          "Sayt ro'yxatdan o'tishda noto'g'ri yozilgan elektron pochtani rad etadi.\n\n"
          "Email kiritiladi (chetida ortiqcha probel bo'lishi mumkin). U to'g'ri hisoblanishi uchun: (1) aynan bitta «@» "
          "bo'lishi; (2) «@» dan oldin kamida bitta belgi bo'lishi; (3) «@» dan keyingi qismda (domen) kamida bitta «.» "
          "bo'lishi va domen «.» bilan boshlanmasligi ham, tugamasligi ham kerak. To'g'ri bo'lsa «Ha», aks holda «Yo'q» "
          "chiqaring.",
          "Bitta qator.", "Ha yoki Yo'q.", "pochta_zx"),
]

DESCRIPTION = (
    "**80 daqiqa · 8 masala.** Mavzu: satrlar (indeks, kesma, `upper` `lower` `count` `strip` `capitalize`, `split` `join`, "
    "`startswith` `endswith` `isdigit` `isalpha`).\n\n"
    "- Codeforces qoidasi: masala bali vaqt o'tishi bilan kamayadi, har noto'g'ri urinish −50 ball (kamida 30%). "
    "Masala ballari qiyinlik bo'yicha o'sib boradi: 250 dan 1000 gacha.\n"
    "- Kirish `input()` bilan o'qiladi, faqat javob chiqariladi. Kirishdagi ortiqcha probellar ham test bo'lishi mumkin.\n"
    "- Masalalarni istalgan tartibda yechishingiz mumkin.\n"
    "- Kontestdan keyin ba'zi yechimlar bo'yicha qisqa suhbat (himoya) o'tkazilishi mumkin: kodni o'zingiz yozing.")


class Command(WeekendCommand):
    help = "Creates CodeArena Round #7 and attaches its eight problems (hidden) as A..H."
    ml_mb = 64
    min_tests = 20

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.set_defaults(contest=TITLE)
        parser.add_argument("--start", default=None, help='Start, Tashkent time: "2026-10-26 10:00" (new contest)')
        parser.add_argument("--minutes", type=int, default=80, help="Length in minutes (new contest)")
        parser.add_argument("--rated", action="store_true", help="Make a new contest rated (default: not rated)")
        parser.add_argument("--pk", type=int, default=None, help="Attach to the contest with this id (titles can repeat)")

    def handle(self, *args, **opts):
        User = get_user_model()
        author = (User.objects.filter(username=opts["author"]).first() if opts["author"]
                  else User.objects.filter(is_superuser=True).order_by("pk").first())
        if author is None:
            raise CommandError("Muallif topilmadi — --author bilan mavjud login bering.")
        with transaction.atomic():
            contest = (Contest.objects.filter(pk=opts["pk"]).first() if opts["pk"]
                       else Contest.objects.filter(title__iexact=opts["contest"]).order_by("-start").first())
            if contest is None:
                if opts["start"]:
                    start = timezone.make_aware(datetime.strptime(opts["start"], "%Y-%m-%d %H:%M"))
                else:  # a week from now at 10:00: the admin sets the real time in the contest form
                    start = timezone.make_aware(datetime.combine(timezone.localdate() + timedelta(days=7), datetime.min.time())
                                                .replace(hour=10))
                contest = Contest.objects.create(
                    title=opts["contest"], description_md=DESCRIPTION, start=start,
                    end=start + timedelta(minutes=opts["minutes"]), type=Contest.Type.CF, is_rated=opts["rated"])
                self.stdout.write(f"«{contest.title}» yaratildi: {timezone.localtime(contest.start):%d.%m.%Y %H:%M}"
                                  f"{'' if opts['start'] else ' (vaqtni musobaqa formasida o‘zgartiring)'}.")
            elif contest.start <= timezone.now() and not opts["force"]:
                raise CommandError("Musobaqa allaqachon boshlangan. Baribir ulash uchun --force qo'shing.")
            for problem in Problem.objects.filter(slug__startswith="k6-", is_public=False):
                if not problem.submissions.exists():
                    problem.delete()
            self._drop_old(contest, PROBLEMS, "k6-")
            taken = set(contest.contest_problems.values_list("label", flat=True))
            # an earlier run may have attached them in another order: park the labels first (they are unique in a contest)
            for i, spec in enumerate(PROBLEMS):
                ContestProblem.objects.filter(contest=contest, problem__slug=spec["slug"]).update(label=f"~{i}")
            taken = set(contest.contest_problems.values_list("label", flat=True))
            for i, spec in enumerate(PROBLEMS):
                self._add(contest, spec, LABELS[i], i, author, taken)
                ContestProblem.objects.filter(contest=contest, problem__slug=spec["slug"]).update(
                    points=spec["points"], label=LABELS[i], order=i)
            if opts["dry_run"]:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("Dry run — hech narsa saqlanmadi."))
                return
        self.stdout.write(self.style.SUCCESS(
            f"Tayyor: «{contest.title}» da {contest.contest_problems.count()} ta masala (jami "
            f"{sum(cp.points for cp in contest.contest_problems.all())} ball). "
            "Masalalar yashirin; musobaqa tugagach Boshqaruv → Musobaqalar → «Masalalarni ochish»."))
