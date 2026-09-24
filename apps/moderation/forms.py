import re
import zipfile

from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.forms.models import BaseInlineFormSet, ModelForm
from django.utils import timezone

from apps.accounts.forms import validate_public_username
from apps.accounts.models import Group, User
from apps.contests.models import Contest, ContestProblem
from apps.problems.models import Problem, SQLDataset, Tag, TestCase

_CA_INPUT = {"class": "ca-input"}
_MD = {"class": "ca-input ca-md", "rows": 6}


class ProblemForm(ModelForm):
    tests_zip = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={"accept": ".zip", "class": "ca-input"}),
    )

    class Meta:
        model = Problem
        fields = ["title", "kind", "statement_md", "input_md", "output_md", "difficulty", "tags",
                  "tl_ms", "ml_mb", "points", "is_public"]
        widgets = {
            "title": forms.TextInput(attrs=_CA_INPUT),
            "kind": forms.Select(attrs={"class": "ca-select"}),
            "statement_md": forms.Textarea(attrs=_MD),
            "input_md": forms.Textarea(attrs={**_MD, "rows": 3}),
            "output_md": forms.Textarea(attrs={**_MD, "rows": 3}),
            "difficulty": forms.Select(attrs={"class": "ca-select"}),
            "tags": forms.SelectMultiple(attrs={"class": "ca-select", "size": 5}),
            "tl_ms": forms.NumberInput(attrs=_CA_INPUT),
            "ml_mb": forms.NumberInput(attrs=_CA_INPUT),
            "points": forms.NumberInput(attrs=_CA_INPUT),
        }

    def clean_tests_zip(self):
        f = self.cleaned_data.get("tests_zip")
        if not f:
            return []
        try:
            pairs = parse_tests_zip(f)
        except (zipfile.BadZipFile, UnicodeDecodeError) as e:
            raise ValidationError(f"ZIP o'qilmadi: {e}")
        if not pairs:
            raise ValidationError("ZIP ichida test juftligi topilmadi (masalan 01.in + 01.out).")
        return pairs


class SQLDatasetForm(ModelForm):
    class Meta:
        model = SQLDataset
        fields = ["schema_sql", "seed_sql", "expected_result"]
        widgets = {k: forms.Textarea(attrs={"class": "ca-input font-mono", "rows": 5}) for k in fields}


_IN_EXT = (".in", ".txt")
_OUT_EXT = (".out", ".ans", ".a")


def _natural_key(name: str):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", name)]


def parse_tests_zip(f) -> list[tuple[str, str]]:
    """Pairs files by stem: `01.in`+`01.out` (or .ans/.a), or `input/01.txt`+`output/01.txt`.
    Returns [(input, expected)] in natural order. Anything unpaired is ignored."""
    ins, outs = {}, {}
    with zipfile.ZipFile(f) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            path = info.filename.lower()
            folder, _, base = path.rpartition("/")
            stem, dot, ext = base.rpartition(".")
            ext = f".{ext}" if dot else ""
            out_dir = folder.endswith(("output", "outputs", "out", "answers"))
            in_dir = folder.endswith(("input", "inputs", "in"))
            if ext in _OUT_EXT or out_dir:
                outs[stem] = z.read(info).decode("utf-8")
            elif ext in _IN_EXT or in_dir:
                ins[stem] = z.read(info).decode("utf-8")
    return [(ins[k], outs[k]) for k in sorted(ins.keys() & outs.keys(), key=_natural_key)]


class BaseTestCaseFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        self.filled_count = sum(
            1 for f in self.forms
            if not f.cleaned_data.get("DELETE") and f.cleaned_data.get("input", "").strip()
            and f.cleaned_data.get("expected", "").strip()
        )


TestCaseFormSet = inlineformset_factory(
    Problem, TestCase, formset=BaseTestCaseFormSet,
    fields=["input", "expected", "is_sample", "order"], extra=2, can_delete=True,
    widgets={
        "input": forms.Textarea(attrs={"rows": 3, "class": "ca-input font-mono"}),
        "expected": forms.Textarea(attrs={"rows": 3, "class": "ca-input font-mono"}),
        "order": forms.NumberInput(attrs={"class": "ca-input w-20"}),
    },
)


class _DateTimeLocal(forms.DateTimeInput):
    input_type = "datetime-local"

    def __init__(self, **kw):
        super().__init__(attrs=_CA_INPUT, format="%Y-%m-%dT%H:%M", **kw)


class ContestForm(ModelForm):
    class Meta:
        model = Contest
        fields = ["title", "description_md", "start", "end", "is_rated", "allowed_ip_prefix", "require_group"]
        widgets = {
            "title": forms.TextInput(attrs=_CA_INPUT),
            "description_md": forms.Textarea(attrs={**_MD, "rows": 4}),
            "start": _DateTimeLocal(),
            "end": _DateTimeLocal(),
            "allowed_ip_prefix": forms.TextInput(attrs={**_CA_INPUT, "placeholder": "masalan 10.0."}),
            "require_group": forms.Select(attrs={"class": "ca-select"}),
        }

    def clean(self):
        data = super().clean()
        if data.get("start") and data.get("end") and data["end"] <= data["start"]:
            self.add_error("end", "Tugash vaqti boshlanishdan keyin bo'lishi kerak.")
        elif self.instance.pk is None and data.get("end") and data["end"] <= timezone.now():
            self.add_error("end", "Tugash vaqti allaqachon o'tib ketgan — sana va yilni tekshiring.")
        return data


ContestProblemFormSet = inlineformset_factory(
    Contest, ContestProblem, fields=["label", "problem", "points", "order"], extra=1, can_delete=True,
    widgets={
        "label": forms.TextInput(attrs={"class": "ca-input w-16 text-center", "maxlength": 2}),
        "problem": forms.Select(attrs={"class": "ca-select"}),
        "points": forms.NumberInput(attrs={"class": "ca-input w-24"}),
        "order": forms.NumberInput(attrs={"class": "ca-input w-20"}),
    },
)


class UserForm(ModelForm):
    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name", "role", "is_staff", "is_active",
                  "rating", "practice_points", "school", "location"]
        widgets = {
            **{k: forms.TextInput(attrs=_CA_INPUT) for k in ["username", "first_name", "last_name", "school", "location"]},
            "email": forms.EmailInput(attrs=_CA_INPUT),
            "role": forms.Select(attrs={"class": "ca-select"}),
            "rating": forms.NumberInput(attrs=_CA_INPUT),
            "practice_points": forms.NumberInput(attrs=_CA_INPUT),
        }

    def clean_username(self):
        return validate_public_username(self.cleaned_data["username"])


class GroupForm(ModelForm):
    class Meta:
        model = Group
        fields = ["name", "teacher", "members"]
        widgets = {
            "name": forms.TextInput(attrs=_CA_INPUT),
            "teacher": forms.Select(attrs={"class": "ca-select"}),
            "members": forms.SelectMultiple(attrs={"class": "ca-select", "size": 12}),
        }

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["teacher"].queryset = User.objects.filter(is_staff=True).order_by("username")
        self.fields["members"].queryset = User.objects.order_by("username")


class TagForm(ModelForm):
    class Meta:
        model = Tag
        fields = ["name"]
        widgets = {"name": forms.TextInput(attrs={**_CA_INPUT, "placeholder": "yangi mavzu (inglizcha)"})}
