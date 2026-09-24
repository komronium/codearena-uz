import re

from django.db import migrations


def strip_email_usernames(apps, schema_editor):
    """Usernames are public (standings, profile URLs); rename email-looking ones to the
    part before @. Login keeps working: EmailOrUsernameBackend accepts the email."""
    User = apps.get_model("accounts", "User")
    taken = set(User.objects.values_list("username", flat=True))
    for user in User.objects.filter(username__contains="@").order_by("pk"):
        base = re.sub(r"[^\w.+-]", "", user.username.split("@", 1)[0]) or "user"
        name, n = base, 1
        while name in taken:
            n += 1
            name = f"{base}{n}"
        taken.discard(user.username)
        taken.add(name)
        if not user.email:
            user.email = user.username  # keep the address they typed as the login email
        user.username = name
        user.save(update_fields=["username", "email"])


class Migration(migrations.Migration):
    dependencies = [("accounts", "0004_alter_user_rating")]
    operations = [migrations.RunPython(strip_email_usernames, migrations.RunPython.noop)]
