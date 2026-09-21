from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.problems.models import Language, Problem, SQLDataset, TestCase


class Command(BaseCommand):
    help = "Seed Python language and A+B problem"

    def handle(self, *args, **opts):
        Language.objects.update_or_create(code="python", defaults=dict(
            name="Python 3", docker_image="codearena-judge-python", run_cmd="python3 main.py", tl_multiplier=3.0))
        Language.objects.update_or_create(code="cpp", defaults=dict(
            name="C++ (g++)", docker_image="codearena-judge-cpp",
            compile_cmd="g++ -O2 -o main main.cpp", run_cmd="./main", tl_multiplier=1.0))
        Language.objects.update_or_create(code="java", defaults=dict(
            name="Java", docker_image="codearena-judge-java",
            compile_cmd="javac Main.java", run_cmd="java Main", tl_multiplier=3.0))
        Language.objects.update_or_create(code="node", defaults=dict(
            name="JavaScript (Node)", docker_image="codearena-judge-node", run_cmd="node main.js", tl_multiplier=2.0))
        # Marker row only — Problem.Kind.SQL submissions run via judge.sql_judge
        # (stdlib sqlite3, no Docker); docker_image/run_cmd are unused for it.
        Language.objects.update_or_create(code="sql", defaults=dict(
            name="SQL (SQLite)", docker_image="-", run_cmd="-"))
        admin, _ = User.objects.get_or_create(username="admin", defaults=dict(role="admin", is_staff=True, is_superuser=True))
        if not admin.has_usable_password():
            admin.set_password("admin")
            admin.save()
        p, created = Problem.objects.get_or_create(slug="a-plus-b", defaults=dict(
            title="A + B", author=admin, tl_ms=1000, ml_mb=64, points=10,
            statement_md="Ikki butun son **a** va **b** berilgan. Ularning yig'indisini chiqaring.\n\n"
                         "**Kirish:** ikki qatorda a va b (−10⁹ ≤ a, b ≤ 10⁹).\n\n**Chiqish:** a + b."))
        if created:
            TestCase.objects.bulk_create([
                TestCase(problem=p, input="1\n2\n", expected="3\n", is_sample=True, order=0),
                TestCase(problem=p, input="-5\n5\n", expected="0\n", order=1),
                TestCase(problem=p, input="1000000000\n1000000000\n", expected="2000000000\n", order=2),
            ])
        sql_p, created = Problem.objects.get_or_create(slug="older-than-21", defaults=dict(
            title="21 yoshdan katta foydalanuvchilar", author=admin, kind=Problem.Kind.SQL,
            tl_ms=1000, ml_mb=64, points=10,
            statement_md="`users(id, name, age)` jadvali berilgan.\n\n"
                         "21 yoshdan katta foydalanuvchilarning ismini, yosh bo'yicha o'sish "
                         "tartibida chiqaring (bitta ustun: `name`)."))
        if created:
            SQLDataset.objects.create(
                problem=sql_p,
                schema_sql="CREATE TABLE users(id INTEGER, name TEXT, age INTEGER);",
                seed_sql="INSERT INTO users VALUES (1,'Ali',20),(2,'Vali',25),(3,'Guli',22);",
                expected_result="Guli\nVali",
            )
        self.stdout.write(self.style.SUCCESS("seeded"))
