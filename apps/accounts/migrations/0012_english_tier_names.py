from django.db import migrations
from django.db.models import Case, Value, When

# seen_tier holds a tier's name; the tiers took Codeforces' English names.
NAMES = {"Boshlovchi": "Newbie", "Shogird": "Pupil", "Mutaxassis": "Specialist", "Bilimdon": "Expert",
         "Master": "Candidate Master", "Ustoz": "Master", "Grandmaster": "Grandmaster",
         "Afsonaviy Grandmaster": "Legendary Grandmaster"}


def rename(apps, schema_editor, names):
    User = apps.get_model("accounts", "User")
    # one UPDATE, so "Master" -> "Candidate Master" and "Ustoz" -> "Master" don't collide
    User.objects.filter(seen_tier__in=names).update(
        seen_tier=Case(*(When(seen_tier=old, then=Value(new)) for old, new in names.items())))


class Migration(migrations.Migration):
    dependencies = [("accounts", "0011_rating_starts_at_zero")]
    operations = [migrations.RunPython(lambda a, s: rename(a, s, NAMES),
                                       lambda a, s: rename(a, s, {v: k for k, v in NAMES.items()}))]
