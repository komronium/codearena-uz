from django import forms

from .models import MAX_LISTS, ProblemList


class ListForm(forms.ModelForm):
    class Meta:
        model = ProblemList
        fields = ["name", "is_public"]
        widgets = {"name": forms.TextInput(attrs={"class": "ca-input", "placeholder": "Masalan: Keyinroq yechaman",
                                                  "maxlength": 80})}

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Nom kiriting.")
        return name

    def clean(self):
        if self.instance.pk is None and ProblemList.objects.filter(owner=self.owner).count() >= MAX_LISTS:
            raise forms.ValidationError(f"Ko‘pi bilan {MAX_LISTS} ta ro‘yxat.")
        return super().clean()

    def save(self, commit=True):
        if self.instance.pk is None:
            self.instance.owner = self.owner
        return super().save(commit)
