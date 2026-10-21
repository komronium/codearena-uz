import re
import zipfile

from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.forms.models import BaseInlineFormSet, ModelForm
from django.utils import timezone

from apps.accounts.countries import COUNTRY_CHOICES
from apps.accounts.forms import validate_public_username
from apps.accounts.models import User
from apps.contests.models import MIN_POINTS, Contest, ContestProblem
from apps.contests.services import reuse_reason
from apps.learn.models import RESERVED_SLUGS, StudyPlan
from apps.problems.models import MAX_HINT_PCT, Problem, ProblemHint, SQLDataset, Tag, TestCase
from judge import sql_judge

from .ai import DEFAULT_LEVELS, DEFAULT_MODEL, MAX_COUNT, MODEL_CHOICES
from django.utils.translation import gettext as _t, gettext_lazy as _tl

_CA_INPUT = {"class": "ca-input"}
_MD = {"class": "ca-input ca-md", "rows": 6}


class _SourceLang:
    """The language the author writes in: optional on the form (an older client that doesn't send it keeps the current one)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "source_lang" in self.fields:
            self.fields["source_lang"].required = False
            self.fields["source_lang"].widget.attrs.setdefault("class", "ca-select")

    def clean_source_lang(self):
        return self.cleaned_data.get("source_lang") or getattr(self.instance, "source_lang", None) or "uz"


class ProblemForm(_SourceLang, ModelForm):
    # A reference solution is checked against every test before saving; it is not stored.
    ref_lang = forms.ChoiceField(required=False, widget=forms.Select(attrs={"class": "ca-select"}))
    ref_source = forms.CharField(required=False, widget=forms.Textarea(attrs={**_CA_INPUT, "rows": 8, "class": "ca-input font-mono",
                                                                         "spellcheck": "false"}))
    tests_zip = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={"accept": ".zip", "class": "ca-input"}),
    )

    class Meta:
        model = Problem
        fields = ["source_lang", "title", "kind", "statement_md", "statement_image", "input_md", "output_md", "difficulty", "rating_guess", "tags",
                  "tl_ms", "ml_mb", "is_public", "editorial_md"]
        widgets = {
            "source_lang": forms.Select(attrs={"class": "ca-select"}),
            "title": forms.TextInput(attrs=_CA_INPUT),
            "kind": forms.Select(attrs={"class": "ca-select"}),
            "statement_md": forms.Textarea(attrs=_MD),
            "statement_image": forms.ClearableFileInput(attrs={"accept": "image/*", "class": "sr-only"}),
            "input_md": forms.Textarea(attrs={**_MD, "rows": 3}),
            "output_md": forms.Textarea(attrs={**_MD, "rows": 3}),
            "editorial_md": forms.Textarea(attrs={**_MD, "rows": 5}),
            "difficulty": forms.Select(attrs={"class": "ca-select"}),
            "rating_guess": forms.NumberInput(attrs={**_CA_INPUT, "min": 100, "max": 3500, "step": 100}),
            "tags": forms.CheckboxSelectMultiple,
            "tl_ms": forms.NumberInput(attrs=_CA_INPUT),
            "ml_mb": forms.NumberInput(attrs=_CA_INPUT),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.problems.models import Language
        self.fields["ref_lang"].choices = [("", "—")] + list(Language.objects.filter(is_active=True).values_list("code", "name"))
        if not self.instance.pk:
            # a new problem starts hidden: publishing is a choice, a contest problem must never leak by default
            self.fields["is_public"].initial = False

    def clean_statement_image(self):
        img = self.cleaned_data.get("statement_image")
        if not img or not hasattr(img, "size"):
            return img
        if img.size > 10 * 1024 * 1024:
            raise ValidationError(_t("Rasm hajmi 10 MB dan oshmasligi kerak."))
        return img

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
        fields = ["schema_sql", "seed_sql", "expected_result", "check_seed_sql", "check_expected_result", "ordered"]
        widgets = {k: forms.Textarea(attrs={"class": "ca-input font-mono", "rows": 5}) for k in fields[:-1]}

    def clean(self):
        data = super().clean()
        schema = data.get("schema_sql", "")
        # Load both data sets here, so a typo in them is the author's error now, not every student's RE later.
        for field in ("seed_sql", "check_seed_sql"):
            if data.get(field, "").strip():
                try:
                    sql_judge.tables(schema, data[field])
                except sql_judge.SQLJudgeError as exc:
                    self.add_error(field, f"SQL xatosi: {exc}")
        if data.get("check_seed_sql", "").strip() and not data.get("check_expected_result", "").strip():
            self.add_error("check_expected_result", _t("Yashirin ma‘lumotlar uchun kutilgan natija kerak."))
        return data


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


class ContestForm(_SourceLang, ModelForm):
    class Meta:
        model = Contest
        fields = ["source_lang", "title", "description_md", "start", "end", "type", "is_rated", "division",
                  "allowed_ip_prefix", "badge", "personal_minutes", "auto_finish", "blind"]
        widgets = {
            "personal_minutes": forms.NumberInput(attrs={**_CA_INPUT, "min": 0, "max": 1440, "placeholder": _tl("0 — hamma uchun bir soat")}),
            "title": forms.TextInput(attrs=_CA_INPUT),
            "description_md": forms.Textarea(attrs={**_MD, "rows": 4}),
            "start": _DateTimeLocal(),
            "end": _DateTimeLocal(),
            "allowed_ip_prefix": forms.TextInput(attrs={**_CA_INPUT, "placeholder": "masalan 10.0."}),
            "badge": forms.TextInput(attrs={**_CA_INPUT, "placeholder": "masalan Marathon #1"}),
            "division": forms.Select(attrs={"class": "ca-select"}),
            "type": forms.Select(attrs={"class": "ca-select"}),
        }

    authors_text = forms.CharField(required=False, label=_tl("Mualliflar"), widget=forms.TextInput(attrs={
        **_CA_INPUT, "placeholder": _tl("login, login … (tanlovdan tashqari qatnashadi)")}))

    # what a trusted writer may set on the draft round they prepare; everything else is the staff's
    WRITER_FIELDS = ("source_lang", "title", "description_md", "start", "end", "type")

    def __init__(self, *args, writer=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.writer = writer
        self.authors_changed = False
        if writer:
            for name in [n for n in self.fields if n not in self.WRITER_FIELDS]:
                del self.fields[name]
            self.fields["type"].required = False
            if self.instance.pk is None:
                self.initial.setdefault("type", Contest.Type.CF)
            return
        if self.instance.pk:
            self.initial["authors_text"] = ", ".join(self.instance.authors.values_list("username", flat=True))
        if self.instance.pk and self.instance.has_started:
            # what the round was rated and ranked by stays as it was played
            for name in ("is_rated", "division", "personal_minutes"):
                self.fields[name].disabled = True
        self.fields["division"].required = False
        self.fields["type"].required = False
        if self.instance.pk is None:
            self.initial.setdefault("type", Contest.Type.CF)  # new rounds run on Codeforces' rules
        elif self.instance.has_started:
            # the rules rank the board: switching them would reorder a contest already played
            self.fields["type"].disabled = True

    def clean(self):
        data = super().clean()
        if data.get("start") and data.get("end") and data["end"] <= data["start"]:
            self.add_error("end", _t("Tugash vaqti boshlanishdan keyin bo'lishi kerak."))
        elif self.instance.pk is None and data.get("end") and data["end"] <= timezone.now():
            self.add_error("end", _t("Tugash vaqti allaqachon o'tib ketgan — sana va yilni tekshiring."))
        return data

    def clean_authors_text(self):
        names = [n for n in re.split(r"[,\s]+", self.cleaned_data.get("authors_text") or "") if n]
        found = {n: User.objects.filter(username__iexact=n).first() for n in names}
        missing = [n for n, u in found.items() if u is None]
        if missing:
            raise forms.ValidationError(_t("Bunday foydalanuvchi yo‘q: {names}").format(names=", ".join(missing)))
        return list({u.pk: u for u in found.values()}.values())

    def save(self, commit=True):
        contest = super().save(commit)

        def authors():
            if self.writer:
                return
            new = {u.pk for u in self.cleaned_data.get("authors_text") or []}
            self.authors_changed = bool(contest.pk) and {u for u in contest.authors.values_list("pk", flat=True)} != new
            contest.authors.set(new)

        if commit:
            authors()
        else:
            old = self.save_m2m
            self.save_m2m = lambda: (old(), authors())
        return contest

    def clean_type(self):
        # left out (an older form) = the rules it has, Codeforces' for a new contest
        return self.cleaned_data.get("type") or (self.instance.type if self.instance.pk else Contest.Type.CF)

    def clean_division(self):
        value = self.cleaned_data.get("division")
        return Contest.Division.OPEN if value is None else value


class BaseContestProblemFormSet(BaseInlineFormSet):
    def add_fields(self, form, index):
        super().add_fields(form, index)
        field = form.fields["problem"]
        if self.problem_queryset is not None:
            field.queryset = self.problem_queryset
        else:
            field.queryset = Problem.objects.order_by("title")
        used = self._used_ids()
        # the picker's rows say how hard a problem is and whether it was used before; the form's script filters them as you type
        field.label_from_instance = lambda p: (f"{p.title} · {p.get_difficulty_display()}"
                                               + (_t(" · ishlatilgan") if p.pk in used else ""))

    problem_queryset = None

    def _used_ids(self):
        if not hasattr(self, "_used"):
            others = ContestProblem.objects.all()
            if self.instance.pk:
                others = others.exclude(contest=self.instance)
            self._used = set(others.values_list("problem_id", flat=True))
        return self._used

    def clean(self):
        super().clean()
        contest = self.instance  # contest_edit validates ContestForm first, which copies the POSTed values here
        if any(self.errors) or not contest.is_rated or contest.end is None:
            return
        # Only a rated contest that had already ended and stays ended is skipped: publishing
        # made its problems public. Judge by the stored row too, so moving `end` into the
        # past, reopening, or turning `is_rated` on after the end can't skip the check.
        now = timezone.now()
        stored = Contest.objects.filter(pk=contest.pk).values("is_rated", "end").first() if contest.pk else None
        if stored and stored["is_rated"] and stored["end"] <= now and contest.end <= now:
            return
        for form in self.forms:
            problem = form.cleaned_data.get("problem")
            if problem is None or form.cleaned_data.get("DELETE"):
                continue
            reason = reuse_reason(problem, contest)
            if reason:
                form.add_error("problem", reason)


HintFormSet = inlineformset_factory(
    Problem, ProblemHint, fields=["order", "body_md", "cost_pct"], extra=1, can_delete=True,
    widgets={
        "order": forms.NumberInput(attrs={"class": "ca-input w-20"}),
        "body_md": forms.Textarea(attrs={**_MD, "rows": 2}),
        "cost_pct": forms.NumberInput(attrs={"class": "ca-input w-24", "min": 0, "max": MAX_HINT_PCT}),
    },
)


ContestProblemFormSet = inlineformset_factory(
    Contest, ContestProblem, formset=BaseContestProblemFormSet,
    fields=["label", "problem", "points", "order"], extra=1, can_delete=True,
    widgets={
        "label": forms.TextInput(attrs={"class": "ca-input w-16 text-center", "maxlength": 2}),
        "problem": forms.Select(attrs={"class": "ca-select"}),
        "points": forms.NumberInput(attrs={"class": "ca-input w-24", "min": MIN_POINTS, "step": 50}),
        "order": forms.NumberInput(attrs={"class": "ca-input w-20"}),
    },
)


class UserForm(ModelForm):
    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name", "role", "is_staff", "is_setter", "is_active",
                  "rating", "school", "country", "location"]
        widgets = {
            "country": forms.Select(attrs={"class": "ca-select"}, choices=[("", "—")] + COUNTRY_CHOICES),
            **{k: forms.TextInput(attrs=_CA_INPUT) for k in ["username", "first_name", "last_name", "school", "location"]},
            "email": forms.EmailInput(attrs=_CA_INPUT),
            "role": forms.Select(attrs={"class": "ca-select"}),
            "rating": forms.NumberInput(attrs=_CA_INPUT),
        }

    def clean_username(self):
        return validate_public_username(self.cleaned_data["username"])


class TagForm(ModelForm):
    class Meta:
        model = Tag
        fields = ["name", "kind"]
        widgets = {"name": forms.TextInput(attrs={**_CA_INPUT, "placeholder": "masalan: two-pointers"}),
                   "kind": forms.Select(attrs={"class": "ca-select"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["kind"].required = False  # left out: a programming topic

    def clean_kind(self):
        return self.cleaned_data.get("kind") or Tag.Kind.CODE

    def clean_name(self):
        # One standard English spelling per topic; free text is how "sikl", "cikl" and "loop" piled up.
        name = self.cleaned_data["name"].strip().lower()
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name):
            raise ValidationError(_t("Inglizcha nom, kichik harflar va chiziqcha bilan: masalan, two-pointers."))
        return name


class AIGenerateForm(forms.Form):
    """What the AI drafts: how many problems per level, on which topics, and optionally
    one precise theme."""
    topics = forms.ModelMultipleChoiceField(Tag.objects.filter(kind=Tag.Kind.CODE).order_by("name"),
                                            to_field_name="name", required=False,
                                            widget=forms.CheckboxSelectMultiple)
    focus = forms.CharField(required=False, max_length=500, widget=forms.Textarea(attrs={
        "class": "ca-input", "rows": 3,
        "placeholder": "Masalan: bozordagi narxlar, Fibonachchi sonlari, 1 ≤ n ≤ 10⁵"}))
    model = forms.ChoiceField(choices=MODEL_CHOICES, initial=DEFAULT_MODEL,
                              widget=forms.Select(attrs={"class": "ca-select"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for value, label in Problem.Difficulty.choices:
            self.fields[f"n_{value}"] = forms.IntegerField(
                label=label, min_value=0, max_value=MAX_COUNT, required=False, initial=DEFAULT_LEVELS.get(value, 0),
                widget=forms.NumberInput(attrs={"class": "ca-input tabular", "data-level-count": ""}))

    def count_fields(self):
        return [(value, self[f"n_{value}"]) for value in Problem.Difficulty.values]

    def levels(self) -> dict[str, int]:
        return {value: self.cleaned_data.get(f"n_{value}") or 0 for value in Problem.Difficulty.values}

    def clean(self):
        cleaned = super().clean()
        if not 1 <= sum(self.levels().values()) <= MAX_COUNT:
            raise ValidationError(_t("Jami 1 dan {max_count} tagacha masala so‘rang.").format(max_count=MAX_COUNT))
        return cleaned


# ---- courses -----------------------------------------------------------------

class StudyPlanForm(_SourceLang, ModelForm):
    """A course: its problems are every open problem carrying any of the chosen tags."""
    class Meta:
        model = StudyPlan
        fields = ["source_lang", "title", "slug", "stage", "order", "level", "icon", "summary", "theory_md", "description_md",
                  "tags", "is_public"]
        widgets = {
            **{k: forms.TextInput(attrs=_CA_INPUT) for k in ["title", "slug", "summary"]},
            **{k: forms.Select(attrs={"class": "ca-select"}) for k in ["stage", "level", "icon"]},
            "theory_md": forms.Textarea(attrs={**_MD, "rows": 18}),
            "description_md": forms.Textarea(attrs={**_MD, "rows": 3}),
            "order": forms.NumberInput(attrs=_CA_INPUT),
            "tags": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tags"].queryset = Tag.objects.order_by("kind", "name")

    def clean_slug(self):
        slug = self.cleaned_data["slug"]
        if slug in RESERVED_SLUGS:
            raise ValidationError(_t("Bu nom band (O‘rganish bo‘limidagi sahifa). Boshqa slug tanlang."))
        return slug
