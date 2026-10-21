import datetime
import os
import time
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
from django.utils.translation import gettext as _t, gettext_lazy as _tl
from django.views.decorators.http import require_POST

from apps.accounts.decorators import setter_required, staff_required
from apps.accounts.models import User
from apps.contests.models import Contest, Participation
from apps.contests import rating
from apps.contests.services import blind_problem_ids, reuse_reason
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
def rating_stats(request):
    """Reyting statistikasi: the contest rating and the duel rating today, what is coming and the pace."""
    from . import rating_stats as stats
    return render(request, "moderation/rating_stats.html", {"cr": stats.contest_rating(), "dr": stats.duel_rating()})


@staff_required
def search(request):
    """The command palette's staff results: people, problems and rounds that match, each a link to the staff page."""
    q = request.GET.get("q", "").strip()[:60]
    if len(q) < 2:
        return JsonResponse({"results": []})
    out = []
    for u in User.objects.filter(Q(username__icontains=q) | Q(email__icontains=q)).order_by("username")[:5]:
        out.append({"label": u.username, "hint": u.email or "", "icon": "user", "url": reverse("moderation:user_edit", args=[u.pk])})
    blind = blind_problem_ids(request.user)
    for p in Problem.objects.filter(Q(title__icontains=q) | Q(slug__icontains=q)).exclude(pk__in=blind).order_by("-pk")[:5]:
        out.append({"label": p.title, "hint": f"#{p.pk:04d}", "icon": "file-code-2", "url": reverse("moderation:problem_edit", args=[p.pk])})
    for c in Contest.objects.filter(title__icontains=q).order_by("-start")[:4]:
        out.append({"label": c.title, "hint": f"#{c.pk}", "icon": "trophy", "url": reverse("moderation:contest_edit", args=[c.pk])})
    return JsonResponse({"results": out})


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
        "todo": _staff_todo_fresh(),
        "next_round": (Contest.objects.filter(is_draft=False, start__gt=timezone.now()).order_by("start").first()),
    })


def _staff_todo_fresh() -> dict:
    """The waiting work, counted now (the menu's counters are cached for half a minute)."""
    from django.core.cache import cache
    cache.delete("nav-staff-todo")
    from apps.home.context_processors import _staff_todo
    return _staff_todo()


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
    """Is the judge keeping up: submissions waiting or running for over two minutes (of the last day: an old leftover is not
    an alarm), when the last verdict came, how many workers are alive and what waits in the queues."""
    now = timezone.now()
    stuck = Submission.objects.filter(verdict__in=[Submission.Verdict.PENDING, Submission.Verdict.RUNNING],
                                      created__lt=now - datetime.timedelta(minutes=2),
                                      created__gte=now - datetime.timedelta(days=1))
    last = Submission.objects.exclude(verdict__in=[Submission.Verdict.PENDING, Submission.Verdict.RUNNING]).order_by("-created").first()
    workers, queued = None, {}
    try:
        from rq import Worker
        for name in ("default", "run", "rejudge"):
            queue = django_rq.get_queue(name)
            queued[name] = queue.count
            if workers is None:
                workers = Worker.count(queue=queue)
    except Exception:  # noqa: BLE001 - Redis down is itself the answer
        workers = None
    return {"stuck": stuck.count(), "last": last.created if last else None, "workers": workers, "queued": queued,
            "rejudge": queued.get("rejudge", 0)}


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
    by_day = {row.date: row for row in schedule}
    calendar = [{"date": today + datetime.timedelta(days=i), "row": by_day.get(today + datetime.timedelta(days=i))} for i in range(15)]
    q = request.GET.get("q", "").strip()[:60]
    from apps.problems.skills import open_problems
    found = (list(open_problems().filter(Q(title__icontains=q) | Q(slug__icontains=q)).order_by("-pk")[:8])
             if len(q) >= 2 and not blind_problem_ids(request.user) else [])
    return render(request, "moderation/daily_problem.html", {
        "calendar": calendar, "q": q, "found": found,
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
    swap = request.user.is_superuser and request.POST.get("swap") == "1"  # an emergency swap of a broken problem
    if day == today and DailyProblem.objects.filter(date=today).exists() and not swap:
        messages.error(request, _t("Bugungi masala allaqachon e’lon qilingan va almashtirilmaydi."))
        return redirect("moderation:daily_problem")

    candidate_ids = {problem.pk for problem in daily_candidates(day)}
    from apps.problems.skills import open_problems
    if request.POST.get("custom") == "1":  # a problem found by search: any open problem will do
        candidate_ids |= set(open_problems().filter(pk=problem_id).values_list("pk", flat=True))
    if problem_id not in candidate_ids:
        messages.error(request, _t("Bu masala tanlov ro‘yxatida yo‘q. Sahifani yangilab, variantlardan birini tanlang."))
        return redirect(f"{reverse('moderation:daily_problem')}?date={day.isoformat()}")

    problem = Problem.objects.get(pk=problem_id)
    try:
        with transaction.atomic():
            assignment = DailyProblem.objects.select_for_update().filter(date=day).first()
            if day == timezone.localdate() and assignment and not swap:
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
                request, audit.Action.DAILY_SWAP if swap else audit.Action.DAILY_SELECT,
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


@staff_required
@require_POST
def daily_problem_clear(request):
    """Take back a pick for a coming day: the site chooses that day by itself again."""
    try:
        day = datetime.date.fromisoformat(request.POST.get("date", ""))
    except ValueError:
        return redirect("moderation:daily_problem")
    if day > timezone.localdate():
        row = DailyProblem.objects.filter(date=day).first()
        if row:
            audit.record(request, audit.Action.DAILY_SELECT, note=f"{day.isoformat()}: {_t('tanlov bekor qilindi')} ({row.problem.slug})")
            row.delete()
            messages.success(request, _t("{d} uchun tanlov bekor qilindi.").format(d=day.strftime("%d.%m.%Y")))
    return redirect(f"{reverse('moderation:daily_problem')}?date={day.isoformat()}")


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
    if ext not in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:  # no SVG: a script inside one would run from the site's own address
        return JsonResponse({"error": _t("Faqat rasm fayllari (PNG, JPG, GIF, WebP) ruxsat etilgan.")}, status=400)
    try:  # the bytes must really be an image, whatever the name says
        from PIL import Image
        Image.open(f).verify()
        f.seek(0)
    except Exception:  # noqa: BLE001
        return JsonResponse({"error": _t("Fayl rasm emas yoki buzilgan.")}, status=400)
    from django.core.cache import cache
    key = f"upload:{request.user.pk}:{timezone.localdate()}"
    cache.add(key, 0, 86400)
    if cache.incr(key) > 60:  # a day's quota of uploads per person
        return JsonResponse({"error": _t("Bugungi rasm yuklash chegarasi tugadi.")}, status=429)

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
    if problem is not None and problem.pk in blind_problem_ids(request.user):
        raise PermissionDenied  # a blind round's problem: not for staff who did not write the round, until it ends
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
        elif (not is_sql and not writer and form.cleaned_data.get("is_public")
              and formset.filled_count + len(zipped) < 2):
            error = _t("Ochiq masala uchun kamida 2 ta test kerak: bitta test bilan noto‘g‘ri yechim ham o‘tib ketishi mumkin.")
        else:
            error = _check_reference(form, formset, zipped, is_sql)
        if error:
            pass
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
                tests_changed = problem is not None and (formset.has_changed() or bool(zipped))
                if tests_changed and obj.submissions.filter(verdict__in=Submission.TERMINAL).exists():
                    if request.POST.get("rejudge") == "1":
                        n = _rejudge(request, obj)
                        messages.info(request, _t("Testlar o‘zgardi: {n} ta urinish qayta tekshirishga yuborildi.").format(n=n))
                    else:
                        messages.warning(request, _t("Testlar o‘zgardi, lekin mavjud urinishlar eski testlar bilan baholangan: «Qayta tekshirish» ni bosing."))
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


def _check_reference(form, formset, zipped, is_sql) -> str | None:
    """Run the optional reference solution on every test of the form; an error text when it does not pass them all."""
    source = (form.cleaned_data.get("ref_source") or "").strip()
    if not source or is_sql:
        return None
    lang = form.cleaned_data.get("ref_lang")
    if not lang:
        return _t("Namunaviy yechim uchun tilni tanlang.")
    tests = [(f.cleaned_data["input"], f.cleaned_data["expected"]) for f in formset.forms
             if f.cleaned_data and not f.cleaned_data.get("DELETE") and f.cleaned_data.get("expected", "").strip() != ""]
    tests += list(zipped)
    if not tests:
        return None
    from judge.runner import run_trial
    args = (lang, source, [t[0] for t in tests], [t[1] for t in tests],
            form.cleaned_data.get("tl_ms") or 1000, form.cleaned_data.get("ml_mb") or 64)
    if settings.RQ_ASYNC:
        job = django_rq.get_queue("run").enqueue(run_trial, *args, result_ttl=120, failure_ttl=120)
        deadline = time.monotonic() + 60
        while job.get_status() not in ("finished", "failed", "stopped", "canceled") and time.monotonic() < deadline:
            time.sleep(0.4)
        if job.get_status() != "finished":
            return _t("Namunaviy yechim vaqtida tekshirilmadi: tekshiruvchi band. Keyinroq urinib ko‘ring.")
        result = job.return_value()
    else:
        result = run_trial(*args)
    if result["verdict"] == "CE":
        return _t("Namunaviy yechim kompilyatsiya bo‘lmadi: {log}").format(log=result["log"][:300])
    bad = [i + 1 for i, c in enumerate(result["cases"]) if c["verdict"] != "AC"]
    if bad:
        return _t("Namunaviy yechim {n} ta testdan o‘tmadi (test raqami: {nums}). Test yoki yechimni tekshiring.").format(
            n=len(bad), nums=", ".join(map(str, bad[:8])))
    return None


def _rejudge(request, problem) -> int:
    """Queue every finished submission of the problem again; how many were queued."""
    with transaction.atomic():
        ids = list(Submission.objects.filter(problem=problem, verdict__in=Submission.TERMINAL)
                   .select_for_update().order_by("created", "id").values_list("pk", flat=True))
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
    return len(ids)


@setter_required
def mine(request):
    """A writer's own problems and where each stands: waiting for the staff, published, or sent back."""
    rows = Problem.objects.filter(author=request.user).order_by("-pk")
    return render(request, "moderation/mine.html", {"problems": rows})


SORTS = {"new": "-pk", "old": "pk", "solved": "-n_solved", "tests": "-n_tests", "title": "title"}


@staff_required
def problems(request):
    q = request.GET.get("q", "").strip()
    # A subquery, not a second Count join: two joins would multiply tests by submissions.
    finished = (Submission.objects.filter(problem=OuterRef("pk"), verdict__in=Submission.TERMINAL)
                .order_by().values("problem").annotate(n=Count("pk")).values("n"))
    solved = (UserProblemSolved.objects.filter(problem=OuterRef("pk")).order_by().values("problem")
              .annotate(n=Count("pk")).values("n"))
    qs = (Problem.objects.select_related("author").prefetch_related("tags")
          .annotate(n_tests=Count("testcases", distinct=True), n_subs=Coalesce(Subquery(finished), 0),
                    n_solved=Coalesce(Subquery(solved), 0)))
    blind = blind_problem_ids(request.user)
    if blind:  # a blind round's problems are not for these eyes yet
        qs = qs.exclude(pk__in=blind)
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
    elif status == "unsolved":
        qs = qs.filter(is_public=True, n_solved=0)
    else:
        status = ""
    difficulty = request.GET.get("difficulty", "")
    if difficulty in Problem.Difficulty.values:
        qs = qs.filter(difficulty=difficulty)
    else:
        difficulty = ""
    tag = request.GET.get("tag", "").strip()
    if tag:
        qs = qs.filter(tags__name=tag)
    sort = request.GET.get("sort", "")
    qs = qs.order_by(SORTS.get(sort, "-pk"), "-pk")
    if sort not in SORTS:
        sort = ""
    notests = Problem.objects.filter(kind=Problem.Kind.CODE).annotate(n=Count("testcases")).filter(n=0).count()
    page = Paginator(qs, 30).get_page(request.GET.get("page"))
    return render(request, "moderation/problems.html", {
        "page": page, "q": q, "status": status, "difficulty": difficulty, "tag": tag, "sort": sort,
        "difficulties": Problem.Difficulty.choices, "n_notests": notests, "n_blind": len(blind),
        "tags": Tag.objects.filter(kind=Tag.Kind.CODE).order_by("name"),
    })


@staff_required
@require_POST
def problems_bulk(request):
    """One action on the ticked problems: publish, hide, rejudge or add a topic."""
    ids = [int(i) for i in request.POST.getlist("ids") if i.isdigit()]
    action = request.POST.get("do", "")
    back = request.POST.get("next") if (request.POST.get("next") or "").startswith("/") else reverse("moderation:problems")
    if not ids or action not in ("publish", "hide", "rejudge", "tag"):
        messages.error(request, _t("Masalalarni belgilang va amalni tanlang."))
        return redirect(back)
    rows = Problem.objects.filter(pk__in=ids).exclude(pk__in=blind_problem_ids(request.user))
    now = timezone.now()
    done = skipped = 0
    for problem in rows:
        if action == "publish":
            if problem.is_public:
                continue
            if problem.status != Problem.Status.APPROVED or problem.contests.filter(end__gt=now).exists():
                skipped += 1
                continue
            problem.is_public = True
            problem.save(update_fields=["is_public"])
            audit.record(request, audit.Action.PROBLEM_TOGGLE, note=f"{problem.slug}: ochiq")
        elif action == "hide":
            if not problem.is_public:
                continue
            problem.is_public = False
            problem.save(update_fields=["is_public"])
            audit.record(request, audit.Action.PROBLEM_TOGGLE, note=f"{problem.slug}: yopiq")
        elif action == "rejudge":
            _rejudge(request, problem)
        elif action == "tag":
            tag = Tag.objects.filter(name=request.POST.get("tag", "").strip()).first()
            if tag is None:
                messages.error(request, _t("Mavzu topilmadi."))
                return redirect(back)
            problem.tags.add(tag)
        done += 1
    msg = _t("{n} ta masala yangilandi.").format(n=done)
    if skipped:
        msg += " " + _t("{n} tasi o‘tkazib yuborildi: tasdiqlanmagan yoki tugamagan musobaqada.").format(n=skipped)
    messages.success(request, msg)
    return redirect(back)


@staff_required
@require_POST
def problem_toggle(request, pk):
    problem = get_object_or_404(Problem, pk=pk)
    if problem.pk in blind_problem_ids(request.user):
        raise PermissionDenied
    if problem.status != Problem.Status.APPROVED:
        messages.error(request, _t("Navbatdagi yoki rad etilgan masalani ochib bo‘lmaydi: avval tasdiqlang."))
    elif not problem.is_public and problem.contests.filter(end__gt=timezone.now()).exists():
        messages.error(request, _t("Masala tugamagan musobaqada turibdi: musobaqa tugagach «Masalalarni ochish» bilan oching."))
    else:
        problem.is_public = not problem.is_public
        problem.save(update_fields=["is_public"])
        audit.record(request, audit.Action.PROBLEM_TOGGLE, note=f"{problem.slug}: {'ochiq' if problem.is_public else 'yopiq'}")
    back = request.POST.get("next") or ""
    return redirect(back if back.startswith("/") else "moderation:problems")


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
    n = _rejudge(request, problem)
    messages.success(request, _t("{len_ids} ta urinish qayta tekshirishga yuborildi.").format(len_ids=n))
    applied = list(problem.contests.filter(rating_applied=True).values_list("title", flat=True))
    if applied:
        messages.warning(request, f"{', '.join(applied)}: reyting allaqachon hisoblangan — "
                                  "qayta tekshiruvdan keyin ham o‘zgarmaydi.")
    return redirect("moderation:problems")


def _tell_author(problem, msgid, url: str) -> None:
    """The writer hears the staff's decision in the bell (nothing for a problem the staff wrote themselves)."""
    if problem.author_id and not problem.author.is_staff:
        from apps.accounts.notifications import notify_t
        notify_t(problem.author_id, "report", f"problem:{problem.pk}:{problem.status}", msgid, url, problem_title=problem.title)


@staff_required
def queue(request):
    problems = (Problem.objects.filter(status=Problem.Status.PENDING)
                .select_related("author").order_by("created"))
    return render(request, "moderation/queue.html", {"problems": problems})


@staff_required
@require_POST
def approve(request, pk):
    problem = get_object_or_404(Problem, pk=pk, status=Problem.Status.PENDING)
    if problem.pk in blind_problem_ids(request.user):
        raise PermissionDenied
    if problem.kind == Problem.Kind.CODE and problem.testcases.count() < 2:
        messages.error(request, _t("«{t}»: kamida 2 ta test kerak, tasdiqlab bo‘lmaydi.").format(t=problem.title))
        return redirect("moderation:queue")
    problem.status = Problem.Status.APPROVED
    problem.is_public = True
    problem.save(update_fields=["status", "is_public"])
    _tell_author(problem, _tl("«{problem_title}» masalangiz tasdiqlandi va saytda chiqdi"), reverse("problems:detail", args=[problem.slug]))
    return redirect("moderation:queue")


@staff_required
@require_POST
def reject(request, pk):
    problem = get_object_or_404(Problem, pk=pk, status=Problem.Status.PENDING)
    problem.status = Problem.Status.REJECTED
    problem.save(update_fields=["status"])
    _tell_author(problem, _tl("«{problem_title}» masalangiz rad etildi: tahrirlab qayta yuborishingiz mumkin"), reverse("moderation:mine"))
    return redirect("moderation:queue")


# ---- tags --------------------------------------------------------------------

@staff_required
def tags(request):
    form = TagForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("moderation:tags")
    q = request.GET.get("q", "").strip()
    qs = Tag.objects.annotate(n=Count("problem", distinct=True)).prefetch_related("courses")
    if q:
        qs = qs.filter(name__icontains=q)
    sort = request.GET.get("sort", "")
    qs = qs.order_by("-n", "name") if sort == "count" else qs.order_by("name")
    status = request.GET.get("show", "")
    rows = list(qs)
    if status == "empty":
        rows = [t for t in rows if t.n == 0]
    elif status == "nocourse":
        rows = [t for t in rows if not t.courses.all()]
    return render(request, "moderation/tags.html", {"tags": rows, "form": form, "q": q, "sort": sort, "show": status,
                                                    "all_tags": Tag.objects.order_by("name")})


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
    tag = get_object_or_404(Tag, pk=pk)
    n = tag.problem_set.count()
    courses = list(tag.courses.values_list("title", flat=True))
    if n or courses:  # a topic in use holds problems and courses together: merge it into another one, or empty it first
        messages.error(request, _t("«{tag}» ishlatilmoqda: {n} ta masala, kurslar: {courses}. O‘chirishdan oldin boshqa mavzuga birlashtiring.")
                       .format(tag=tag.name, n=n, courses=", ".join(courses) or "—"))
        return redirect("moderation:tags")
    audit.record(request, audit.Action.TAG_DELETE, note=tag.name)
    tag.delete()
    messages.success(request, _t("«{tag}» o‘chirildi.").format(tag=tag.name))
    return redirect("moderation:tags")


@staff_required
@require_POST
def tag_merge(request, pk):
    """Move every problem and course of the topic to another one and remove it (two names for one topic)."""
    tag = get_object_or_404(Tag, pk=pk)
    into = Tag.objects.filter(pk=request.POST.get("into") or 0).exclude(pk=tag.pk).first()
    if into is None:
        messages.error(request, _t("Qaysi mavzuga birlashtirilishini tanlang."))
        return redirect("moderation:tags")
    with transaction.atomic():
        for problem in tag.problem_set.all():
            problem.tags.add(into)
        for course in tag.courses.all():
            course.tags.add(into)
        audit.record(request, audit.Action.TAG_DELETE, note=f"{tag.name} → {into.name}")
        tag.delete()
    messages.success(request, _t("«{a}» «{b}» bilan birlashtirildi.").format(a=tag.name, b=into.name))
    return redirect("moderation:tags")


# ---- courses -----------------------------------------------------------------

@staff_required
def plans(request):
    qs = StudyPlan.objects.annotate(n_tags=Count("tags", distinct=True)).order_by("order", "id")
    rank = {v: i for i, v in enumerate(StudyPlan.Stage.values)}
    rows = sorted(qs, key=lambda p: (rank.get(p.stage, len(rank)), p.order, p.pk))  # grouped like the learn hub
    open_counts = {k: len(v) for k, v in plan_problem_ids(rows, raw=True).items()}
    for p in rows:
        p.n_open = open_counts[p.pk]
        p.partial = bool(p.n_tags) and 0 < p.n_open < COURSE_MIN
        p.empty = bool(p.n_tags) and p.n_open == 0
    n_partial = sum(1 for p in rows if p.partial or p.empty)
    return render(request, "moderation/plans.html", {"plans": rows, "course_min": COURSE_MIN, "course_max": COURSE_MAX,
                                                     "n_partial": n_partial})


@staff_required
def plan_edit(request, pk=None):
    plan = get_object_or_404(StudyPlan, pk=pk) if pk else None
    form = StudyPlanForm(request.POST or None, instance=plan)
    if request.method == "POST" and form.is_valid():
        plan = form.save()
        if form.changed_data and set(form.changed_data) & set(StudyPlan.TRANSLATABLE):
            from apps.translations import service as translations
            translations.stale(plan)  # the original changed: the other language waits for an admin again
        messages.success(request, "Kurs saqlandi.")
        return redirect("learn:course", plan.slug)
    return render(request, "moderation/plan_form.html", {"form": form, "plan": plan})


@staff_required
@require_POST
def plan_delete(request, pk):
    plan = get_object_or_404(StudyPlan, pk=pk)
    records = plan.reads.count() + plan.dones.count()
    if records:  # deleting would take the learners' "read" and "finished" records with it: hide the course instead
        messages.error(request, _t("«{plan_title}»: {n} ta o‘quvchi yozuvi bor. O‘chirmang, kursni yashiring (Ochiq belgisini olib tashlang).")
                       .format(plan_title=plan.title, n=records))
        return redirect("moderation:plans")
    audit.record(request, audit.Action.PLAN_DELETE, note=plan.title)
    plan.delete()  # problems and tags stay; only the course goes
    messages.success(request, _t("«{plan_title}» o‘chirildi.").format(plan_title=plan.title))
    return redirect("moderation:plans")


@staff_required
@require_POST
def plan_move(request, pk):
    """Move a course one step up or down on the path (within the list: it swaps places with its neighbour)."""
    plan = get_object_or_404(StudyPlan, pk=pk)
    rank = {v: i for i, v in enumerate(StudyPlan.Stage.values)}
    plans = sorted(StudyPlan.objects.all(), key=lambda p: (rank.get(p.stage, len(rank)), p.order, p.pk))  # the path's order
    i = next(k for k, p in enumerate(plans) if p.pk == plan.pk)
    j = i - 1 if request.POST.get("dir") == "up" else i + 1
    if 0 <= j < len(plans) and plans[j].stage == plan.stage:
        plans[i], plans[j] = plans[j], plans[i]
        for n, p in enumerate(plans, start=1):
            if p.order != n:
                StudyPlan.objects.filter(pk=p.pk).update(order=n)
    return redirect("moderation:plans")


# ---- contests ----------------------------------------------------------------

@setter_required
def contests(request):
    writer = not request.user.is_staff
    # similarity flags nobody has looked at yet: the reminder before a rating that can't be taken back
    open_flags = (SimilarityFlag.objects.filter(submission_a__contest=OuterRef("pk"), reviewed=False)
                  .values("submission_a__contest").annotate(n=Count("pk")).values("n"))
    qs = Contest.objects.annotate(n_problems=Count("contest_problems", distinct=True),
                                  n_participants=Count("participations", distinct=True),
                                  n_hidden=Count("contest_problems", filter=Q(contest_problems__problem__is_public=False),
                                                 distinct=True),
                                  n_open_flags=Coalesce(Subquery(open_flags), 0)).prefetch_related("authors").order_by("-start")
    if writer:
        qs = qs.filter(is_draft=True, authors=request.user)
    now = timezone.now()
    state = request.GET.get("state", "")
    if state == "running":
        qs = qs.filter(start__lte=now, end__gt=now)
    elif state == "upcoming":
        qs = qs.filter(start__gt=now)
    elif state == "torate":
        qs = qs.filter(is_rated=True, rating_applied=False, end__lte=now)
    elif state == "draft":
        qs = qs.filter(is_draft=True)
    elif state == "ended":
        qs = qs.filter(end__lte=now)
    else:
        state = ""
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(title__icontains=q)
    rows = list(qs)
    for c in rows:
        c.state = "draft" if c.is_draft else "running" if c.start <= now < c.end else "upcoming" if c.start > now else "ended"
        c.to_rate = c.is_rated and not c.rating_applied and c.end <= now
        c.blind_now = c.blind and c.end > now
    return render(request, "moderation/contests.html", {"contests": rows, "state": state, "q": q, "writer": writer,
                                                        "n_draft": sum(1 for c in rows if c.is_draft)})


@setter_required
def contest_edit(request, pk=None):
    writer = not request.user.is_staff
    contest = get_object_or_404(Contest, pk=pk) if pk else None
    is_author = contest is not None and contest.authors.filter(pk=request.user.pk).exists()
    if writer and contest is not None and not (contest.is_draft and is_author):
        raise PermissionDenied  # a writer prepares their own drafts only
    hidden = contest is not None and contest.blind and not contest.has_ended and not is_author and request.user.is_staff
    form = ContestForm(request.POST or None, instance=contest, writer=writer)
    formset = None if hidden else ContestProblemFormSet(request.POST or None, instance=form.instance, prefix="cp")
    if formset is not None and writer:
        formset.problem_queryset = Problem.objects.filter(author=request.user).order_by("title")
    if request.method == "POST" and form.is_valid() and (formset is None or formset.is_valid()):
        applied = contest is not None and contest.rating_applied
        if applied and formset is not None and formset.has_changed():
            messages.error(request, _t("Reyting hisoblangan: masalalar ro‘yxati va ballarini o‘zgartirib bo‘lmaydi (jadval va reyting buziladi)."))
        else:
            with transaction.atomic():
                contest = form.save(commit=False)
                if writer:
                    contest.is_draft, contest.blind = True, True
                contest.save()
                form.save_m2m()
                if writer:
                    contest.authors.add(request.user)
                if form.changed_data and set(form.changed_data) & set(Contest.TRANSLATABLE):
                    from apps.translations import service as translations
                    translations.stale(contest)
                if formset is not None:
                    formset.instance = contest
                    formset.save()
                audit.record(request, audit.Action.CONTEST_EDIT, contest=contest, note=", ".join(sorted(form.changed_data))[:250])
            messages.success(request, _t("Musobaqa saqlandi."))
            if applied and form.authors_changed:
                # who is rated changed: redo this round and every rated one after it
                n = rating.recompute_from(contest)
                audit.record(request, audit.Action.RATING_RECOMPUTE, contest=contest, note=_t("mualliflar o‘zgardi"))
                messages.info(request, _t("Mualliflar o‘zgardi: {n} ta raundning reytingi qayta hisoblandi.").format(n=n))
            if not contest.is_rated and not contest.has_ended and formset is not None:
                known = [cp.label for cp in contest.contest_problems.select_related("problem")
                         if reuse_reason(cp.problem, contest)]
                if known:
                    messages.warning(request, f"{', '.join(known)}: ochiq yoki boshqa musobaqada ishlatilgan — "
                                              "ishtirokchilar bu masalalarni oldindan bilishi mumkin.")
            return redirect("moderation:contests")
    if formset is not None:
        from apps.contests.models import LEVEL_POINTS
        problem_points = {p.pk: LEVEL_POINTS.get(p.difficulty, 500) for p in formset.forms[0].fields["problem"].queryset} if formset.forms else {}
        formset.forms  # noqa: B018 - built before the template asks for the empty form
    else:
        problem_points = {}
    return render(request, "moderation/contest_form.html", {"form": form, "formset": formset, "contest": contest, "writer": writer,
                                                            "hidden": hidden, "problem_points": problem_points,
                                                            "started": bool(contest and contest.has_started),
                                                            "applied": bool(contest and contest.rating_applied)})


@staff_required
@require_POST
def contest_draft_publish(request, pk):
    """A writer's draft goes live: its problems are approved (still hidden until the round ends) and the round is listed.
    The checks are mechanical (tests, time), so the staff need not read the problems."""
    contest = get_object_or_404(Contest, pk=pk, is_draft=True)
    problems = list(contest.contest_problems.select_related("problem"))
    if not problems:
        messages.error(request, _t("Raundda masala yo‘q."))
    elif contest.start <= timezone.now():
        messages.error(request, _t("Boshlanish vaqti o‘tib ketgan: raund vaqtini yangilash uchun muallifga qaytaring."))
    else:
        weak = [cp.label for cp in problems if cp.problem.kind == Problem.Kind.CODE and cp.problem.testcases.count() < 2]
        if weak:
            messages.error(request, _t("{labels}: kamida 2 ta test kerak.").format(labels=", ".join(weak)))
        else:
            with transaction.atomic():
                for cp in problems:
                    if cp.problem.status != Problem.Status.APPROVED:
                        Problem.objects.filter(pk=cp.problem_id).update(status=Problem.Status.APPROVED, is_public=False)
                contest.is_draft = False
                contest.save(update_fields=["is_draft"])
                audit.record(request, audit.Action.DRAFT_PUBLISH, contest=contest)
            messages.success(request, _t("«{t}» e’lon qilindi.").format(t=contest.title))
    return redirect("moderation:contests")


@staff_required
def contest_rating_preview(request, pk):
    """What applying the rating would do, without writing anything: each rated entrant's rating before and after."""
    contest = get_object_or_404(Contest, pk=pk)
    rows = rating._rated_rows(contest)
    ids = [r["user"].pk for r in rows]
    shown = dict(User.objects.filter(pk__in=ids).values_list("pk", "rating"))
    counts = rating._rated_counts(ids)
    before = [shown[i] for i in ids]
    after = rating._new_ratings(rows, before, [counts.get(i, 0) for i in ids])
    table = [{"row": r, "before": b, "after": a, "delta": a - b} for r, b, a in zip(rows, before, after)]
    flags = SimilarityFlag.objects.filter(submission_a__contest=contest, reviewed=False).count()
    return render(request, "moderation/contest_preview.html", {"contest": contest, "table": table, "flags": flags,
                                                               "gate": rating.gate_applies(contest)})


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
    if contest.is_rated and not contest.rating_applied:
        messages.error(request, _t("Avval reytingni hisoblang: masalalar ochilgach urinishlar mashq ballariga o‘tadi."))
        return redirect("moderation:contests")
    open_flags = SimilarityFlag.objects.filter(submission_a__contest=contest, reviewed=False).count()
    if open_flags and request.POST.get("force") != "1":
        messages.error(request, _t("{n} ta ko‘rilmagan o‘xshashlik belgisi bor: avval ko‘rib chiqing (yoki «Baribir ochish»).").format(n=open_flags))
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
def contest_unpublish(request, pk):
    """Take a published round's problems private again and return its contest solves from practice points."""
    contest = get_object_or_404(Contest, pk=pk)
    if contest.published_at is None:
        messages.error(request, _t("Bu raundning masalalari ochilmagan."))
        return redirect("moderation:contests")
    with transaction.atomic():
        Problem.objects.filter(contests=contest).update(is_public=False)
        contest.published_at = None
        contest.save(update_fields=["published_at"])
        for problem_id in contest.contest_problems.values_list("problem_id", flat=True):
            refresh_solves(problem_id)
        audit.record(request, audit.Action.UNPUBLISH, contest=contest)
    messages.success(request, _t("Masalalar yopildi."))
    return redirect("moderation:contests")


@staff_required
@require_POST
def contest_apply_rating(request, pk):
    from apps.contests import jobs
    contest = get_object_or_404(Contest, pk=pk)
    open_flags = SimilarityFlag.objects.filter(submission_a__contest=contest, reviewed=False).count()
    if not contest.is_rated:
        messages.error(request, "Reyting hisoblanmadi: musobaqa reytingli emas.")
    elif not contest.rating_applied and not contest.has_ended:
        messages.error(request, _t("Reyting hisoblanmadi: musobaqa hali tugamagan."))
    elif contest.rating_applied:
        messages.info(request, "Bu musobaqaning reytingi allaqachon hisoblangan.")
    elif open_flags and request.POST.get("force") != "1":
        messages.error(request, _t("{n} ta ko‘rilmagan o‘xshashlik belgisi bor: avval «Halollik» da ko‘rib chiqing (yoki «Baribir hisoblash»).").format(n=open_flags))
    else:
        jobs.run(jobs.apply_rating, contest.pk)
        audit.record(request, audit.Action.RATING_APPLY, contest=contest)
        messages.success(request, _t("Reyting hisoblanmoqda: bir necha soniyadan keyin sahifani yangilang.") if settings.RQ_ASYNC
                         else "Reyting hisoblandi.")
    return redirect("moderation:contests")


# ---- users -------------------------------------------------------------------

@staff_required
def submissions(request):
    """Every user's submissions, newest first; filters live in the query string so views are linkable."""
    qs = Submission.objects.select_related("user", "problem", "language", "contest").defer("source", "compile_log")
    blind = blind_problem_ids(request.user)
    if blind:
        qs = qs.exclude(problem_id__in=blind)
    f = {k: request.GET.get(k, "").strip() for k in ("user", "problem", "verdict", "contest", "lang", "since", "stuck")}
    if f["user"]:
        qs = qs.filter(user__username__icontains=f["user"])
    if f["problem"]:
        qs = qs.filter(Q(problem__slug__icontains=f["problem"]) | Q(problem__title__icontains=f["problem"]))
    if f["verdict"] in Submission.Verdict.values:
        qs = qs.filter(verdict=f["verdict"])
    if f["contest"].isdigit():
        qs = qs.filter(contest_id=int(f["contest"]))
    if f["lang"]:
        qs = qs.filter(language__code=f["lang"])
    if f["since"]:
        try:
            qs = qs.filter(created__date__gte=datetime.date.fromisoformat(f["since"]))
        except ValueError:
            f["since"] = ""
    if f["stuck"] == "1":  # waiting or running for over two minutes
        qs = qs.filter(verdict__in=[Submission.Verdict.PENDING, Submission.Verdict.RUNNING],
                       created__lt=timezone.now() - datetime.timedelta(minutes=2))
    page = Paginator(qs.order_by("-pk"), 50).get_page(request.GET.get("page"))
    from apps.problems.models import Language
    return render(request, "moderation/submissions.html", {
        "page": page, "f": f, "verdicts": list(VERDICT_LABELS.items()),
        "contests": Contest.objects.order_by("-start").only("id", "title")[:50],
        "languages": Language.objects.filter(is_active=True).order_by("name"),
        "stale_at": timezone.now() - datetime.timedelta(minutes=2),
    })


@staff_required
def duel_detail(request, pk):
    """One duel under the lens: each player's answers with the time each took, and the very fast ones marked."""
    from apps.classroom.duels import AWAY_MS
    from apps.classroom.models import Duel, DuelAnswer

    duel = get_object_or_404(Duel.objects.select_related("challenger", "opponent", "winner"), pk=pk)
    sides = []
    for u in (duel.challenger, duel.opponent):
        if u is None:
            continue
        rows = []
        for a in DuelAnswer.objects.filter(duel=duel, user=u).select_related("question").order_by("index"):
            took = (a.answered_at - a.shown_at).total_seconds() if a.answered_at else None
            rows.append({"a": a, "took": None if took is None else round(took, 1), "fast": took is not None and took < 1.5,
                         "away": round(a.away_ms / 1000, 1), "left": a.away_ms >= AWAY_MS})
        avg = [r["took"] for r in rows if r["took"] is not None]
        sides.append({"user": u, "rows": rows, "fast": sum(r["fast"] for r in rows), "left": sum(r["left"] for r in rows),
                      "left_right": sum(r["left"] and r["a"].correct for r in rows),
                      "avg": round(sum(avg) / len(avg), 1) if avg else None})
    return render(request, "moderation/duel_detail.html", {"duel": duel, "sides": sides})


@staff_required
@require_POST
def duel_void(request, pk):
    """Take a finished duel back: it no longer counts, and every duel rating is worked out again without it."""
    from apps.classroom import duels as duel_rules
    from apps.classroom.models import Duel

    duel = get_object_or_404(Duel, pk=pk)
    if duel.status != Duel.Status.FINISHED:
        messages.error(request, _t("Faqat tugagan duelni bekor qilish mumkin."))
        return redirect("moderation:duel_detail", pk)
    duel.status = Duel.Status.VOID
    duel.save(update_fields=["status"])
    duel_rules.replay(Duel.objects.all(), User.objects.all())
    audit.record(request, audit.Action.DUEL_VOID, subject=duel.challenger, note=f"#{duel.pk} {duel.challenger} – {duel.opponent}")
    messages.success(request, _t("Duel #{n} bekor qilindi, duel reytinglari qayta hisoblandi.").format(n=duel.pk))
    return redirect("moderation:duels")


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
    elif role == "setter":
        qs = qs.filter(is_setter=True)
    elif role == "unverified":
        qs = qs.filter(email_verified_at__isnull=True, is_staff=False)
    elif role == "idle":
        qs = qs.filter(n_subs=0, is_staff=False)
    elif role == "student":
        qs = qs.filter(is_staff=False)
    else:
        role = ""
    country = request.GET.get("country", "").strip().upper()
    if country:
        qs = qs.filter(country=country)
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
    from apps.accounts.countries import COUNTRY_CHOICES
    return render(request, "moderation/users.html", {
        "page": page, "q": q, "role": role, "sort": sort, "country": country, "countries": COUNTRY_CHOICES,
        "counts": {"unverified": User.objects.filter(email_verified_at__isnull=True, is_staff=False).count(),
                   "idle": User.objects.annotate(n=Count("submissions")).filter(n=0, is_staff=False).count()},
    })


@staff_required
def user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    form = UserForm(request.POST or None, instance=user)
    if request.method == "POST" and form.is_valid():
        if user == request.user and not (form.cleaned_data["is_staff"] and form.cleaned_data["is_active"]):
            form.add_error(None, _t("O'zingizni admin huquqidan yoki faollikdan mahrum qila olmaysiz."))
        else:
            changed = sorted(form.changed_data)
            form.save()
            audit.record(request, audit.Action.USER_EDIT, subject=user, note=", ".join(changed)[:250])
            messages.success(request, _t("Foydalanuvchi saqlandi."))
            if "rating" in changed:
                messages.warning(request, _t("Qo‘lda yozilgan reyting keyingi to‘liq qayta hisobda (replay) o‘chib ketadi."))
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
        elif request.POST.get("force") != "1" and user.participations.filter(rating_after__isnull=False).exists():
            # deleting would move the places of everyone who played those rated rounds: block the account instead
            reason = _t("reytingli raundlarda qatnashgan: o‘chirsangiz boshqalarning o‘rni ham o‘zgaradi. Hisobni bloklang (Faol belgisini olib tashlang) yoki «Baribir o‘chirish» ni bosing")
        else:
            reason = None
        if reason:
            messages.error(request, f"{user.username}: {reason}.")
            return redirect("moderation:user_edit", pk)
        audit.record(request, audit.Action.USER_DELETE, note=f"#{user.pk} — {user.username} ({user.email})")
        user.delete()
    messages.success(request, _t("{user_username} o‘chirildi.").format(user_username=user.username))
    return redirect("moderation:users")


@staff_required
def accepted_preview(request):
    """What a player sees and hears on an accepted attempt, to try without solving anything."""
    return render(request, "moderation/accepted_preview.html")
