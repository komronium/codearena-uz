import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("classroom", "0006_duelseasonresult"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LiveQuiz",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(blank=True, max_length=120)),
                ("code", models.CharField(db_index=True, max_length=6)),
                ("language", models.CharField(choices=[("python", "Python"), ("cpp", "C++"), ("java", "Java"), ("js", "JavaScript")], max_length=10)),
                ("level", models.CharField(choices=[("beginner", "Beginner"), ("easy", "Easy"), ("medium", "Medium")], max_length=10)),
                ("questions", models.JSONField(default=list)),
                ("status", models.CharField(choices=[("lobby", "Kutish zali"), ("question", "Savol"), ("reveal", "Natija"), ("done", "Tugagan")], default="lobby", max_length=10)),
                ("index", models.IntegerField(default=-1)),
                ("question_started_at", models.DateTimeField(blank=True, null=True)),
                ("seconds", models.PositiveSmallIntegerField(default=20)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("teacher", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created"]},
        ),
        migrations.CreateModel(
            name="LiveQuizPlayer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("score", models.IntegerField(default=0)),
                ("joined", models.DateTimeField(auto_now_add=True)),
                ("quiz", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="players", to="classroom.livequiz")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="LiveQuizAnswer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("index", models.PositiveSmallIntegerField()),
                ("answer", models.CharField(blank=True, max_length=200)),
                ("correct", models.BooleanField(default=False)),
                ("points", models.PositiveIntegerField(default=0)),
                ("ms", models.PositiveIntegerField(default=0)),
                ("quiz", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="answers", to="classroom.livequiz")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="livequizplayer",
            constraint=models.UniqueConstraint(fields=("quiz", "user"), name="one_player_per_live_quiz"),
        ),
        migrations.AddConstraint(
            model_name="livequizanswer",
            constraint=models.UniqueConstraint(fields=("quiz", "user", "index"), name="one_live_answer"),
        ),
    ]
