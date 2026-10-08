from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integrity", "0011_similarityflag_deep"),
    ]

    operations = [
        migrations.AlterField(
            model_name="auditentry",
            name="action",
            field=models.CharField(
                choices=[
                    ("disqualify", "Diskvalifikatsiya"),
                    ("requalify", "Diskvalifikatsiya bekor"),
                    ("void", "Masala natijasi bekor"),
                    ("unvoid", "Masala natijasi tiklandi"),
                    ("penalty", "AI jarimasi: xato urinish, masala bloklandi"),
                    ("rejudge", "Qayta tekshiruv"),
                    ("publish", "Masalalar ochildi"),
                    ("rating_apply", "Reyting hisoblandi"),
                    ("rating_recompute", "Reyting qayta hisoblandi"),
                    ("flag_review", "O‘xshashlik ko‘rildi"),
                    ("problem_delete", "Masala o‘chirildi"),
                    ("contest_delete", "Musobaqa o‘chirildi"),
                    ("user_delete", "Foydalanuvchi o‘chirildi"),
                    ("verify", "Shaxsi tasdiqlandi"),
                    ("unverify", "Shaxs tasdig‘i bekor"),
                    ("official_review", "Kodini tushuntirdi"),
                    ("official_apply", "Rasmiy reyting qo‘llandi"),
                ],
                max_length=20,
            ),
        ),
    ]
