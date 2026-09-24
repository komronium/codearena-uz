from django.contrib.auth.backends import ModelBackend

from .models import User


class EmailOrUsernameBackend(ModelBackend):
    """The login box also takes an email address, so users whose email-looking usernames
    were renamed (usernames are public) keep logging in with what they always typed."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username and "@" in username:
            user = User.objects.filter(email__iexact=username).order_by("pk").first()
            if user is not None:
                username = user.get_username()
        return super().authenticate(request, username=username, password=password, **kwargs)
