from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User

_CA_INPUT = {"class": "ca-input"}


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=150, label="Ism")
    last_name = forms.CharField(max_length=150, label="Familiya", required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "first_name", "last_name")

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
