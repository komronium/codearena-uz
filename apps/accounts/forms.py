from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import BaseUserCreationForm, UserCreationForm
from django.core.exceptions import ValidationError

from .countries import COUNTRY_CHOICES
from .models import TelegramLink, User

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
    is_teacher = forms.BooleanField(required=False, label="Men o‘qituvchiman")

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

    def save(self, commit=True):
        user = super().save(commit=False)
        user.teacher_requested = self.cleaned_data.get("is_teacher", False)
        if commit:
            user.save()
        return user

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Bu email allaqachon ro'yxatdan o'tgan.")
        return email



def _unique_email(email: str, user) -> str:
    if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
        raise forms.ValidationError("Bu email boshqa hisobda ishlatilgan.")
    return email


class _ProfileFields(forms.ModelForm):
    """The fields the account gate asks for (apps.accounts.onboarding.REQUIRED), all required here."""
    country = forms.ChoiceField(label="Davlat", choices=[("", "Davlatni tanlang")] + COUNTRY_CHOICES)
    email = forms.EmailField(label="Email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("first_name", "last_name", "location"):
            self.fields[name].required = True
        self.fields["location"].label = "Shahar"
        self.fields["location"].error_messages["required"] = "Shaharni yozing."
        self.fields["first_name"].error_messages["required"] = "Ismingizni yozing."
        self.fields["last_name"].error_messages["required"] = "Familiyangizni yozing."
        self.fields["country"].error_messages["required"] = "Davlatni tanlang."
        if not self.initial.get("country"):
            self.initial["country"] = "UZ"  # most users are from here

    def clean_email(self):
        return _unique_email(self.cleaned_data["email"], self.instance)


class WelcomeForm(_ProfileFields):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "country", "location", "email")


class ProfileEditForm(_ProfileFields):
    """Settings' profile card. The username may change once in USERNAME_CHANGE_DAYS days; a new email has to be
    confirmed again (the account waits on the welcome page until it is)."""

    class Meta:
        model = User
        fields = ("avatar", "username", "first_name", "last_name", "country", "location", "school", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].help_text = ""
        self.next_rename = rename_allowed_from(self.instance)
        if self.next_rename:
            self.fields["username"].disabled = True

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
            "notify_assignments",
            "notify_duels",
            "notify_badges",
            "notify_streak",
        )
