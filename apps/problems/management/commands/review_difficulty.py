"""Check every problem's difficulty against how students actually did on it.

For each approved problem: how many students tried it (distinct users with a submission, staff and
the author left out) and how many solved it. The solve rate points at a level (scoring.level_for_rate):
80%+ beginner, 55%+ easy, 30%+ medium, below that hard. Problems whose label disagrees are listed;
with --apply they move one level towards what the data says (never two at once), and their points
and everyone's practice points follow at once. A few labels are also fixed from reading the
statement (RELABEL), whatever the data says.

    python manage.py review_difficulty [--min-tried 8] [--apply]
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, F, Q

from apps.problems.models import Problem
from apps.problems.scoring import level_for_rate

# Read, not measured: labelled Medium, but each needs only a few `if`s.
RELABEL = {"sort-three": "easy", "closest-to-zero": "easy", "c-queen": "easy"}
ORDER = list(Problem.Difficulty.values)


class Command(BaseCommand):
    help = "Report (and with --apply, fix) problem difficulties that don't match how students did."

    def add_arguments(self, parser):
        parser.add_argument("--min-tried", type=int, default=8,
                            help="Students who must have tried a problem before its label is judged")
        parser.add_argument("--apply", action="store_true", help="Move the flagged problems one level")

    def handle(self, *args, **opts):
        students = Q(submissions__user__is_staff=False) & ~Q(submissions__user=F("author"))
        problems = (Problem.objects.filter(status=Problem.Status.APPROVED)
                    .annotate(tried=Count("submissions__user", filter=students, distinct=True),
                              solved=Count("userproblemsolved", distinct=True,
                                           filter=Q(userproblemsolved__user__is_staff=False)
                                           & ~Q(userproblemsolved__user=F("author"))))
                    .order_by("id"))
        moves, thin, fine = [], 0, 0
        for p in problems:
            want = RELABEL.get(p.slug)
            why = "matnga ko'ra"
            if want is None and p.tried >= opts["min_tried"]:
                rate = min(p.solved / p.tried, 1.0)
                want, why = level_for_rate(rate), f"{p.solved}/{p.tried} yechdi ({rate:.0%})"
            elif want is None:
                thin += 1
                continue
            if want == p.difficulty:
                fine += 1
                continue
            step = 1 if ORDER.index(want) > ORDER.index(p.difficulty) else -1
            moves.append((p, ORDER[ORDER.index(p.difficulty) + step], want, why))

        self.stdout.write(f"{fine} ta masala darajasiga mos, {thin} tasida hali ma'lumot kam "
                          f"(< {opts['min_tried']} talaba urinib ko'rgan).")
        if not moves:
            self.stdout.write(self.style.SUCCESS("O'zgartirish kerak bo'lgan masala yo'q."))
            return
        self.stdout.write(f"\n{len(moves)} ta masala darajasi mos emas:")
        for p, to, want, why in moves:
            aim = "" if to == want else f" (ma'lumot {want} deydi — bir qadam)"
            self.stdout.write(f"  #{p.pk:04d} {p.title[:40]:40} {p.difficulty:>8} → {to:<8}{aim}  · {why}")
        if not opts["apply"]:
            self.stdout.write("\nO'zgartirish uchun: --apply bilan qayta ishga tushiring.")
            return
        for p, to, _, _ in moves:
            p.difficulty = to
            p.save(update_fields=["difficulty"])  # reprices it and its solvers' practice points
        self.stdout.write(self.style.SUCCESS(f"{len(moves)} ta masala darajasi yangilandi, ballari qayta hisoblandi."))
