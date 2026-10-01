import django_rq
from django.contrib import messages
from django.core.management import CommandError, call_command
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from apps.accounts.decorators import staff_required
from apps.accounts.models import Group, User
from apps.contests.models import Contest
from apps.contests.services import reuse_reason
from apps.problems.models import Problem, Tag, TestCase
from apps.submissions.models import VERDICT_LABELS, Submission, TestResult, UserProblemSolved
from apps.submissions.solves import refresh_solves
from apps.integrity import audit
from judge.runner import run_submission

from .ai import MAX_COUNT, AIGenerationError, generate_problems
from .forms import (
    AIGenerateForm,
    ContestForm,
    ContestProblemFormSet,
    GroupForm,
    HintFormSet,
    ProblemForm,
    SQLDatasetForm,
    TagForm,
    TestCaseFormSet,
    UserForm,
)


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
            "tags": Tag.objects.count(),
            "groups": Group.objects.count(),
            "teacher_requests": User.objects.filter(teacher_requested=True).count(),
        },
    })


# ---- problems ----------------------------------------------------------------

@staff_required
def ai_generate(request):
    form = AIGenerateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            drafts = generate_problems(
                form.levels(), topics=[t.name for t in form.cleaned_data["topics"]],
                focus=form.cleaned_data["focus"].strip(), model=form.cleaned_data["model"],
                allowed_tags=list(Tag.objects.filter(kind=Tag.Kind.CODE).order_by("name")
                                  .values_list("name", flat=True)))
        except AIGenerationError as e:
            messages.error(request, f"AI xato: {e}")  # the form stays filled in: try again as is
        else:
            with transaction.atomic():
                for draft in drafts:
                    tags = Tag.objects.filter(name__in=draft.get("tags", []))  # never a new topic
                    obj = Problem.objects.create(
                        title=draft["title"], slug=_unique_slug(draft["title"]), kind=Problem.Kind.CODE,
                        statement_md=draft["statement_md"], input_md=draft["input_md"], output_md=draft["output_md"],
                        difficulty=draft["difficulty"], tl_ms=draft["tl_ms"], ml_mb=draft["ml_mb"],
                        is_public=False, status=Problem.Status.PENDING, author=request.user,
                    )
                    obj.tags.set(tags)
                    TestCase.objects.bulk_create([
                        TestCase(problem=obj, input=tc["input"], expected=tc["expected"],
                                 is_sample=tc["is_sample"], order=i)
                        for i, tc in enumerate(draft["testcases"])
                    ])
            messages.success(request, f"{len(drafts)} ta masala tuzildi — Navbat bo'limida ko'rib chiqing va tasdiqlang.")
            return redirect("moderation:queue")
    return render(request, "moderation/ai_generate.html", {"form": form, "max_count": MAX_COUNT})


@staff_required
def submit(request, pk=None):
    problem = get_object_or_404(Problem, pk=pk) if pk else None
    form = ProblemForm(request.POST or None, request.FILES or None, instance=problem)
    formset = TestCaseFormSet(request.POST or None, instance=form.instance, prefix="testcases")
    # A client that doesn't send the hints block (older forms, scripts) leaves hints as they are.
    hint_data = request.POST if "hints-TOTAL_FORMS" in request.POST else None
    hint_formset = HintFormSet(hint_data, instance=form.instance, prefix="hints")
    sql_form = SQLDatasetForm(request.POST or None, prefix="sql",
                              instance=getattr(problem, "sql_dataset", None) if problem else None)
    error = None
    if (request.method == "POST" and form.is_valid() and formset.is_valid()
            and (hint_data is None or hint_formset.is_valid())):
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
                if hint_data is not None:
                    hint_formset.instance = obj
                    hint_formset.save()
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
                  {"form": form, "formset": formset, "sql_form": sql_form, "error": error, "problem": problem,
                   "hint_formset": hint_formset})


@staff_required
def problems(request):
    q = request.GET.get("q", "").strip()
    # A subquery, not a second Count join: two joins would multiply tests by submissions.
    finished = (Submission.objects.filter(problem=OuterRef("pk"), verdict__in=Submission.TERMINAL)
                .order_by().values("problem").annotate(n=Count("pk")).values("n"))
    qs = (Problem.objects.select_related("author")
          .annotate(n_tests=Count("testcases"), n_subs=Coalesce(Subquery(finished), 0)).order_by("-pk"))
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
    with transaction.atomic():
        # The row lock makes check-then-delete atomic: an insert that references the problem
        # (a submission, a contest row) takes a key-share lock on it for its FK check, so it
        # either commits first and the check sees it, or waits and then fails on the FK.
        problem = get_object_or_404(Problem.objects.select_for_update(), pk=pk)
        # A contest's record or other people's work hangs on it; hiding keeps both.
        if problem.contests.exists() or problem.submissions.exclude(user_id=problem.author_id).exists():
            messages.error(request, f"«{problem.title}» musobaqada ishlatilgan yoki unga boshqalar urinish "
                                    "yuborgan — o‘chirib bo‘lmaydi, yashirib qo‘ying.")
            return redirect("moderation:problems")
        problem.delete()
        audit.record(request, audit.Action.PROBLEM_DELETE, note=f"{problem.slug} — {problem.title}")
    messages.success(request, f"«{problem.title}» o'chirildi.")
    return redirect("moderation:problems")


@staff_required
@require_POST
def problem_rejudge(request, pk):
    """Judge every finished submission of the problem again, e.g. after its tests were
    fixed. In-flight ones are left alone. The runner then moves verdicts, solves, points
    and standings like for a fresh submission."""
    problem = get_object_or_404(Problem, pk=pk)
    with transaction.atomic():
        # The row locks make a concurrent double click find nothing left to reset.
        ids = list(Submission.objects.filter(problem=problem, verdict__in=Submission.TERMINAL)
                   .select_for_update().order_by("created", "id").values_list("pk", flat=True))
        # Reset by id, not by verdict again: a submission that finished after the SELECT is
        # not locked, and resetting it without queueing it would leave it PENDING for good.
        # ponytail: one IN list; chunk it past ~65k submissions of one problem (Postgres
        # takes at most 65535 parameters per statement).
        TestResult.objects.filter(submission_id__in=ids).delete()
        Submission.objects.filter(pk__in=ids).update(verdict=Submission.Verdict.PENDING, passed=0, total=0,
                                                     exec_ms=0, mem_kb=0, compile_log="")

        def enqueue():
            queue = django_rq.get_queue("rejudge")
            for submission_id in ids:
                queue.enqueue(run_submission, submission_id)
        transaction.on_commit(enqueue)
        if ids:
            audit.record(request, audit.Action.REJUDGE, note=f"{problem.title}: {len(ids)} ta urinish")
    messages.success(request, f"{len(ids)} ta urinish qayta tekshirishga yuborildi.")
    applied = list(problem.contests.filter(rating_applied=True).values_list("title", flat=True))
    if applied:
        messages.warning(request, f"{', '.join(applied)}: reyting allaqachon hisoblangan — "
                                  "qayta tekshiruvdan keyin ham o‘zgarmaydi.")
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
        if not contest.is_rated and not contest.has_ended:
            known = [cp.label for cp in contest.contest_problems.select_related("problem")
                     if reuse_reason(cp.problem, contest)]
            if known:
                messages.warning(request, f"{', '.join(known)}: ochiq yoki boshqa musobaqada ishlatilgan — "
                                          "ishtirokchilar bu masalalarni oldindan bilishi mumkin.")
        return redirect("moderation:contests")
    return render(request, "moderation/contest_form.html", {"form": form, "formset": formset, "contest": contest})


@staff_required
@require_POST
def contest_delete(request, pk):
    with transaction.atomic():
        # Locked like in problem_delete, so a submission can't land between check and delete.
        contest = get_object_or_404(Contest.objects.select_for_update(), pk=pk)
        # Submission.contest is SET_NULL: deleting would turn its ACs, unpublished and
        # disqualified ones included, into practice ACs that count as solves.
        if contest.submissions.exists():
            messages.error(request, f"«{contest.title}» musobaqasida urinishlar bor — o‘chirib bo‘lmaydi.")
            return redirect("moderation:contests")
        audit.record(request, audit.Action.CONTEST_DELETE, note=f"#{contest.pk} — {contest.title}")
        contest.delete()
    messages.success(request, f"«{contest.title}» o'chirildi.")
    return redirect("moderation:contests")


@staff_required
@require_POST
def contest_publish(request, pk):
    """After a contest: make its problems public and let participants' contest ACs count
    as practice solves. Disqualified participants get nothing (apps.submissions.solves).
    Publishing again keeps the first time and re-applies the rule."""
    contest = get_object_or_404(Contest, pk=pk)
    if not contest.has_ended:
        messages.error(request, "Musobaqa hali tugamagan.")
        return redirect("moderation:contests")
    with transaction.atomic():
        Problem.objects.filter(contests=contest).update(is_public=True)
        if contest.published_at is None:
            contest.published_at = timezone.now()
            contest.save(update_fields=["published_at"])
        for problem_id in contest.contest_problems.values_list("problem_id", flat=True):
            refresh_solves(problem_id)
        audit.record(request, audit.Action.PUBLISH, contest=contest)
    granted = UserProblemSolved.objects.filter(first_ac_submission__contest=contest).count()
    messages.success(request, f"Masalalar ochildi; {granted} ta yechim amaliyot balliga o'tkazildi.")
    return redirect("moderation:contests")


@staff_required
@require_POST
def contest_apply_rating(request, pk):
    try:
        call_command("recalc_rating", pk)
        audit.record(request, audit.Action.RATING_APPLY, contest=Contest.objects.get(pk=pk))
        messages.success(request, "Reyting hisoblandi.")
    except CommandError as e:
        messages.error(request, f"Reyting hisoblanmadi: {e}")
    return redirect("moderation:contests")


# ---- users -------------------------------------------------------------------

@staff_required
def submissions(request):
    """Every user's submissions, newest first; filters live in the query string so views are linkable."""
    qs = Submission.objects.select_related("user", "problem", "language", "contest").defer("source", "compile_log")
    f = {k: request.GET.get(k, "").strip() for k in ("user", "problem", "verdict", "contest")}
    if f["user"]:
        qs = qs.filter(user__username=f["user"])
    if f["problem"]:
        qs = qs.filter(problem__slug=f["problem"])
    if f["verdict"] in Submission.Verdict.values:
        qs = qs.filter(verdict=f["verdict"])
    if f["contest"].isdigit():
        qs = qs.filter(contest_id=int(f["contest"]))
    page = Paginator(qs.order_by("-pk"), 50).get_page(request.GET.get("page"))
    return render(request, "moderation/submissions.html", {
        "page": page, "f": f, "verdicts": list(VERDICT_LABELS.items()),
        "contests": Contest.objects.order_by("-start").only("id", "title")[:50],
    })


@staff_required
def users(request):
    q = request.GET.get("q", "").strip()
    requests_only = request.GET.get("requests") == "1"
    qs = User.objects.annotate(n_subs=Count("submissions")).order_by("-teacher_requested", "-date_joined")
    if requests_only:
        qs = qs.filter(teacher_requested=True)
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(email__icontains=q) | Q(first_name__icontains=q)
                       | Q(last_name__icontains=q) | Q(school__icontains=q))
    page = Paginator(qs, 30).get_page(request.GET.get("page"))
    return render(request, "moderation/users.html", {
        "page": page, "q": q, "requests_only": requests_only,
        "n_requests": User.objects.filter(teacher_requested=True).count(),
    })


@staff_required
@require_POST
def teacher_decide(request, pk):
    """Approve gives the teacher role (they then open their own groups); decline just clears the request."""
    user = get_object_or_404(User, pk=pk, teacher_requested=True)
    user.teacher_requested = False
    if request.POST.get("decision") == "approve":
        user.role = User.Role.TEACHER
        messages.success(request, f"{user.username} endi o‘qituvchi.")
    else:
        messages.info(request, f"{user.username} so‘rovi rad etildi.")
    user.save(update_fields=["teacher_requested", "role"])
    left = User.objects.filter(teacher_requested=True).exists()
    return redirect(reverse("moderation:users") + ("?requests=1" if left else ""))


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


@staff_required
@require_POST
def user_delete(request, pk):
    """Delete for good: submissions, solves, participations and the rest cascade with the
    account. Ratings already given from a contest stay as they are for everyone else."""
    with transaction.atomic():
        user = get_object_or_404(User.objects.select_for_update(), pk=pk)
        if user == request.user or user.is_staff or user.is_superuser:
            reason = "admin hisobini o‘chirib bo‘lmaydi — avval admin huquqini oling"
        # Problem.author is PROTECT and Group.teacher would cascade other people's group.
        elif user.authored_problems.exists() or user.taught_groups.exists():
            reason = "uning masalalari yoki guruhlari bor — avval boshqasiga o‘tkazing yoki bloklang"
        else:
            reason = None
        if reason:
            messages.error(request, f"{user.username}: {reason}.")
            return redirect("moderation:user_edit", pk)
        audit.record(request, audit.Action.USER_DELETE, note=f"#{user.pk} — {user.username} ({user.email})")
        user.delete()
    messages.success(request, f"{user.username} o‘chirildi.")
    return redirect("moderation:users")


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
