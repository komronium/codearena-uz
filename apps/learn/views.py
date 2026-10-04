from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.problems.models import Problem
from apps.problems.skills import open_problems
from apps.problems.views import _render_statement
from apps.submissions.models import UserProblemSolved

from .forms import ListForm
from .models import ProblemList, ProblemListItem, StudyPlan
from .progress import course_rows, plan_progress, plan_sections, solved_ids

# Old addresses that moved: the first study plans, and topics whose tag was renamed or that
# have no course of their own. Any other topic goes to the course that carries its tag.
OLD_PLANS = {
    "birinchi-qadam": "input-output", "massiv-va-satrlar": "arrays", "algoritmlarga-kirish": "complexity",
    "malumotlar-tuzilmalari": "stack-queue", "rekursiya-va-qidiruv": "functions", "graflar": "graph-traversal",
    "dinamik-dasturlash": "dp-intro", "matematika-va-sonlar": "number-basics",
    "musobaqaga-tayyorgarlik": "complexity", "sql-asoslari": "sql-select",
}
MOVED_TOPICS = {"loops": "for-loop", "math": "arithmetic", "complexity": "complexity",
                "data-structures": "stack-queue", "graphs": "graph-traversal"}


def _plans_for(user):
    plans = StudyPlan.objects.all()
    return plans if user.is_staff else plans.filter(is_public=True)


def _current(user, plans):
    """The course to continue: the unfinished one with the user's latest solve (a problem in
    several courses: the earliest of them on the path), else the first unfinished course that
    has problems."""
    open_courses = [p for p in plans if p.progress["total"] and not p.progress["completed"]]
    if user.is_authenticated and open_courses:
        solved_at = dict(UserProblemSolved.objects.filter(user=user).values_list("problem_id", "solved_at"))
        started = [(max(solved_at[i] for i in p.problem_ids if i in solved_at), -p.number, p)
                   for p in open_courses if any(i in solved_at for i in p.problem_ids)]
        if started:
            return max(started, key=lambda t: t[:2])[2]
    return open_courses[0] if open_courses else None


def hub(request):
    """O‘rganish: every course on one path, chapter by chapter (StudyPlan.Stage), numbered in
    path order, plus one "continue" card with the next problem to solve."""
    stage_rank = {v: i for i, v in enumerate(StudyPlan.Stage.values)}
    plans = sorted(_plans_for(request.user).annotate(n_tags=Count("tags")),
                   key=lambda p: (stage_rank.get(p.stage, len(stage_rank)), p.order, p.pk))
    progress = plan_progress(request.user, plans)
    details = plan_sections(request.user, plans)
    ids = {plan_id: [i for i, _ in rows] for plan_id, rows in course_rows(plans).items()}
    for number, p in enumerate(plans, 1):
        p.number, p.progress, p.problem_ids = number, progress[p.pk], ids[p.pk]
        p.dots = details[p.pk]["sections"]
        p.dots_done = sum(1 for s in p.dots if s["complete"])
    current = _current(request.user, plans)
    next_problem, up_next = None, []
    if current is not None and details[current.pk]["next_id"]:
        # the current course's next few unsolved problems, in course order
        solved = solved_ids(request.user, current.problem_ids)
        todo = [i for i in current.problem_ids if i not in solved][:5]
        found = Problem.objects.in_bulk(todo)
        up_next = [found[i] for i in todo if i in found]
        next_problem = up_next[0] if up_next else None
    labels = dict(StudyPlan.Stage.choices)
    stages = []
    for p in plans:
        if not stages or stages[-1]["stage"] != p.stage:
            stages.append({"stage": p.stage, "label": labels.get(p.stage, p.stage), "courses": []})
        stages[-1]["courses"].append(p)
    # a course badge per finished course; the ones with problems still to earn show locked
    badges = [p for p in plans if p.progress["total"] and p.is_public]
    return render(request, "learn/hub.html", {
        "stages": stages, "current": current, "next_problem": next_problem, "up_next": up_next,
        "here": current if request.user.is_authenticated else None,
        "badges": badges, "badges_earned": sum(1 for p in badges if p.progress["completed"])})


def course_detail(request, slug):
    """A course: its theory, then its open problems grouped by difficulty."""
    plan = get_object_or_404(_plans_for(request.user), slug=slug)
    rows = course_rows([plan])[plan.pk]
    problems = Problem.objects.filter(pk__in=[i for i, _ in rows]).prefetch_related("tags").in_bulk()
    solved = solved_ids(request.user, problems)
    labels = dict(Problem.Difficulty.choices)
    groups: list[dict] = []
    for problem_id, level in rows:
        p = problems[problem_id]
        p.solved = p.pk in solved
        if not groups or groups[-1]["level"] != level:
            groups.append({"level": level, "label": labels.get(level, level), "problems": [], "done": 0})
        groups[-1]["problems"].append(p)
        groups[-1]["done"] += p.solved
    progress = plan_progress(request.user, [plan])[plan.pk]
    next_id = next((i for i, _ in rows if i not in solved), None)
    return render(request, "learn/course.html", {
        "plan": plan, "groups": groups, "progress": progress, "next_problem": problems.get(next_id),
        "theory_html": _render_statement(plan.theory_md), "description_html": _render_statement(plan.description_md),
    })


def plan_redirect(request, slug):
    """/learn/plans/<slug>/ — where courses lived before."""
    return redirect("learn:course", OLD_PLANS.get(slug, slug))


def topics(request):
    """Qo‘llanma's old list: its articles are inside the courses now."""
    return redirect("learn:hub")


def topic_redirect(request, name):
    """An old Qo‘llanma article: to the course carrying its tag; a tag with no course but with
    problems goes to the problem list filtered by it."""
    slug = MOVED_TOPICS.get(name)
    if slug is None:
        course = _plans_for(request.user).filter(tags__name=name).order_by("order", "id").first()
        slug = course.slug if course else None
    if slug is not None:
        return redirect("learn:course", slug)
    if open_problems().filter(tags__name=name).exists():
        return redirect(f"{reverse('problems:list')}?{urlencode({'tag': name})}")
    raise Http404


def course_search(request):
    """Courses for the command palette: title, summary or theory matches, path order."""
    q = request.GET.get("q", "").strip()[:60]
    if len(q) < 2:
        return JsonResponse({"results": []})
    stage_labels = dict(StudyPlan.Stage.choices)
    found = (_plans_for(request.user).filter(Q(title__icontains=q) | Q(summary__icontains=q)
                                             | Q(theory_md__icontains=q) | Q(slug__icontains=q.replace(" ", "-")))
             .order_by("order", "id")[:20])
    rows = sorted(found, key=lambda p: (q.lower() not in p.title.lower(), p.order))[:5]
    return JsonResponse({"results": [
        {"title": p.title, "url": reverse("learn:course", args=[p.slug]), "icon": p.icon,
         "hint": stage_labels.get(p.stage, "") if q.lower() in p.title.lower() else "nazariyada"}
        for p in rows]})


# ---- my lists ("Ro‘yxatlarim") -------------------------------------------------

@login_required
def lists(request):
    form = ListForm(request.POST or None, owner=request.user)
    if request.method == "POST" and form.is_valid():
        lst = form.save()
        return redirect("learn:list", lst.pk)
    rows = (request.user.problem_lists
            .annotate(n=Count("items", filter=Q(items__problem__in=open_problems()), distinct=True)))
    return render(request, "learn/lists.html", {"lists": rows, "form": form})


def list_detail(request, pk):
    lst = get_object_or_404(ProblemList.objects.select_related("owner"), pk=pk)
    is_owner = lst.owner_id == request.user.id
    if not (lst.is_public or is_owner):
        raise Http404
    ids = list(lst.items.values_list("problem_id", flat=True))
    shown = {p.pk: p for p in open_problems().filter(pk__in=ids).prefetch_related("tags")}
    solved = solved_ids(request.user, shown)
    rows = [shown[i] for i in ids if i in shown]
    for p in rows:
        p.solved = p.pk in solved
    return render(request, "learn/list.html", {
        "lst": lst, "rows": rows, "n_hidden": len(ids) - len(rows), "is_owner": is_owner,
        "form": ListForm(instance=lst, owner=request.user) if is_owner else None,
    })


@login_required
@require_POST
def list_edit(request, pk):
    lst = get_object_or_404(ProblemList, pk=pk, owner=request.user)
    form = ListForm(request.POST, instance=lst, owner=request.user)
    if form.is_valid():
        form.save()
    else:
        messages.error(request, " ".join(e for errs in form.errors.values() for e in errs))
    return redirect("learn:list", lst.pk)


@login_required
@require_POST
def list_delete(request, pk):
    lst = get_object_or_404(ProblemList, pk=pk, owner=request.user)
    lst.delete()
    messages.success(request, f"«{lst.name}» o‘chirildi.")
    return redirect("learn:lists")


@login_required
@require_POST
def save(request, slug):
    """Toggle a problem in one of the user's lists (list=<pk>), or start a new list with it
    (list=new, name=...). Only open problems: a list must not reveal hidden ones."""
    problem = get_object_or_404(open_problems(), slug=slug)
    if request.POST.get("list") == "new":
        form = ListForm({"name": request.POST.get("name", "")}, owner=request.user)
        if not form.is_valid():
            messages.error(request, " ".join(e for errs in form.errors.values() for e in errs))
            return _back(request, problem)
        lst = form.save()
    else:
        try:
            list_id = int(request.POST.get("list", ""))
        except ValueError:
            raise Http404
        lst = get_object_or_404(ProblemList, pk=list_id, owner=request.user)
    removed, _ = ProblemListItem.objects.filter(list=lst, problem=problem).delete()
    if not removed:
        ProblemListItem.objects.get_or_create(list=lst, problem=problem)
    done = "ro‘yxatidan olindi" if removed else "ro‘yxatiga saqlandi"
    messages.success(request, f"«{problem.title}» — «{lst.name}» {done}.")
    return _back(request, problem)


def _back(request, problem):
    nxt = request.POST.get("next", "")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()},
                                                require_https=request.is_secure()):
        return redirect(nxt)
    return redirect("problems:detail", problem.slug)

