from django.contrib import messages
from django.core.management import CommandError, call_command
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from apps.accounts.decorators import staff_required
from apps.accounts.models import Group, User
from apps.contests.models import Contest
from apps.problems.models import Problem, Tag, TestCase
from apps.submissions.models import Submission, UserProblemSolved

from .ai import DEFAULT_MODEL, MODEL_CHOICES, AIGenerationError, generate_problem
from .forms import (
    ContestForm,
    ContestProblemFormSet,
    GroupForm,
    ProblemForm,
    SQLDatasetForm,
    TagForm,
    TestCaseFormSet,
    UserForm,
)


def _draft_to_problem_initial(draft: dict) -> dict:
    tag_ids = [Tag.objects.get_or_create(name=name.strip())[0].id
               for name in draft.get("tags", []) if name.strip()]
    return {
        "title": draft["title"], "kind": Problem.Kind.CODE,
        "statement_md": draft["statement_md"], "input_md": draft["input_md"], "output_md": draft["output_md"],
        "difficulty": draft["difficulty"], "tl_ms": draft["tl_ms"], "ml_mb": draft["ml_mb"], "points": draft["points"],
        "tags": tag_ids,
    }


def _unique_slug(title: str) -> str:
    base = slugify(title) or "masala"
    slug, n = base, 2
    while Problem.objects.filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


@staff_required
def dashboard(request):
    return render(request, "moderation/dashboard.html", {
        "counts": {
            "problems": Problem.objects.count(),
            "pending": Problem.objects.filter(status=Problem.Status.PENDING).count(),
            "contests": Contest.objects.count(),
            "users": User.objects.count(),
            "submissions": Submission.objects.count(),
            "groups": Group.objects.count(),
        },
    })


# ---- problems ----------------------------------------------------------------

@staff_required
def ai_generate(request):
    if request.method == "POST":
        prompt = request.POST.get("prompt", "").strip()
        model = request.POST.get("model", DEFAULT_MODEL)
        if model not in dict(MODEL_CHOICES):
            model = DEFAULT_MODEL
        if not prompt:
            messages.error(request, "Promt kiriting.")
            return redirect("moderation:ai_generate")
        try:
            draft = generate_problem(prompt, model)
        except AIGenerationError as e:
            messages.error(request, f"AI xato: {e}")
            return redirect("moderation:ai_generate")
        request.session["ai_draft"] = draft
        messages.success(request, "AI masalani tuzdi — tekshirib, kerak bo'lsa tahrirlab saqlang.")
        return redirect("moderation:submit")
    return render(request, "moderation/ai_generate.html", {"models": MODEL_CHOICES, "default_model": DEFAULT_MODEL})


@staff_required
def submit(request, pk=None):
    problem = get_object_or_404(Problem, pk=pk) if pk else None
    draft = request.session.pop("ai_draft", None) if problem is None and request.method == "GET" else None
    problem_initial = _draft_to_problem_initial(draft) if draft else None
    formset_initial = [{**tc, "order": i} for i, tc in enumerate(draft["testcases"])] if draft else None

    form = ProblemForm(request.POST or None, request.FILES or None, instance=problem, initial=problem_initial)
    formset = TestCaseFormSet(request.POST or None, instance=form.instance, prefix="testcases", initial=formset_initial)
    sql_form = SQLDatasetForm(request.POST or None, prefix="sql",
                              instance=getattr(problem, "sql_dataset", None) if problem else None)
    error = None
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        is_sql = form.cleaned_data["kind"] == Problem.Kind.SQL
        zipped = form.cleaned_data["tests_zip"]
        if is_sql and not sql_form.is_valid():
            error = "SQL masala uchun jadval, ma'lumot va kutilgan natija kerak."
        elif not is_sql and formset.filled_count + len(zipped) == 0:
            error = "Kamida bitta test kerak: qo'lda kiriting yoki ZIP yuklang."
        else:
            with transaction.atomic():
                obj = form.save(commit=False)
                if problem is None:
                    obj.author = request.user
                    obj.slug = _unique_slug(obj.title)
                    obj.status = Problem.Status.APPROVED
                obj.save()
                form.save_m2m()
                formset.save()
                if zipped:
                    start = obj.testcases.count()
                    TestCase.objects.bulk_create([
                        TestCase(problem=obj, input=i, expected=o, order=start + n)
                        for n, (i, o) in enumerate(zipped)
                    ])
                if is_sql:
                    dataset = sql_form.save(commit=False)
                    dataset.problem = obj
                    dataset.save()
            messages.success(request, "Masala saqlandi.")
            return redirect("problems:detail", obj.slug)
    return render(request, "moderation/submit.html",
                  {"form": form, "formset": formset, "sql_form": sql_form, "error": error, "problem": problem})


@staff_required
def problems(request):
    q = request.GET.get("q", "").strip()
    qs = Problem.objects.select_related("author").annotate(n_tests=Count("testcases")).order_by("-pk")
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(slug__icontains=q))
    page = Paginator(qs, 30).get_page(request.GET.get("page"))
    return render(request, "moderation/problems.html", {"page": page, "q": q})


@staff_required
@require_POST
def problem_toggle(request, pk):
    problem = get_object_or_404(Problem, pk=pk)
    problem.is_public = not problem.is_public
    problem.save(update_fields=["is_public"])
    return redirect("moderation:problems")


@staff_required
@require_POST
def problem_delete(request, pk):
    problem = get_object_or_404(Problem, pk=pk)
    problem.delete()
    messages.success(request, f"«{problem.title}» o'chirildi.")
    return redirect("moderation:problems")


@staff_required
def queue(request):
    problems = (Problem.objects.filter(status=Problem.Status.PENDING)
                .select_related("author").order_by("created"))
    return render(request, "moderation/queue.html", {"problems": problems})


@staff_required
@require_POST
def approve(request, pk):
    problem = get_object_or_404(Problem, pk=pk, status=Problem.Status.PENDING)
    problem.status = Problem.Status.APPROVED
    problem.is_public = True
    problem.save(update_fields=["status", "is_public"])
    return redirect("moderation:queue")


@staff_required
@require_POST
def reject(request, pk):
    problem = get_object_or_404(Problem, pk=pk, status=Problem.Status.PENDING)
    problem.status = Problem.Status.REJECTED
    problem.save(update_fields=["status"])
    return redirect("moderation:queue")


# ---- tags --------------------------------------------------------------------

@staff_required
def tags(request):
    form = TagForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("moderation:tags")
    qs = Tag.objects.annotate(n=Count("problem")).order_by("name")
    return render(request, "moderation/tags.html", {"tags": qs, "form": form})


@staff_required
@require_POST
def tag_delete(request, pk):
    get_object_or_404(Tag, pk=pk).delete()
    return redirect("moderation:tags")


# ---- contests ----------------------------------------------------------------

@staff_required
def contests(request):
    qs = Contest.objects.annotate(n_problems=Count("contest_problems", distinct=True),
                                  n_participants=Count("participations", distinct=True),
                                  n_hidden=Count("contest_problems", filter=Q(contest_problems__problem__is_public=False),
                                                 distinct=True)).order_by("-start")
    return render(request, "moderation/contests.html", {"contests": qs})


@staff_required
def contest_edit(request, pk=None):
    contest = get_object_or_404(Contest, pk=pk) if pk else None
    form = ContestForm(request.POST or None, instance=contest)
    formset = ContestProblemFormSet(request.POST or None, instance=form.instance, prefix="cp")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            contest = form.save()
            formset.instance = contest
            formset.save()
        messages.success(request, "Musobaqa saqlandi.")
        return redirect("moderation:contests")
    return render(request, "moderation/contest_form.html", {"form": form, "formset": formset, "contest": contest})


@staff_required
@require_POST
def contest_delete(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    contest.delete()
    messages.success(request, f"«{contest.title}» o'chirildi.")
    return redirect("moderation:contests")


@staff_required
@require_POST
def contest_publish(request, pk):
    """After a contest: make its problems public and turn each participant's first
    contest AC into a practice solve (points were withheld during the contest)."""
    contest = get_object_or_404(Contest, pk=pk)
    if not contest.has_ended:
        messages.error(request, "Musobaqa hali tugamagan.")
        return redirect("moderation:contests")
    granted = 0
    with transaction.atomic():
        Problem.objects.filter(contests=contest).update(is_public=True)
        acs = (Submission.objects.filter(contest=contest, verdict="AC")
               .select_related("problem").order_by("created"))
        for sub in acs:
            _, created = UserProblemSolved.objects.get_or_create(
                user_id=sub.user_id, problem=sub.problem, defaults={"first_ac_submission": sub})
            if created:
                User.objects.filter(pk=sub.user_id).update(practice_points=F("practice_points") + sub.problem.points)
                granted += 1
    messages.success(request, f"Masalalar ochildi; {granted} ta yechim amaliyot balliga o'tkazildi.")
    return redirect("moderation:contests")


@staff_required
@require_POST
def contest_apply_rating(request, pk):
    try:
        call_command("recalc_rating", pk)
        messages.success(request, "Reyting hisoblandi.")
    except CommandError as e:
        messages.error(request, f"Reyting hisoblanmadi: {e}")
    return redirect("moderation:contests")


# ---- users -------------------------------------------------------------------

@staff_required
def users(request):
    q = request.GET.get("q", "").strip()
    qs = User.objects.annotate(n_subs=Count("submissions")).order_by("-date_joined")
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(email__icontains=q) | Q(first_name__icontains=q)
                       | Q(last_name__icontains=q) | Q(school__icontains=q))
    page = Paginator(qs, 30).get_page(request.GET.get("page"))
    return render(request, "moderation/users.html", {"page": page, "q": q})


@staff_required
def user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    form = UserForm(request.POST or None, instance=user)
    if request.method == "POST" and form.is_valid():
        if user == request.user and not (form.cleaned_data["is_staff"] and form.cleaned_data["is_active"]):
            form.add_error(None, "O'zingizni admin huquqidan yoki faollikdan mahrum qila olmaysiz.")
        else:
            form.save()
            messages.success(request, "Foydalanuvchi saqlandi.")
            return redirect("moderation:users")
    return render(request, "moderation/user_form.html", {"form": form, "obj": user})


# ---- groups ------------------------------------------------------------------

@staff_required
def groups(request):
    qs = Group.objects.select_related("teacher").annotate(n=Count("members")).order_by("name")
    return render(request, "moderation/groups.html", {"groups": qs})


@staff_required
def group_edit(request, pk=None):
    group = get_object_or_404(Group, pk=pk) if pk else None
    form = GroupForm(request.POST or None, instance=group)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Guruh saqlandi.")
        return redirect("moderation:groups")
    return render(request, "moderation/group_form.html", {"form": form, "group": group})


@staff_required
@require_POST
def group_delete(request, pk):
    get_object_or_404(Group, pk=pk).delete()
    return redirect("moderation:groups")
