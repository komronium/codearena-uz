from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import BaseUserCreationForm, UserCreationForm
from django.core.exceptions import ValidationError

from .countries import COUNTRY_CHOICES
from .models import TelegramLink, User
from .places import OTHER, canon_city, canon_school

_CA_INPUT = {"class": "ca-input"}


def validate_public_username(username: str) -> str:
    # usernames are shown on standings and in profile URLs; an email there leaks it to everyone
    if "@" in username:
        raise forms.ValidationError("Foydalanuvchi nomida @ bo‘lmasin — u hammaga ko‘rinadi. Email alohida maydonga yoziladi.")
    return username


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=150, label="Ism")
    last_name = forms.CharField(max_length=150, label="Familiya", required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "first_name", "last_name")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # One password field: the eye button lets people check what they typed, and a second box costs sign-ups.
        del self.fields["password2"]

    def _post_clean(self):
        # Skip the parent's check of password2 (gone) and validate the one password here.
        super(BaseUserCreationForm, self)._post_clean()
        password = self.cleaned_data.get("password1")
        if password:
            try:
                password_validation.validate_password(password, self.instance)
            except ValidationError as error:
                self.add_error("password1", error)

    def clean_username(self):
        return validate_public_username(super().clean_username())

    def clean_email(self):
        email = self.cleaned_data["email"]
        if not _free_stale_email(email):
            raise forms.ValidationError("Bu email allaqachon ro'yxatdan o'tgan.")
        return email



def _free_stale_email(email: str, exclude_pk=None) -> bool:
    """True when `email` is free to take. An address nobody confirmed within 3 days of signing up is released (the
    old account keeps working with a blank email), so pre-registering somebody else's address cannot lock them out."""
    from datetime import timedelta
    from django.utils import timezone
    taken = User.objects.filter(email__iexact=email)
    if exclude_pk:
        taken = taken.exclude(pk=exclude_pk)
    stale = taken.filter(email_verified_at__isnull=True, is_staff=False,
                         date_joined__lt=timezone.now() - timedelta(days=3))
    stale.update(email="")
    return not taken.exists()


def _unique_email(email: str, user) -> str:
    if not _free_stale_email(email, user.pk):
        raise forms.ValidationError("Bu email boshqa hisobda ishlatilgan.")
    return email


class _ProfileFields(forms.ModelForm):
    """The fields the account gate asks for (apps.accounts.onboarding.REQUIRED), all required here."""
    country = forms.ChoiceField(label="Davlat", choices=[("", "Davlatni tanlang")] + COUNTRY_CHOICES)
    email = forms.EmailField(label="Email")
    # the city picker's "Boshqa…" (places.OTHER) sends the typed city here
    location_other = forms.CharField(required=False, max_length=100)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("first_name", "location"):
            self.fields[name].required = True
        self.fields["last_name"].required = False  # the sign-up form says it is optional
        self.fields["location"].label = "Shahar"
        self.fields["location"].error_messages["required"] = "Shaharni tanlang."
        self.fields["first_name"].error_messages["required"] = "Ismingizni yozing."
        self.fields["country"].error_messages["required"] = "Davlatni tanlang."
        if not self.initial.get("country"):
            self.initial["country"] = "UZ"  # most users are from here
        if self.instance.pk and not self.instance.email and self.instance.email_verified_at:
            self.fields["email"].required = False  # signed up through Telegram: an email can be added later

    def clean_email(self):
        email = self.cleaned_data["email"]
        return _unique_email(email, self.instance) if email else ""

    def clean(self):
        data = super().clean()
        if "location" in data:
            city = data["location"]
            if city == OTHER:
                city = data.get("location_other", "")
            city = canon_city(data.get("country", ""), city)
            if not city:
                self.add_error("location", "Shaharni yozing.")
            data["location"] = city
        return data


class WelcomeForm(_ProfileFields):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "country", "location", "email")


class ProfileEditForm(_ProfileFields):
    """Settings' profile card. The username may change once in USERNAME_CHANGE_DAYS days; a new email has to be
    confirmed again (the account waits on the welcome page until it is)."""
    school_other = forms.CharField(required=False, max_length=150)  # the school picker's "Boshqa…"

    class Meta:
        model = User
        fields = ("avatar", "username", "first_name", "last_name", "country", "location", "school", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].help_text = ""
        self.fields["school"].required = False
        self.next_rename = rename_allowed_from(self.instance)
        if self.next_rename:
            self.fields["username"].disabled = True

    def clean(self):
        data = super().clean()
        if "school" in data:
            school = data["school"]
            if school == OTHER:
                school = data.get("school_other", "")
            data["school"] = canon_school(data.get("country", ""), school)
        return data

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if avatar and hasattr(avatar, "size") and avatar.size > 2 * 1024 * 1024:
            raise forms.ValidationError("Rasm 2 MB dan oshmasligi kerak.")
        return avatar

    def clean_username(self):
        name = self.cleaned_data["username"]
        if name == self.instance.username:
            return name
        validate_public_username(name)
        if User.objects.filter(username__iexact=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Bu foydalanuvchi nomi band.")
        return name


def rename_allowed_from(user):
    """The day the user may rename themselves again, or None if they may now."""
    if user.username_changed_at is None:
        return None
    from datetime import timedelta

    from django.conf import settings
    from django.utils import timezone
    when = user.username_changed_at + timedelta(days=settings.USERNAME_CHANGE_DAYS)
    return when if when > timezone.now() else None


class TelegramPreferencesForm(forms.ModelForm):
    class Meta:
        model = TelegramLink
        fields = (
            "notify_daily_problem",
            "notify_daily_tip",
            "notify_trending_problem",
            "notify_contests",
            "notify_duels",
            "notify_badges",
            "notify_streak",
        )
