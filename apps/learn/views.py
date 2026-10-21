import re
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, Q
from apps.translations.mixin import localized
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.problems.models import Problem
from apps.problems.skills import open_problems
from apps.problems.views import _render_statement
from apps.submissions.models import UserProblemSolved

from .forms import ListForm
from .models import PlanRead, ProblemList, ProblemListItem, StudyPlan
from .progress import COURSE_MIN, course_rows, plan_progress, plan_sections, solved_ids
from django.utils.translation import gettext as _t
from django.utils.translation import gettext as _t

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


def continue_course(user) -> dict | None:
    """The dashboard's "keep learning": the course the hub would continue, its progress and its
    next unsolved problem."""
    stage_rank = {v: i for i, v in enumerate(StudyPlan.Stage.values)}
    plans = sorted(_plans_for(user), key=lambda p: (stage_rank.get(p.stage, len(stage_rank)), p.order, p.pk))
    progress = plan_progress(user, plans)
    ids = {plan_id: [i for i, _ in rows] for plan_id, rows in course_rows(plans, user=user).items()}
    for number, p in enumerate(plans, 1):
        p.number, p.progress, p.problem_ids = number, progress[p.pk], ids[p.pk]
    current = _current(user, plans)
    if current is None:
        return None
    solved = solved_ids(user, current.problem_ids)
    next_id = next((i for i in current.problem_ids if i not in solved), None)
    return {"plan": current, "progress": current.progress,
            "next": Problem.objects.filter(pk=next_id).first() if next_id else None}


def hub(request):
    """O‘rganish: every course on one path, chapter by chapter (StudyPlan.Stage), numbered in
    path order, plus one "continue" card with the next problem to solve."""
    stage_rank = {v: i for i, v in enumerate(StudyPlan.Stage.values)}
    plans = sorted(_plans_for(request.user).annotate(n_tags=Count("tags")),
                   key=lambda p: (stage_rank.get(p.stage, len(stage_rank)), p.order, p.pk))
    progress = plan_progress(request.user, plans)
    details = plan_sections(request.user, plans)
    ids = {plan_id: [i for i, _ in rows] for plan_id, rows in course_rows(plans, user=request.user).items()}
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
    raw = course_rows(plans, raw=True)
    stages, soon, step = [], [], 0
    for p in plans:
        # a course with topics but under 10 open problems is "Qisman": it opens as soon as it has any problem (the theory
        # reads now, the problems it has can be solved, and it counts towards a badge at 10); one with none yet waits in
        # "Tez orada". A theory-only course (no topics) reads now and stays.
        p.partial = bool(p.n_tags and not p.progress["total"] and not p.progress["completed"])
        if p.partial:
            p.ready = min(len(raw[p.pk]), COURSE_MIN)  # how close it is to opening in full
            p.ready_pct = round(100 * p.ready / COURSE_MIN)
            if not p.ready:
                soon.append(p)
                continue
        step += 1
        p.step = step
        # a rough time: ten minutes of theory and about twelve a problem
        p.hours = max(1, round((10 + 12 * (p.progress["total"] or (p.ready if p.partial else 0))) / 60))
        if not stages or stages[-1]["stage"] != p.stage:
            stages.append({"stage": p.stage, "label": labels.get(p.stage, p.stage), "courses": []})
        stages[-1]["courses"].append(p)
    for st in stages:
        st["done"] = sum(1 for c in st["courses"] if c.progress["completed"])
    path = {"done": sum(st["done"] for st in stages), "total": step}
    path["pct"] = round(100 * path["done"] / path["total"]) if path["total"] else 0
    return render(request, "learn/hub.html", {
        "stages": stages, "soon": soon, "current": current, "next_problem": next_problem, "up_next": up_next, "path": path,
        "here": current if request.user.is_authenticated else None})


def _next_course(user, plan):
    """The course after `plan` on the path that can be opened and isn't finished yet (None at the end of the path)."""
    stage_rank = {v: i for i, v in enumerate(StudyPlan.Stage.values)}
    path = sorted(_plans_for(user), key=lambda p: (stage_rank.get(p.stage, len(stage_rank)), p.order, p.pk))
    rest = path[[p.pk for p in path].index(plan.pk) + 1:]
    progress = plan_progress(user, rest)
    return next((p for p in rest if not progress[p.pk]["completed"] and (progress[p.pk]["total"] or progress[p.pk]["theory_only"])), None)


def course_detail(request, slug):
    """A course: its theory, then its open problems grouped by difficulty."""
    plan = get_object_or_404(_plans_for(request.user), slug=slug)
    rows = course_rows([plan], user=request.user)[plan.pk]
    ready = partial = 0
    if not rows:  # still short of problems: list the few it has, they can be solved already
        rows = course_rows([plan], raw=True)[plan.pk]
        ready = partial = len(rows)
    tag_ids = set(plan.tags.values_list("pk", flat=True))
    problems = (Problem.objects.filter(pk__in=[i for i, _ in rows]).annotate(n_solved=Count("userproblemsolved"))
                .prefetch_related("tags").in_bulk())
    solved = solved_ids(request.user, problems)
    labels = dict(Problem.Difficulty.choices)
    groups: list[dict] = []
    for problem_id, level in rows:
        p = problems[problem_id]
        p.solved = p.pk in solved
        p.other_tags = [t for t in p.tags.all() if t.pk not in tag_ids][:3]  # the course's own topic is no news in its list
        if not groups or groups[-1]["level"] != level:
            groups.append({"level": level, "label": labels.get(level, level), "problems": [], "done": 0})
        groups[-1]["problems"].append(p)
        groups[-1]["done"] += p.solved
    progress = plan_progress(request.user, [plan])[plan.pk]
    show_tags = any(p.other_tags for g in groups for p in g["problems"])  # a column of nothing is not drawn
    next_id = next((i for i, _ in rows if i not in solved), None)
    theory_html, toc = _with_toc(_render_statement(localized(plan, "theory_md")))
    following = _next_course(request.user, plan)
    from apps.accounts import badges
    learner = next(f for f in badges.ladders(request.user) if f["key"] == "bilimdon")
    return render(request, "learn/course.html", {
        "plan": plan, "groups": groups, "progress": progress, "next_problem": problems.get(next_id),
        "theory_html": theory_html, "toc": toc, "next_plan": following, "learner": learner, "partial": partial,
        "ready": ready, "course_min": COURSE_MIN, "show_tags": show_tags,
        "description_html": _render_statement(localized(plan, "description_md")),
    })


CODE_LANGS = {"python", "c", "c++", "cpp", "java", "javascript", "js", "sql", "c#", "rust"}


def _with_toc(html: str) -> tuple[str, list[dict]]:
    """Give the theory's h2/h3 headings anchors and list them, for the course's contents card."""
    toc, seen = [], set()

    def anchor(m):
        level, inner = m.group(1), m.group(2)
        text = re.sub(r"<[^>]+>", "", inner).strip()
        base = slugify(text, allow_unicode=True) or "bo-lim"
        slug, n = base, 2
        while slug in seen:
            slug, n = f"{base}-{n}", n + 1
        seen.add(slug)
        if text.lower() not in CODE_LANGS:  # "Python", "C++": a code block's label, not a section
            toc.append({"id": slug, "text": text, "level": int(level)})
        return f'<h{level} id="{slug}">{inner}</h{level}>'

    return re.sub(r"<h([23])>(.*?)</h\1>", anchor, html, flags=re.S), toc


@login_required
@require_POST
def course_read(request, slug):
    """"Tushundim" / "Qaytarish": mark the course's theory as read, or undo it."""
    plan = get_object_or_404(_plans_for(request.user), slug=slug)
    if request.POST.get("undo"):
        PlanRead.objects.filter(user=request.user, plan=plan).delete()
    else:
        PlanRead.objects.get_or_create(user=request.user, plan=plan)  # (a theory-only course earns no badge level)
        messages.success(request, _t("Nazariya o‘qildi deb belgilandi.") if plan.tags.exists()
                         else _t("Nazariya o‘qildi: kurs tugatildi. Nishon bosqichi faqat masalali kurslar bilan oshadi."))
    return redirect(reverse("learn:course", args=[slug]) + "#nazariya-tugadi")


def plan_redirect(request, slug):
    """/learn/plans/<slug>/ — where courses lived before. Moved for good: 301, so search engines
    carry the old address's standing over."""
    return redirect("learn:course", OLD_PLANS.get(slug, slug), permanent=True)


def topics(request):
    """Qo‘llanma's old list: its articles are inside the courses now."""
    return redirect("learn:hub", permanent=True)


def topic_redirect(request, name):
    """An old Qo‘llanma article: to the course carrying its tag; a tag with no course but with
    problems goes to the problem list filtered by it."""
    slug = MOVED_TOPICS.get(name)
    if slug is None:
        course = _plans_for(request.user).filter(tags__name=name).order_by("order", "id").first()
        slug = course.slug if course else None
    if slug is not None:
        return redirect("learn:course", slug, permanent=True)
    if open_problems().filter(tags__name=name).exists():
        return redirect(f"{reverse('problems:list')}?{urlencode({'tag': name})}", permanent=True)
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
    open_ = open_problems()
    rows = (request.user.problem_lists
            .annotate(n=Count("items", filter=Q(items__problem__in=open_), distinct=True),
                      n_solved=Count("items", filter=Q(items__problem__in=open_, items__problem__userproblemsolved__user=request.user),
                                     distinct=True),
                      changed=Max("items__added")))
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
        "lst": lst, "rows": rows, "n_hidden": len(ids) - len(rows) if is_owner else 0, "is_owner": is_owner,
        "n_solved": sum(1 for p in rows if p.solved), "next_row": next((p for p in rows if not p.solved), None),
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
    messages.success(request, _t("«{lst_name}» o‘chirildi.").format(lst_name=lst.name))
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
    if request.headers.get("X-Requested-With") == "fetch":  # the menu on the problem page: no reload, it updates itself
        saved = set(ProblemListItem.objects.filter(list__owner=request.user, problem=problem).values_list("list_id", flat=True))
        return JsonResponse({"has": not removed, "list": lst.pk, "any": bool(saved),
                             "text": f"«{lst.name}» " + (_t("ro‘yxatidan olindi") if removed else _t("ro‘yxatiga saqlandi"))})
    done = _t("ro‘yxatidan olindi") if removed else _t("ro‘yxatiga saqlandi")
    messages.success(request, f"«{problem.title}» — «{lst.name}» {done}.")
    return _back(request, problem)


def _back(request, problem):
    nxt = request.POST.get("next", "")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()},
                                                require_https=request.is_secure()):
        return redirect(nxt)
    return redirect("problems:detail", problem.slug)

