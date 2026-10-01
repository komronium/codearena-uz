"""Split the broad `loops` and `math` tags into the topics the O‘rganish courses follow, and give a few
problems the tag of the course they belong to. Problems are matched by slug; ones that don't exist
here are skipped. Safe to re-run. `loops` and `math` are deleted once no problem carries them, so the
problem form and the AI generator stop offering them. --reverse puts the old tags back.

    python manage.py retag_problems [--dry-run] [--reverse]
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.problems.models import Problem, Tag

# loops -> for-loop when the count is known up front, while-loop when a condition stops it
# ("digits", "how many years until"); nested-loops when one loop runs inside another.
LOOPS = {
    "kundalik-mashqlar-push-up-hisoblagichi": "for-loop", "bozorda-narxlar-jadvali": "for-loop",
    "kunlik-qadam-soni": "for-loop", "dokondagi-umumiy-xarid-summasi": "for-loop",
    "shahardagi-eng-baland-bino": "for-loop", "faktorial": "for-loop", "juft-sonlar-soni": "for-loop",
    "dokon-cheki": "for-loop", "sinf-ortacha-bahosi": "for-loop", "eng-qimmat-mahsulot": "for-loop",
    "sovuq-kunlar": "for-loop", "qadam-hisoblagich": "for-loop", "jamgarma-maqsadi": "for-loop",
    "jamgarma-daftari": "for-loop", "chek-raqamlari-yigindisi": "while-loop",
    "qutilarga-teng-bolish-boluvchilar": "for-loop", "quyonlar-fermasi": "for-loop",
    "unli-harflarni-sanash": "for-loop", "kinoteatr-orindiqlari": "for-loop", "maxsus-sonlar": "for-loop",
    "c3-even-digits": "while-loop", "c3-vowels": "for-loop", "c3-compress": "for-loop",
    "wc1-kopaytirish-jadvali": "for-loop", "wc1-omonat": "while-loop", "wc1-sport-rejimi": "for-loop",
    "wc1-ikkilik-son": "while-loop number-basics", "wc1-palindrom-sonlar": "for-loop",
    "wc1-kop-olingan-baho": "for-loop", "wc1-tub-kopaytuvchilar": "while-loop number-basics",
    "p1-faktorial": "for-loop", "p1-raqamlar-soni": "while-loop", "p1-raqamlar-kopaytmasi": "while-loop",
    "p1-boluvchilar-soni": "for-loop", "p1-tub-sonmi": "for-loop", "p1-eng-issiq-eng-sovuq": "for-loop",
    "p1-musbat-manfiy-nol": "for-loop", "p1-quyonlar-oilasi": "for-loop", "p1-bakteriyalar": "while-loop",
    "p1-yulduzcha-zinapoya": "for-loop nested-loops", "p1-raqamli-ildiz": "while-loop nested-loops",
    "p1-jamgarma": "while-loop", "p2-eng-boy-mijoz": "nested-loops matrices", "p2-ketma-ket-birlar": "for-loop",
    "ca4-uchlik": "for-loop", "ca4-dokon-hisoboti": "for-loop", "ca4-toq-boluvchilar": "for-loop",
    "ca4-yettilik": "for-loop", "ca4-harf-baho": "for-loop", "ca4-jamgarma": "while-loop",
    # hidden or rejected, retagged so the old tags can go
    "kopaytirish-jadvali": "for-loop", "kopaytirish-jadvali-2": "for-loop", "avtobusdagi-eng-arzon-chipta": "for-loop",
    "sovgalarni-joylashtirish-faktorial": "for-loop", "har-k-chi-xaridorga-sovga": "for-loop",
    "chek-raqamini-teskari-oqish": "while-loop",
}

# math -> number-basics for divisors, primes, number bases and roots; arithmetic for the rest.
NUMBER_BASICS = {"p1-boluvchilar-soni", "p1-tub-sonmi", "p2-ikkining-darajasi", "p2-jadval-ustuni",
                 "p2-butun-ildiz", "ca4-toq-boluvchilar"}
ARITHMETIC = {
    "a-plus-b", "rectangle", "last-digit", "digit-sum-3", "reverse-two-digit", "seconds-to-hms", "discount",
    "c-sum-product", "c-queen", "electricity-bill", "kundalik-mashqlar-push-up-hisoblagichi",
    "kunlik-qadam-soni", "dokondagi-umumiy-xarid-summasi", "faktorial", "juft-sonlar-soni",
    "burger-va-kola-narxi", "taksi-xizmati-narxi", "bozor-xaridi", "chegirma-bilan-xarid",
    "ikki-son-yigindisi-va-ayirmasi", "doira-perimetri-va-yuzi", "dokon-cheki", "sinf-ortacha-bahosi",
    "jamgarma-maqsadi", "jamgarma-daftari", "chek-raqamlari-yigindisi", "kinoteatr-orindiqlari",
    "maxsus-sonlar", "tangalar", "pitsa-bolish", "p1-olmalarni-bolish", "p1-kinoteatrda-orin",
    "p1-dars-qachon-tugaydi", "p1-poyezd-yoli", "p1-bayram-konfetlari", "p1-svetofor",
    "p1-tenglama-ildizlari", "p1-nuqta-va-aylana", "p2-yoqolgan-son", "p2-katta-songa-bir", "p2-baxtli-son",
    "ca4-kassa", "ca4-yettilik", "mc1-partalar", "mc1-chetki-raqamlar", "mc1-soat-formati", "ca4-jamgarma",
    # hidden or rejected
    "c-middle-digit", "c-manhattan", "c2-shop-discount", "kitob-va-daftar-narxi", "kvadrat-perimetri-va-yuzi",
    "chek-raqamini-teskari-oqish",
}
MATH = {**{s: "number-basics" for s in NUMBER_BASICS}, **{s: "arithmetic" for s in ARITHMETIC},
        "p2-zinapoya": "combinatorics"}

# slug -> (tags removed, tags added)
OTHER = {
    "qutilarga-teng-bolish-boluvchilar": ("number-theory", "number-basics"),  # easy: divisors, not theory
    "qavslar-balansi": ("", "stack"),
    "oraliq-minimumi": ("", "segment-tree"),
    "labirint": ("", "bfs"),
    "shaharlar-yollari": ("", "shortest-paths"),
    "yollar-tarmogi": ("", "union-find"),
    "eng-uzun-oraliq": ("", "sliding-window"),
    "older-than-21": ("", "where"),
}


def changes() -> dict[str, tuple[set[str], set[str]]]:
    """slug -> (tags to remove, tags to add)."""
    out: dict[str, tuple[set[str], set[str]]] = {}
    for old, table in (("loops", LOOPS), ("math", MATH)):
        for slug, new in table.items():
            remove, add = out.setdefault(slug, (set(), set()))
            remove.add(old)
            add.update(new.split())
    for slug, (old, new) in OTHER.items():
        remove, add = out.setdefault(slug, (set(), set()))
        remove.update(old.split())
        add.update(new.split())
    return out


class Command(BaseCommand):
    help = "Retag problems for the O‘rganish courses (loops/math split, missing course tags)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show what would change, write nothing.")
        parser.add_argument("--reverse", action="store_true", help="Undo: put the old tags back.")

    def handle(self, *args, dry_run=False, reverse=False, **options):
        plan = changes()
        problems = Problem.objects.filter(slug__in=plan).prefetch_related("tags").in_bulk(field_name="slug")
        changed = 0
        with transaction.atomic():
            for slug, (remove, add) in plan.items():
                problem = problems.get(slug)
                if problem is None:
                    continue
                if reverse:
                    remove, add = add, remove
                kind = Tag.Kind.SQL if problem.kind == Problem.Kind.SQL else Tag.Kind.CODE
                had = {t.name for t in problem.tags.all()}
                gone, new = had & remove, add - had
                if not gone and not new:
                    continue
                problem.tags.remove(*[t for t in problem.tags.all() if t.name in gone])
                problem.tags.add(*[Tag.objects.get_or_create(name=n, defaults={"kind": kind})[0] for n in new])
                changed += 1
                diff = [f"-{n}" for n in sorted(gone)] + [f"+{n}" for n in sorted(new)]
                self.stdout.write(f"{slug}: {' '.join(diff)}")
            if not reverse:
                for name in ("loops", "math"):
                    left = list(Problem.objects.filter(tags__name=name).values_list("slug", flat=True))
                    if left:
                        self.stdout.write(f"«{name}» qoldi ({len(left)}): {', '.join(sorted(left))}")
                    else:
                        Tag.objects.filter(name=name).delete()
            self.stdout.write(f"{changed} ta masala o‘zgardi, {len(plan) - len(problems)} ta slug bu yerda yo‘q")
            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write("dry-run: hech narsa saqlanmadi")
