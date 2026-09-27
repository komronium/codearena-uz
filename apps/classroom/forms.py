import re

from django import forms

from apps.accounts.models import Group
from apps.contests.services import in_upcoming_contest
from apps.moderation.forms import _CA_INPUT, _MD, _DateTimeLocal
from apps.problems.models import Problem

from .models import Assignment


class AssignmentForm(forms.ModelForm):
    problems = forms.CharField(
        widget=forms.TextInput(attrs={**_CA_INPUT, "placeholder": "a-plus-b, fizzbuzz, …"}),
        help_text="Masala slug’lari, vergul bilan, kerakli tartibda. Faqat ochiq masalalar.")

    class Meta:
        model = Assignment
        fields = ["group", "title", "description_md", "start", "deadline"]
        widgets = {
            "group": forms.Select(attrs={"class": "ca-select"}),
            "title": forms.TextInput(attrs=_CA_INPUT),
            "description_md": forms.Textarea(attrs={**_MD, "rows": 3}),
            "start": _DateTimeLocal(),
            "deadline": _DateTimeLocal(),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        groups = Group.objects.order_by("name")
        self.fields["group"].queryset = groups if user.is_staff else groups.filter(teacher=user)
        if self.instance.pk and not self.is_bound:
            self.initial["problems"] = ", ".join(
                ap.problem.slug for ap in self.instance.assignment_problems.select_related("problem"))

    def clean_problems(self):
        slugs = list(dict.fromkeys(s for s in re.split(r"[\s,]+", self.cleaned_data["problems"]) if s))
        found = {p.slug: p for p in Problem.objects.filter(slug__in=slugs)}
        bad = [s for s in slugs if s not in found]
        if bad:
            raise forms.ValidationError(f"Topilmadi: {', '.join(bad)}")
        # Hidden or contest-locked problems would need a second access path for the group.
        closed = [s for s in slugs if not found[s].is_public or found[s].status != Problem.Status.APPROVED
                  or in_upcoming_contest(found[s])]
        if closed:
            raise forms.ValidationError(f"Yopiq masala (faqat ochiq masalalar mumkin): {', '.join(closed)}")
        if not slugs:
            raise forms.ValidationError("Kamida bitta masala kiriting.")
        return [found[s] for s in slugs]

    def clean(self):
        data = super().clean()
        if data.get("start") and data.get("deadline") and data["deadline"] <= data["start"]:
            self.add_error("deadline", "Muddat boshlanishdan keyin bo‘lishi kerak.")
        return data
