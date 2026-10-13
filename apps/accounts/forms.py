from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import BaseUserCreationForm, UserCreationForm
from django.core.exceptions import ValidationError

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



class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("avatar", "first_name", "last_name", "location", "school")
        widgets = {
            "first_name": forms.TextInput(attrs=_CA_INPUT),
            "last_name": forms.TextInput(attrs=_CA_INPUT),
            "location": forms.TextInput(attrs=_CA_INPUT),
            "school": forms.TextInput(attrs=_CA_INPUT),
        }


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
