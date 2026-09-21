import random
from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.contests.models import Clarification, Contest, ContestProblem, Participation
from apps.integrity.models import FocusEvent, SimilarityFlag
from apps.problems.models import Language, Problem, Tag, TestCase
from apps.submissions.models import Submission, UserProblemSolved

TAGS = ["arrays", "graphs", "dp", "math", "strings",
        "search", "greedy", "sorting", "recursion", "binary search"]

USERNAMES = ["aziz", "dilnoza", "javlon", "malika", "sardor", "nodira", "bekzod",
             "zarina", "umid", "gulnora", "sherzod", "kamola", "otabek", "madina", "farrux"]

CITIES = ["Toshkent", "Samarqand", "Buxoro", "Andijon", "Farg'ona", "Namangan"]
SCHOOLS = ["INHA Toshkent", "TATU", "Najot Ta'lim", "IT Park Academy", "TDTU"]

VERDICTS = ["AC"] * 5 + ["WA"] * 3 + ["TLE", "MLE", "RE", "CE"]

PROBLEM_TITLES = [
    ("Ikki yig'indi", "beginner"), ("Eng uzun o'sib boruvchi ketma-ketlik", "hard"),
    ("Parenteza balansi", "advanced"), ("Grafda eng qisqa yo'l", "hard"),
    ("Anagram tekshiruv", "easy"), ("Knapsack masalasi", "hard"),
    ("Ikkilik qidiruv", "beginner"), ("Median topish", "medium"),
    ("Eng katta umumiy bo'luvchi", "easy"), ("Segment daraxt", "hard"),
    ("Saralangan massivni birlashtirish", "advanced"), ("Palindrom tekshiruv", "beginner"),
    ("Chuqurlik bo'yicha qidiruv", "medium"), ("Kengin qidiruv", "advanced"),
    ("Eng qisqa umumiy qism satr", "hard"), ("Matritsa aylantirish", "medium"),
    ("Steklar yordamida hisoblash", "advanced"), ("Ikki ko'rsatkich usuli", "easy"),
]


class Command(BaseCommand):
    help = "Seed randomized demo data (users, problems, contests, submissions) for UI review."

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true", help="Delete previously seeded demo rows first.")

    def handle(self, *args, **opts):
        random.seed(42)
        call_command("seed")

        if opts["flush"]:
            demo_users = User.objects.filter(username__in=USERNAMES)
            UserProblemSolved.objects.filter(user__in=demo_users).delete()
            Submission.objects.filter(user__in=demo_users).delete()
            Problem.objects.filter(author__in=demo_users).delete()
            Contest.objects.filter(title__startswith="Demo").delete()
            demo_users.delete()
            Problem.objects.filter(title__in=[t for t, _ in PROBLEM_TITLES]).delete()

        with transaction.atomic():
            admin = User.objects.get(username="admin")
            tags = [Tag.objects.get_or_create(name=n)[0] for n in TAGS]
            languages = list(Language.objects.filter(is_active=True))

            users = []
            for i, uname in enumerate(USERNAMES):
                user, _ = User.objects.get_or_create(username=uname, defaults=dict(
                    email=f"{uname}@example.uz",
                    role=User.Role.TEACHER if i == 0 else User.Role.STUDENT,
                    rating=random.randint(900, 1600),
                    practice_points=random.randint(0, 3000),
                    location=random.choice(CITIES),
                    school=random.choice(SCHOOLS),
                ))
                if not user.has_usable_password():
                    user.set_unusable_password()
                    user.save()
                users.append(user)

            problems = []
            for title, diff in PROBLEM_TITLES:
                slug_base = title.lower().replace("'", "").replace(" ", "-")
                p, created = Problem.objects.get_or_create(title=title, defaults=dict(
                    slug=slug_base, author=admin, difficulty=diff,
                    tl_ms=random.choice([1000, 1500, 2000]), ml_mb=256,
                    points=random.choice([50, 100, 150, 200]), is_public=True,
                    statement_md=f"**{title}** masalasi. Berilgan shartlarga ko'ra yechim toping.\n\n"
                                 "Masala matni bu yerda bo'ladi: nima berilgan, nimani topish kerak, "
                                 "qanday chegaralar bor ($1 \\le n \\le 10^5$).",
                    input_md="Birinchi qatorda bitta butun son $n$ — elementlar soni.\n\n"
                             "Ikkinchi qatorda $n$ ta butun son $a_1, a_2, \\ldots, a_n$.",
                    output_md="Yagona qatorda javobni chiqaring.",
                ))
                if p.difficulty != diff:  # re-runs re-level older seeds onto the current 5-step scale
                    p.difficulty = diff
                    p.save(update_fields=["difficulty"])
                if created:
                    p.tags.set(random.sample(tags, k=random.randint(1, 3)))
                    TestCase.objects.bulk_create([
                        TestCase(problem=p, input="1\n2\n", expected="3\n", is_sample=True, order=0),
                        TestCase(problem=p, input="5\n7\n", expected="12\n", order=1),
                    ])
                problems.append(p)

            # a couple of pending problems for the moderation queue
            for i, u in enumerate(users[1:4]):
                Problem.objects.get_or_create(
                    title=f"Foydalanuvchi masalasi #{i + 1}", defaults=dict(
                        slug=f"foydalanuvchi-masalasi-{i + 1}", author=u, difficulty="medium",
                        status=Problem.Status.PENDING, is_public=False, points=100,
                        statement_md="Foydalanuvchi tomonidan yuborilgan masala, tekshiruv kutilmoqda.",
                    ))

            now = timezone.now()
            submissions = []
            for u in users:
                for p in random.sample(problems, k=random.randint(4, 10)):
                    n_attempts = random.randint(1, 3)
                    for a in range(n_attempts):
                        verdict = "AC" if a == n_attempts - 1 and random.random() < 0.7 else random.choice(VERDICTS)
                        created = now - timedelta(days=random.randint(0, 150), hours=random.randint(0, 23))
                        submissions.append(Submission(
                            user=u, problem=p, language=random.choice(languages), source="print('demo')",
                            verdict=verdict, exec_ms=random.randint(20, 900), mem_kb=random.randint(2000, 60000),
                            passed=3 if verdict == "AC" else random.randint(0, 2), total=3, created=created,
                        ))
            created_at = [s.created for s in submissions]
            # auto_now_add overwrites `created` on insert; restore the random dates
            for s, ts in zip(Submission.objects.bulk_create(submissions), created_at):
                Submission.objects.filter(pk=s.pk).update(created=ts)

            for u in users:
                for p in problems:
                    first_ac = (Submission.objects.filter(user=u, problem=p, verdict="AC")
                                .order_by("created").first())
                    if first_ac:
                        UserProblemSolved.objects.get_or_create(
                            user=u, problem=p, defaults=dict(first_ac_submission=first_ac))

            # contests: 5 ended (rated, build rating history), 1 running, 1 upcoming
            contest_defs = [
                ("Demo musobaqa 1", now - timedelta(days=120), now - timedelta(days=120, hours=-2), True),
                ("Demo musobaqa 2", now - timedelta(days=90), now - timedelta(days=90, hours=-2), True),
                ("Demo musobaqa 3", now - timedelta(days=60), now - timedelta(days=60, hours=-2), True),
                ("Demo musobaqa 4", now - timedelta(days=35), now - timedelta(days=35, hours=-2), True),
                ("Demo musobaqa 5", now - timedelta(days=12), now - timedelta(days=12, hours=-2), True),
                ("Demo musobaqa (jonli)", now - timedelta(hours=1), now + timedelta(hours=2), False),
                ("Demo musobaqa (kelgusi)", now + timedelta(days=5), now + timedelta(days=5, hours=3), False),
            ]
            contests = []
            for title, start, end, is_rated in contest_defs:
                c, _ = Contest.objects.get_or_create(title=title, defaults=dict(
                    start=start, end=end, type=Contest.Type.ICPC, is_rated=is_rated,
                    rating_applied=is_rated))
                contests.append(c)
                for i, p in enumerate(random.sample(problems, k=4)):
                    ContestProblem.objects.get_or_create(
                        contest=c, label=chr(ord("A") + i), defaults=dict(problem=p, order=i, points=100))

            ended_contests = contests[:5]
            for u in users:
                rating = random.randint(950, 1300)
                for c in ended_contests:
                    delta = random.randint(-120, 180)
                    Participation.objects.get_or_create(user=u, contest=c, defaults=dict(
                        rating_before=rating, rating_after=rating + delta,
                        score=random.randint(0, 400), penalty=random.randint(0, 600),
                        rank=random.randint(1, len(users))))
                    rating += delta
                    u.rating = rating
                    u.save(update_fields=["rating"])
                    for cp in c.contest_problems.all():
                        if random.random() < 0.6:
                            s = Submission.objects.create(
                                user=u, problem=cp.problem, contest=c, language=random.choice(languages),
                                source="print('demo')", verdict=random.choice(VERDICTS),
                                exec_ms=random.randint(20, 900), mem_kb=random.randint(2000, 60000),
                                passed=3, total=3)
                            Submission.objects.filter(pk=s.pk).update(
                                created=c.start + timedelta(minutes=random.randint(1, 100)))
            # running contest: a few live participants, no rating yet
            for u in random.sample(users, k=6):
                Participation.objects.get_or_create(user=u, contest=contests[5])

            for c in ended_contests + [contests[5]]:
                for u in random.sample(users, k=2):
                    Clarification.objects.get_or_create(
                        contest=c, user=u, question="Testlar chegarasi qancha?",
                        defaults=dict(answer="10^9 gacha.", answered_by=admin, answered_at=now))

            # Integrity demo: similarity flags (some reviewed) and behaviour events with
            # a few obvious "suspects" per contest so the report has something to show.
            NOTES = ["Bir xil kod, faqat o'zgaruvchi nomlari farq qiladi.", "Tasodif — standart yechim.", ""]
            for c in ended_contests:
                subs = list(Submission.objects.filter(contest=c, verdict="AC").order_by("problem_id", "user_id"))
                pairs = [(a, b) for a in subs for b in subs if a.problem_id == b.problem_id and a.user_id < b.user_id]
                for a, b in random.sample(pairs, k=min(4, len(pairs))):
                    SimilarityFlag.objects.get_or_create(
                        submission_a=a, submission_b=b,
                        defaults=dict(score=round(random.uniform(0.62, 0.99), 2),
                                      reviewed=random.random() < 0.4, note=random.choice(NOTES)))
                if not FocusEvent.objects.filter(contest=c).exists():
                    events = []
                    for u in random.sample(users, k=8):
                        suspicious = random.random() < 0.3
                        blurs = random.randint(6, 25) if suspicious else random.randint(0, 4)
                        kinds = ["blur", "focus"] * blurs
                        kinds += ["paste"] * (random.randint(2, 6) if suspicious else random.choice([0, 0, 1]))
                        kinds += ["copy"] * random.randint(0, 3)
                        events += [FocusEvent(user=u, contest=c, kind=k) for k in kinds]
                    FocusEvent.objects.bulk_create(events)

        self.stdout.write(self.style.SUCCESS(
            f"seeded demo data: {len(users)} users, {len(problems)} problems, "
            f"{Submission.objects.count()} submissions, {len(contests)} contests"))
