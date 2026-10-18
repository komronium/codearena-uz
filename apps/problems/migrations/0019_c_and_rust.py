# C and Rust join the judge's languages. Their images: judge/images/c and judge/images/rust (see the README's build loop).

from django.db import migrations

LANGS = {
    "c": dict(name="C (gcc)", docker_image="codearena-judge-c",
              compile_cmd="gcc -O2 -std=c17 -o main main.c -lm", run_cmd="./main", tl_multiplier=1.0),
    "rust": dict(name="Rust", docker_image="codearena-judge-rust",
                 compile_cmd="rustc -O --edition 2021 -o main main.rs", run_cmd="./main", tl_multiplier=1.0),
}


def add(apps, schema_editor):
    Language = apps.get_model("problems", "Language")
    for code, fields in LANGS.items():
        Language.objects.update_or_create(code=code, defaults=fields)


def remove(apps, schema_editor):
    apps.get_model("problems", "Language").objects.filter(code__in=LANGS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("problems", "0018_merge_daily_problem_selection_problem_updated"),
    ]

    operations = [migrations.RunPython(add, remove)]
