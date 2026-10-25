from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import BaseUserCreationForm, UserCreationForm
from django.core.exceptions import ValidationError

from .avatars import shrink
from .countries import COUNTRY_CHOICES
from .models import TelegramLink, User
from .usernames import USERNAME_RULE, valid_username
from .places import OTHER, canon_city, canon_school
from django.utils.translation import gettext as _t, gettext_lazy as _tl

_CA_INPUT = {"class": "ca-input"}


def validate_public_username(username: str) -> str:
    # usernames are shown on standings and in profile URLs; an email there leaks it to everyone
    if "@" in username:
        raise forms.ValidationError(_t("Foydalanuvchi nomida @ bo‘lmasin — u hammaga ko‘rinadi. Email alohida maydonga yoziladi."))
    if not valid_username(username):
        raise forms.ValidationError(USERNAME_RULE)
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
        self.fields["username"].help_text = ""

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
        name = super().clean_username()  # Django itself refuses a taken one, whatever the case; it returns None then
        return validate_public_username(name) if name else name

    def clean_email(self):
        email = self.cleaned_data["email"]
        if not _free_stale_email(email):
            raise forms.ValidationError(_t("Bu email allaqachon ro‘yxatdan o‘tgan."))
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
        raise forms.ValidationError(_t("Bu email boshqa hisobda ishlatilgan."))
    return email


class _ProfileFields(forms.ModelForm):
    """The fields the account gate asks for (apps.accounts.onboarding.REQUIRED), all required here."""
    country = forms.ChoiceField(label=_tl("Davlat"), choices=[("", _tl("Davlatni tanlang"))] + COUNTRY_CHOICES)
    email = forms.EmailField(label="Email")
    # the city picker's "Boshqa…" (places.OTHER) sends the typed city here
    location_other = forms.CharField(required=False, max_length=100)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("first_name", "location"):
            self.fields[name].required = True
        self.fields["last_name"].required = False  # the sign-up form says it is optional
        self.fields["location"].label = "Shahar"
        self.fields["location"].error_messages["required"] = _t("Shaharni tanlang.")
        self.fields["first_name"].error_messages["required"] = _t("Ismingizni yozing.")
        self.fields["country"].error_messages["required"] = _t("Davlatni tanlang.")
        if not self.initial.get("country"):
            self.initial["country"] = "UZ"  # most users are from here

    def clean_email(self):
        return _unique_email(self.cleaned_data["email"], self.instance)

    def clean(self):
        data = super().clean()
        if "location" in data:
            city = data["location"]
            if city == OTHER:
                city = data.get("location_other", "")
            city = canon_city(data.get("country", ""), city)
            if not city:
                self.add_error("location", _t("Shaharni yozing."))
            data["location"] = city
        return data


class WelcomeForm(_ProfileFields):
    """The gate's form. A handle that breaks the rule (accounts from before it) is asked here too, with no waiting
    period: it is a fix, not a rename."""

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "country", "location", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if valid_username(self.instance.username):
            del self.fields["username"]
        else:
            self.fields["username"].help_text = ""
            self.fields["username"].error_messages["required"] = _t("Foydalanuvchi nomini yozing.")

    def clean_username(self):
        name = self.cleaned_data["username"]
        validate_public_username(name)
        if User.objects.filter(username__iexact=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_t("Bu foydalanuvchi nomi band."))
        return name


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
        if self.next_rename and valid_username(self.instance.username):  # a handle that breaks the rule may always be fixed
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
            raise forms.ValidationError(_t("Rasm 2 MB dan oshmasligi kerak."))
        if avatar and hasattr(avatar, "size"):  # a new upload (not the stored file coming back unchanged)
            try:
                return shrink(avatar, f"avatar-{self.instance.pk}")
            except (OSError, ValueError):
                raise forms.ValidationError(_t("Bu rasm emas yoki buzilgan."))
        return avatar

    def clean_username(self):
        name = self.cleaned_data["username"]
        if name == self.instance.username and valid_username(name):
            return name
        validate_public_username(name)
        if User.objects.filter(username__iexact=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_t("Bu foydalanuvchi nomi band."))
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
            "notify_digest",
        )
