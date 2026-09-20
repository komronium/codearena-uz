from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.forms.models import BaseInlineFormSet, ModelForm

from apps.problems.models import Problem, TestCase

_CA_INPUT = {"class": "ca-input"}


class ProblemForm(ModelForm):
    class Meta:
        model = Problem
        fields = ["title", "statement_md", "difficulty", "tl_ms", "ml_mb", "points"]
        widgets = {
            "title": forms.TextInput(attrs=_CA_INPUT),
            "statement_md": forms.Textarea(attrs={**_CA_INPUT, "rows": 8}),
            "difficulty": forms.Select(attrs={"class": "ca-select"}),
            "tl_ms": forms.NumberInput(attrs=_CA_INPUT),
            "ml_mb": forms.NumberInput(attrs=_CA_INPUT),
            "points": forms.NumberInput(attrs=_CA_INPUT),
        }


class BaseTestCaseFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        filled = [
            f for f in self.forms
            if not f.cleaned_data.get("DELETE") and f.cleaned_data.get("input", "").strip()
            and f.cleaned_data.get("expected", "").strip()
        ]
        if not filled:
            raise ValidationError("Kamida bitta test case kerak (input va expected to'ldirilgan).")


TestCaseFormSet = inlineformset_factory(
    Problem, TestCase, formset=BaseTestCaseFormSet,
    fields=["input", "expected", "is_sample", "order"], extra=3, can_delete=True,
    widgets={
        "input": forms.Textarea(attrs={**_CA_INPUT, "rows": 3, "class": "ca-input font-mono"}),
        "expected": forms.Textarea(attrs={**_CA_INPUT, "rows": 3, "class": "ca-input font-mono"}),
        "order": forms.NumberInput(attrs={"class": "ca-input w-20"}),
    },
)
