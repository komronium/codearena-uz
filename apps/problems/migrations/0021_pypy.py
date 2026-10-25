# PyPy joins the judge's languages. Its image: judge/images/pypy (see the README's build loop).

from django.db import migrations

PYPY = dict(name="PyPy 3", docker_image="codearena-judge-pypy", compile_cmd="", run_cmd="pypy3 main.py", tl_multiplier=2.0)


def add(apps, schema_editor):
    apps.get_model("problems", "Language").objects.update_or_create(code="pypy", defaults=PYPY)


def remove(apps, schema_editor):
    apps.get_model("problems", "Language").objects.filter(code="pypy").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("problems", "0020_problem_source_lang"),
    ]

    operations = [migrations.RunPython(add, remove)]
