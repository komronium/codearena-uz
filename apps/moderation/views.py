import datetime
import os
import uuid

import django_rq
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.files.storage import default_storage
from django.core.management import CommandError, call_command
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce, TruncDate
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from apps.accounts.decorators import setter_required, staff_required
from apps.accounts.models import User
from apps.contests.models import Contest, Participation
from apps.contests.rating import recalc_official, review_queue
from apps.contests.services import reuse_reason
from apps.problems.daily import daily_candidates, daily_for, refresh_daily
from apps.problems.models import DailyProblem, Problem, Tag, TestCase
from apps.submissions.models import VERDICT_LABELS, Submission, TestResult, UserProblemSolved
from apps.submissions.solves import refresh_solves
from apps.integrity import audit
from apps.integrity.models import SimilarityFlag
from apps.learn.models import StudyPlan
from apps.learn.progress import COURSE_MAX, COURSE_MIN, plan_problem_ids
from judge.runner import run_submission

from .ai import MAX_COUNT, AIGenerationError, generate_problems
from .forms import (
    AIGenerateForm,
    ContestForm,
    ContestProblemFormSet,
    HintFormSet,
    ProblemForm,
    SQLDatasetForm,
    StudyPlanForm,
    TagForm,
    TestCaseFormSet,
    UserForm,
)
from django.utils.translation import gettext as _t
from django.utils.translation import gettext as _t


def _unique_slug(title: str) -> str:
    base = slugify(title) or _t("masala")
    slug, n = base, 2
    while Problem.objects.filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


@staff_required
@require_POST
def duel_switch(request):
    """Close the duels for the students (45 or 90 minutes, or until opened), or open them."""
    from apps.classroom import switch
    action = request.POST.get("do", "")
    if action == "open":
        switch.open_up(request.user)
        messages.success(request, "Duellar ochildi.")
    elif action in ("45", "90", "forever"):
        switch.close(request.user, None if action == "forever" else int(action))
        messages.success(request, _t("Duellar yopildi: talabalar duel sahifasini ko‘rmaydi."))
    return redirect(request.POST.get("next") if (request.POST.get("next") or "").startswith("/") else "moderation:dashboard")


@staff_required
def dashboard(request):
    from apps.classroom.switch import closed_until
    return render(request, "moderation/dashboard.html", {
        "duel_switch": closed_until(),
        "counts": {
            "problems": Problem.objects.count(),
            "pending": Problem.objects.filter(status=Problem.Status.PENDING).count(),
            "contests": Contest.objects.count(),
            "users": User.objects.count(),
            "submissions": Submission.objects.count(),
            "tags": Tag.objects.count(),
        },
        # the decisions waiting first: the newest problems in the queue, and today's problem
        "pending": list(Problem.objects.filter(status=Problem.Status.PENDING).select_related("author").order_by("-pk")[:5]),
        "daily": daily_for(),
        "activity": _activity(),
        "judge": _judge_health(),
    })


def _activity(days: int = 14) -> dict:
    """Submissions and new users per day for the dashboard: bars scaled to the busiest day."""
    today = timezone.localdate()
    first = today - datetime.timedelta(days=days - 1)
    subs = dict(Submission.objects.filter(created__date__gte=first).annotate(d=TruncDate("created"))
                .values_list("d").annotate(n=Count("pk")))
    joined = dict(User.objects.filter(date_joined__date__gte=first).annotate(d=TruncDate("date_joined"))
                  .values_list("d").annotate(n=Count("pk")))
    rows = [{"day": first + datetime.timedelta(days=i)} for i in range(days)]
    top = max([subs.get(r["day"], 0) for r in rows] + [1])
    for r in rows:
        r["subs"], r["users"] = subs.get(r["day"], 0), joined.get(r["day"], 0)
        r["pct"] = round(100 * r["subs"] / top)
    return {"rows": rows, "subs": sum(r["subs"] for r in rows), "users": sum(r["users"] for r in rows)}


def _judge_health() -> dict:
    """Is the judge keeping up: submissions waiting or running for over two minutes, and when the last verdict came."""
    stuck = Submission.objects.filter(verdict__in=[Submission.Verdict.PENDING, Submission.Verdict.RUNNING],
                                      created__lt=timezone.now() - datetime.timedelta(minutes=2))
    last = Submission.objects.exclude(verdict__in=[Submission.Verdict.PENDING, Submission.Verdict.RUNNING]).order_by("-created").first()
    return {"stuck": stuck.count(), "last": last.created if last else None}


@staff_required
def daily_problem(request):
    """Staff picker for scheduling a daily problem without changing a published day."""
    today = timezone.localdate()
    today_assignment = DailyProblem.objects.filter(date=today).select_related("problem").first()
    default_date = today + datetime.timedelta(days=1) if today_assignment else today
    raw_date = request.GET.get("date", "")
    malformed_date = False
    try:
        day = datetime.date.fromisoformat(raw_date) if raw_date else default_date
    except ValueError:
        day = default_date
        malformed_date = True
    max_date = today + datetime.timedelta(days=365)
    invalid_date = malformed_date or day < today or day > max_date
    if invalid_date:
        day = default_date

    assignment = DailyProblem.objects.filter(date=day).select_related(
        "problem", "selected_by"
    ).first()
    candidates = daily_candidates(day)
    schedule = (DailyProblem.objects.filter(
        date__gte=today, date__lte=today + datetime.timedelta(days=14)
    ).select_related("problem").order_by("date"))
    return render(request, "moderation/daily_problem.html", {
        "today": today,
        "max_date": max_date,
        "day": day,
        "assignment": assignment,
        "today_assignment": today_assignment,
        "candidates": candidates,
        "schedule": schedule,
        "invalid_date": invalid_date,
    })


@staff_required
@require_POST
def daily_problem_choose(request):
    today = timezone.localdate()
    try:
        day = datetime.date.fromisoformat(request.POST.get("date", ""))
        problem_id = int(request.POST.get("problem_id", ""))
    except (TypeError, ValueError):
        messages.error(request, _t("Sana yoki masala noto‘g‘ri tanlandi."))
        return redirect("moderation:daily_problem")

    if day < today or day > today + datetime.timedelta(days=365):
        messages.error(request, _t("Faqat bugun yoki keyingi 365 kun uchun masala tanlash mumkin."))
        return redirect("moderation:daily_problem")
    if day == today and DailyProblem.objects.filter(date=today).exists():
        messages.error(request, _t("Bugungi masala allaqachon e’lon qilingan va almashtirilmaydi."))
        return redirect("moderation:daily_problem")

    candidate_ids = {problem.pk for problem in daily_candidates(day)}
    if problem_id not in candidate_ids:
        messages.error(request, _t("Bu masala tanlov ro‘yxatida yo‘q. Sahifani yangilab, variantlardan birini tanlang."))
        return redirect(f"{reverse('moderation:daily_problem')}?date={day.isoformat()}")

    problem = Problem.objects.get(pk=problem_id)
    try:
        with transaction.atomic():
            assignment = DailyProblem.objects.select_for_update().filter(date=day).first()
            if day == timezone.localdate() and assignment:
                messages.error(request, _t("Bugungi masala tanlov paytida e’lon qilindi va endi almashtirilmaydi."))
                return redirect(f"{reverse('moderation:daily_problem')}?date={day.isoformat()}")
            if assignment:
                assignment.problem = problem
                assignment.selection_method = DailyProblem.SelectionMethod.ADMIN
                assignment.selected_by = request.user
                assignment.save(update_fields=["problem", "selection_method", "selected_by"])
            else:
                # Create rather than get_or_create: if automatic selection wins a concurrent
                # insert, keep that published choice instead of silently replacing it.
                assignment = DailyProblem.objects.create(
                    date=day,
                    problem=problem,
                    selection_method=DailyProblem.SelectionMethod.ADMIN,
                    selected_by=request.user,
                )
            audit.record(
                request, audit.Action.DAILY_SELECT,
                note=f"{day.isoformat()}: {problem.slug} — {problem.title}",
            )
    except IntegrityError:
        messages.error(request, _t("Bu sana uchun masala boshqa so‘rovda tanlandi. Sahifani yangilang."))
        return redirect(f"{reverse('moderation:daily_problem')}?date={day.isoformat()}")
    if day == today:
        # If today's assignment was still unset, account for accepted runs already made today.
        refresh_daily(problem.pk, None)
    messages.success(request, f"{day:%d.%m.%Y} kuniga «{problem.title}» tanlandi.")
    return redirect(f"{reverse('moderation:daily_problem')}?date={assignment.date.isoformat()}")


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
            messages.error(request, _t("AI xato: {e}").format(e=e))  # the form stays filled in: try again as is
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
            messages.success(request, _t("{len_drafts} ta masala tuzildi — Navbat bo'limida ko'rib chiqing va tasdiqlang.").format(len_drafts=len(drafts)))
            return redirect("moderation:queue")
    return render(request, "moderation/ai_generate.html", {"form": form, "max_count": MAX_COUNT})


@setter_required
@require_POST
def upload_image(request):
    """AJAX image upload endpoint for markdown editors (EasyMDE) and problem statements."""
    f = request.FILES.get("image")
    if not f:
        return JsonResponse({"error": "Fayl tanlanmadi."}, status=400)
    if f.size > 10 * 1024 * 1024:
        return JsonResponse({"error": _t("Rasm hajmi 10 MB dan oshmasligi kerak.")}, status=400)
    ext = os.path.splitext(f.name)[1].lower()
    if ext not in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
        return JsonResponse({"error": "Faqat rasm fayllari (PNG, JPG, GIF, WebP, SVG) ruxsat etilgan."}, status=400)

    stem = slugify(os.path.splitext(f.name)[0])[:30] or "image"
    unique_name = f"statements/{uuid.uuid4().hex[:12]}_{stem}{ext}"
    saved_path = default_storage.save(unique_name, f)
    url = default_storage.url(saved_path)
    if not url.startswith("/") and not url.startswith("http"):
        url = "/" + url
    return JsonResponse({"data": {"filePath": url}, "url": url})


@setter_required
def submit(request, pk=None):
    problem = get_object_or_404(Problem, pk=pk) if pk else None
    writer = not request.user.is_staff  # a trusted writer: their own pending or rejected problems only, never published
    if writer and problem is not None and not (problem.author_id == request.user.pk
                                               and problem.status in (Problem.Status.PENDING, Problem.Status.REJECTED)):
        raise PermissionDenied
    form = ProblemForm(request.POST or None, request.FILES or None, instance=problem)
    if writer:
        form.fields.pop("is_public")  # staff publish, writers do not
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
            error = _t("SQL masala uchun jadval, ma'lumot va kutilgan natija kerak.")
        elif not is_sql and formset.filled_count + len(zipped) == 0:
            error = _t("Kamida bitta test kerak: qo'lda kiriting yoki ZIP yuklang.")
        else:
            with transaction.atomic():
                obj = form.save(commit=False)
                if problem is None:
                    obj.author = request.user
                    obj.slug = _unique_slug(obj.title)
                    obj.status = Problem.Status.PENDING if writer else Problem.Status.APPROVED
                    if writer:
                        obj.is_public = False
                elif writer:
                    obj.status = Problem.Status.PENDING  # an edit, or a rejected one sent again, goes back to the queue
                    obj.is_public = False
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
                if problem is not None and set(form.changed_data) & set(Problem.TRANSLATABLE):
                    from apps.translations import service as translations
                    translations.stale(obj)  # the original changed: the other language waits for an admin again
                if is_sql:
                    dataset = sql_form.save(commit=False)
                    dataset.problem = obj
                    dataset.save()
            if writer:
                messages.success(request, _t("Masala adminlar ko‘rib chiqishi uchun yuborildi. Tasdiqlansa, sizning nomingiz bilan chiqadi."))
                return redirect("moderation:mine")
            messages.success(request, _t("Masala saqlandi."))
            return redirect("problems:detail", obj.slug)
    return render(request, "moderation/submit.html",
                  {"form": form, "formset": formset, "sql_form": sql_form, "error": error, "problem": problem,
                   "hint_formset": hint_formset})


@setter_required
def mine(request):
    """A writer's own problems and where each stands: waiting for the staff, published, or sent back."""
    rows = Problem.objects.filter(author=request.user).order_by("-pk")
    return render(request, "moderation/mine.html", {"problems": rows})


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
    status = request.GET.get("status", "")
    if status == "public":
        qs = qs.filter(is_public=True)
    elif status == "hidden":
        qs = qs.filter(is_public=False, status=Problem.Status.APPROVED)
    elif status == "pending":
        qs = qs.filter(status=Problem.Status.PENDING)
    elif status == "notests":
        qs = qs.filter(kind=Problem.Kind.CODE, n_tests=0)
    else:
        status = ""
    difficulty = request.GET.get("difficulty", "")
    if difficulty in Problem.Difficulty.values:
        qs = qs.filter(difficulty=difficulty)
    else:
        difficulty = ""
    page = Paginator(qs, 30).get_page(request.GET.get("page"))
    return render(request, "moderation/problems.html", {
        "page": page, "q": q, "status": status, "difficulty": difficulty,
        "difficulties": Problem.Difficulty.choices,
    })


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
            audit.record(request, audit.Action.REJUDGE, note=_t("{problem_title}: {len_ids} ta urinish").format(problem_title=problem.title, len_ids=len(ids)))
    messages.success(request, _t("{len_ids} ta urinish qayta tekshirishga yuborildi.").format(len_ids=len(ids)))
    applied = list(problem.contests.filter(rating_applied=True).values_list("title", flat=True))
    if applied:
        messages.warning(request, f"{', '.join(applied)}: reyting allaqachon hisoblangan — "
                                  "qayta tekshiruvdan keyin ham o‘zgarmaydi.")
    return redirect("moderation:problems")


def _tell_author(problem, text: str, url: str) -> None:
    """The writer hears the staff's decision in the bell (nothing for a problem the staff wrote themselves)."""
    if problem.author_id and not problem.author.is_staff:
        from apps.accounts.notifications import notify
        notify(problem.author_id, "report", f"problem:{problem.pk}:{problem.status}", text, url)


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
    _tell_author(problem, _t("«{problem_title}» masalangiz tasdiqlandi va saytda chiqdi").format(problem_title=problem.title), reverse("problems:detail", args=[problem.slug]))
    return redirect("moderation:queue")


@staff_required
@require_POST
def reject(request, pk):
    problem = get_object_or_404(Problem, pk=pk, status=Problem.Status.PENDING)
    problem.status = Problem.Status.REJECTED
    problem.save(update_fields=["status"])
    _tell_author(problem, _t("«{problem_title}» masalangiz rad etildi: tahrirlab qayta yuborishingiz mumkin").format(problem_title=problem.title), reverse("moderation:mine"))
    return redirect("moderation:queue")


# ---- tags --------------------------------------------------------------------

@staff_required
def tags(request):
    form = TagForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("moderation:tags")
    qs = Tag.objects.annotate(n=Count("problem")).prefetch_related("courses").order_by("name")
    return render(request, "moderation/tags.html", {"tags": qs, "form": form})


@staff_required
def tag_edit(request, pk):
    tag = get_object_or_404(Tag, pk=pk)
    form = TagForm(request.POST or None, instance=tag)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"«{tag.name}» saqlandi.")
        return redirect("moderation:tags")
    return render(request, "moderation/tag_form.html", {"form": form, "tag": tag, "courses": tag.courses.all()})


@staff_required
@require_POST
def tag_delete(request, pk):
    get_object_or_404(Tag, pk=pk).delete()
    return redirect("moderation:tags")


# ---- courses -----------------------------------------------------------------

@staff_required
def plans(request):
    qs = StudyPlan.objects.annotate(n_tags=Count("tags", distinct=True)).order_by("order", "id")
    open_counts = {k: len(v) for k, v in plan_problem_ids(qs, raw=True).items()}
    for p in qs:
        p.n_open = open_counts[p.pk]
    return render(request, "moderation/plans.html", {"plans": qs, "course_min": COURSE_MIN, "course_max": COURSE_MAX})


@staff_required
def plan_edit(request, pk=None):
    plan = get_object_or_404(StudyPlan, pk=pk) if pk else None
    form = StudyPlanForm(request.POST or None, instance=plan)
    if request.method == "POST" and form.is_valid():
        plan = form.save()
        messages.success(request, "Kurs saqlandi.")
        return redirect("learn:course", plan.slug)
    return render(request, "moderation/plan_form.html", {"form": form, "plan": plan})


@staff_required
@require_POST
def plan_delete(request, pk):
    plan = get_object_or_404(StudyPlan, pk=pk)
    plan.delete()  # problems and tags stay; only the course goes
    messages.success(request, _t("«{plan_title}» o‘chirildi.").format(plan_title=plan.title))
    return redirect("moderation:plans")


# ---- contests ----------------------------------------------------------------

@staff_required
def contests(request):
    # similarity flags nobody has looked at yet: the reminder before a rating that can't be taken back
    open_flags = (SimilarityFlag.objects.filter(submission_a__contest=OuterRef("pk"), reviewed=False)
                  .values("submission_a__contest").annotate(n=Count("pk")).values("n"))
    qs = Contest.objects.annotate(n_problems=Count("contest_problems", distinct=True),
                                  n_participants=Count("participations", distinct=True),
                                  n_hidden=Count("contest_problems", filter=Q(contest_problems__problem__is_public=False),
                                                 distinct=True),
                                  n_open_flags=Coalesce(Subquery(open_flags), 0)).order_by("-start")
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
            messages.error(request, _t("«{contest_title}» musobaqasida urinishlar bor — o‘chirib bo‘lmaydi.").format(contest_title=contest.title))
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
        messages.error(request, _t("Musobaqa hali tugamagan."))
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
    messages.success(request, _t("Masalalar ochildi; {granted} ta yechim amaliyot balliga o'tkazildi.").format(granted=granted))
    return redirect("moderation:contests")


@staff_required
@require_POST
def contest_apply_rating(request, pk):
    from apps.contests import jobs
    contest = get_object_or_404(Contest, pk=pk)
    if not contest.is_rated:
        messages.error(request, "Reyting hisoblanmadi: musobaqa reytingli emas.")
    elif not contest.rating_applied and not contest.has_ended:
        messages.error(request, _t("Reyting hisoblanmadi: musobaqa hali tugamagan."))
    elif contest.rating_applied:
        messages.info(request, "Bu musobaqaning reytingi allaqachon hisoblangan.")
    else:
        jobs.run(jobs.apply_rating, contest.pk)
        audit.record(request, audit.Action.RATING_APPLY, contest=contest)
        messages.success(request, _t("Reyting hisoblanmoqda: bir necha soniyadan keyin sahifani yangilang.") if settings.RQ_ASYNC
                         else "Reyting hisoblandi.")
    return redirect("moderation:contests")


@staff_required
@require_POST
def contest_make_official(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    contest.is_official = True
    contest.save(update_fields=["is_official"])
    messages.success(request, f"«{contest.title}» rasmiy musobaqa deb belgilandi.")
    return redirect("moderation:contest_official", pk=pk)


@staff_required
def contest_official(request, pk):
    """Official rating for one contest: the online top-N code check, then the apply button."""
    contest = get_object_or_404(Contest, pk=pk)
    queue = review_queue(contest)
    return render(request, "moderation/contest_official.html", {
        "contest": contest, "queue": queue,
        "pending": sum(1 for r in queue if not r["participation"].reviewed_at),
    })


@staff_required
@require_POST
def contest_review(request, pk, user_id):
    """Mark that a finisher explained their code (an explicit state, like disqualify)."""
    want = {"1": True, "0": False}.get(request.POST.get("reviewed"))
    if want is None:
        return HttpResponseBadRequest("reviewed must be 0 or 1")
    p = get_object_or_404(Participation.objects.select_related("contest", "user"), contest_id=pk, user_id=user_id)
    if bool(p.reviewed_at) != want:
        p.reviewed_at = timezone.now() if want else None
        p.save(update_fields=["reviewed_at"])
        if want:
            audit.record(request, audit.Action.OFFICIAL_REVIEW, contest=p.contest, subject=p.user)
    return redirect("moderation:contest_official", pk)


@staff_required
@require_POST
def contest_apply_official(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    if not contest.is_official or not contest.has_ended:
        messages.error(request, _t("Faqat tugagan rasmiy musobaqa uchun."))
        return redirect("moderation:contest_official", pk)
    pending = sum(1 for r in review_queue(contest) if not r["participation"].reviewed_at)
    if pending:
        messages.error(request, _t("{pending} ta ishtirokchi hali tekshirilmagan.").format(pending=pending))
        return redirect("moderation:contest_official", pk)
    with transaction.atomic():
        if contest.official_applied_at is None:
            contest.official_applied_at = timezone.now()
            contest.save(update_fields=["official_applied_at"])
        recalc_official()
        audit.record(request, audit.Action.OFFICIAL_APPLY, contest=contest)
    messages.success(request, _t("Rasmiy reyting qo‘llandi."))
    return redirect("moderation:contest_official", pk)


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
def duels(request):
    """Every duel, newest first, each player with their score: right answers and time for a quiz, the
    rating change once it's over. Filters live in the query string, like the submissions list."""
    from apps.classroom.duels import QUESTIONS, run
    from apps.classroom.models import Duel, DuelQuestion

    qs = Duel.objects.select_related("challenger", "opponent", "winner")
    f = {k: request.GET.get(k, "").strip() for k in ("user", "status", "language")}
    if f["user"]:
        qs = qs.filter(Q(challenger__username=f["user"]) | Q(opponent__username=f["user"]))
    if f["status"] in Duel.Status.values:
        qs = qs.filter(status=f["status"])
    if f["language"] in DuelQuestion.Lang.values:
        qs = qs.filter(language=f["language"])
    page = Paginator(qs.order_by(Coalesce("finished_at", "created").desc(), "-pk"), 50).get_page(request.GET.get("page"))
    now = timezone.now()
    for d in page:
        d.sides = []
        for u, delta in ((d.challenger, d.challenger_delta), (d.opponent, d.opponent_delta)):
            r = run(d, u.pk) if u and d.mode == Duel.Mode.QUIZ else None
            d.sides.append({"user": u, "delta": delta, "won": u is not None and d.winner_id == u.pk,
                            "right": r.right if r else None, "seen": len(r.answers) if r else 0,
                            "over": r is not None and r.over(now),
                            "spent": f"{r.spent(now).total_seconds():.1f}".replace(".", ",") if r and r.over(now) else ""})
    today = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
    all_duels = Duel.objects.all()
    counts = {
        "all": all_duels.count(),
        "finished": all_duels.filter(status=Duel.Status.FINISHED).count(),
        "playing": all_duels.filter(status=Duel.Status.ACTIVE).count(),
        "waiting": all_duels.filter(status=Duel.Status.PENDING).count(),
        "today": all_duels.filter(created__gte=today).count(),
        "players": len(set(all_duels.values_list("challenger_id", flat=True))
                       | set(all_duels.exclude(opponent=None).values_list("opponent_id", flat=True))),
    }
    from apps.classroom.switch import closed_until
    return render(request, "moderation/duels.html", {
        "duel_switch": closed_until(),
        "page": page, "f": f, "counts": counts, "n_questions": QUESTIONS,
        "statuses": Duel.Status.choices, "languages": DuelQuestion.Lang.choices,
    })


@staff_required
def users(request):
    q = request.GET.get("q", "").strip()
    qs = User.objects.annotate(n_subs=Count("submissions")).order_by("-date_joined")
    role = request.GET.get("role", "")
    if role == "staff":
        qs = qs.filter(is_staff=True)
    elif role == User.Role.STUDENT:
        qs = qs.filter(role=role, is_staff=False)
    else:
        role = ""
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(email__icontains=q) | Q(first_name__icontains=q)
                       | Q(last_name__icontains=q) | Q(school__icontains=q))
    sort = request.GET.get("sort", "")
    order = {"rating": ("-rating", "username"), "subs": ("-n_subs", "username"), "login": ("-last_login", "username")}.get(sort)
    if order:
        qs = qs.order_by(*order)
    else:
        sort = ""
    page = Paginator(qs, 30).get_page(request.GET.get("page"))
    return render(request, "moderation/users.html", {
        "page": page, "q": q, "role": role, "sort": sort,
    })


@staff_required
def user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    form = UserForm(request.POST or None, instance=user)
    if request.method == "POST" and form.is_valid():
        if user == request.user and not (form.cleaned_data["is_staff"] and form.cleaned_data["is_active"]):
            form.add_error(None, _t("O'zingizni admin huquqidan yoki faollikdan mahrum qila olmaysiz."))
        else:
            form.save()
            messages.success(request, _t("Foydalanuvchi saqlandi."))
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
            reason = _t("admin hisobini o‘chirib bo‘lmaydi — avval admin huquqini oling")
        # Problem.author is PROTECT
        elif user.authored_problems.exists():
            reason = _t("uning masalalari bor — avval boshqasiga o‘tkazing yoki bloklang")
        else:
            reason = None
        if reason:
            messages.error(request, f"{user.username}: {reason}.")
            return redirect("moderation:user_edit", pk)
        audit.record(request, audit.Action.USER_DELETE, note=f"#{user.pk} — {user.username} ({user.email})")
        user.delete()
    messages.success(request, _t("{user_username} o‘chirildi.").format(user_username=user.username))
    return redirect("moderation:users")
