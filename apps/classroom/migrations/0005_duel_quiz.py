import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def coding_duels_to_history(apps, schema_editor):
    """Every duel so far was a coding race: it stays as history. One still open can't go on as a quiz,
    so it lapses with no rating change."""
    Duel = apps.get_model("classroom", "Duel")
    Duel.objects.update(mode="code")
    Duel.objects.filter(status__in=["pending", "active"]).update(status="expired")


def replay_ratings(apps, schema_editor):
    """The finished coding duels count as if they had been quizzes with the same results: duel ratings
    are worked out again from 1200 with the quiz's K (40 for a player's first 30 duels, then 20, then 10
    from 2000). A copy of apps.classroom.duels.replay as it was, so this migration never changes."""
    Duel, User = apps.get_model("classroom", "Duel"), apps.get_model("accounts", "User")
    rating, played = {}, {}

    def k(r, n):
        return 40 if n < 30 else (10 if r >= 2000 else 20)

    for d in Duel.objects.filter(status="finished").order_by("created", "pk"):
        a, b = d.challenger_id, d.opponent_id
        ra, rb = rating.get(a, 1200), rating.get(b, 1200)
        score = 0.5 if d.winner_id is None else (1.0 if d.winner_id == a else 0.0)
        expected = 1 / (1 + 10 ** ((rb - ra) / 400))
        da = round(k(ra, played.get(a, 0)) * (score - expected))
        db = round(k(rb, played.get(b, 0)) * ((1 - score) - (1 - expected)))
        Duel.objects.filter(pk=d.pk).update(challenger_delta=da, opponent_delta=db)
        rating[a], rating[b] = ra + da, rb + db
        played[a], played[b] = played.get(a, 0) + 1, played.get(b, 0) + 1
    User.objects.exclude(pk__in=rating).exclude(duel_rating=1200).update(duel_rating=1200)
    for pk, r in rating.items():
        User.objects.filter(pk=pk).update(duel_rating=r)


class Migration(migrations.Migration):

    dependencies = [
        ("classroom", "0004_duel_own_clocks"),
        ("accounts", "0014_telegram_learning_notifications"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DuelQuestion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=40, unique=True)),
                ("language", models.CharField(choices=[("python", "Python"), ("cpp", "C++"), ("java", "Java"), ("js", "JavaScript")], max_length=10)),
                ("level", models.CharField(choices=[("beginner", "Beginner"), ("easy", "Easy"), ("medium", "Medium")], max_length=10)),
                ("kind", models.CharField(choices=[("output", "Nima chiqaradi?"), ("fill", "Bo‘sh joyni to‘ldiring")], max_length=10)),
                ("code", models.TextField()),
                ("full", models.BooleanField(default=False)),
                ("expect", models.TextField(blank=True)),
                ("options", models.JSONField(blank=True, default=list)),
                ("answer", models.CharField(max_length=200)),
                ("accept", models.JSONField(blank=True, default=list)),
                ("explain", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["language", "level", "id"]},
        ),
        migrations.AddField(
            model_name="duel",
            name="mode",
            field=models.CharField(choices=[("quiz", "Savollar"), ("code", "Masala")], default="quiz", max_length=10),
        ),
        migrations.AddField(
            model_name="duel",
            name="language",
            field=models.CharField(blank=True, choices=[("python", "Python"), ("cpp", "C++"), ("java", "Java"), ("js", "JavaScript")], max_length=10),
        ),
        migrations.AddField(
            model_name="duel",
            name="questions",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(coding_duels_to_history, migrations.RunPython.noop),
        migrations.RunPython(replay_ratings, migrations.RunPython.noop),
        migrations.CreateModel(
            name="DuelAnswer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("index", models.PositiveSmallIntegerField()),
                ("shown_at", models.DateTimeField()),
                ("answered_at", models.DateTimeField(blank=True, null=True)),
                ("answer", models.CharField(blank=True, max_length=200)),
                ("correct", models.BooleanField(default=False)),
                ("duel", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="answers", to="classroom.duel")),
                ("question", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="classroom.duelquestion")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["index"]},
        ),
        migrations.AddConstraint(
            model_name="duelanswer",
            constraint=models.UniqueConstraint(fields=("duel", "user", "index"), name="one_answer_per_question"),
        ),
    ]
