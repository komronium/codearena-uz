import re
from urllib.parse import unquote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.problems.models import Problem, Tag
from apps.problems.skills import open_problems, skill_map
from apps.problems.views import _render_statement

from .forms import ListForm
from .models import ProblemList, ProblemListItem, StudyPlan
from .progress import plan_problem_ids, plan_progress, plan_sections, solved_ids


def _plans_for(user):
    plans = StudyPlan.objects.all()
    return plans if user.is_staff else plans.filter(is_public=True)


def hub(request):
    """Kurslar: the main path (in_quest courses, numbered) and the extra courses, each shown
    once, plus one "continue" card with the next problem to solve."""
    plans = list(_plans_for(request.user))
    progress = plan_progress(request.user, plans)
    details = plan_sections(request.user, plans)
    for p in plans:
        p.progress = progress[p.pk]
        p.dots = details[p.pk]["sections"]
        p.dots_done = sum(1 for s in p.dots if s["complete"])
    quest = [p for p in plans if p.in_quest]
    here = next((p for p in quest if not p.progress["completed"]), None)
    # Continue what was started (in course order), else the first unfinished stage of the path.
    current = next((p for p in plans if 0 < p.progress["done"] and not p.progress["completed"]), here)
    next_problem = None
    if current is not None and details[current.pk]["next_id"]:
        next_problem = Problem.objects.filter(pk=details[current.pk]["next_id"]).first()
    return render(request, "learn/hub.html", {
        "quest": quest, "here": here if request.user.is_authenticated else None,
        "extra": [p for p in plans if not p.in_quest],
        "current": current, "next_problem": next_problem,
    })


def _section_topic(intro_md: str, problems):
    """The topic a section is about: the one its intro links to, else the most common tag
    with written theory among its problems."""
    linked = re.search(r"/learn/topics/([^/)\s]+)/", intro_md)
    if linked:
        tag = Tag.objects.filter(name=unquote(linked.group(1))).exclude(about_md="").first()
        if tag is not None:
            return tag
    counts: dict = {}
    for p in problems:
        for t in p.tags.all():
            if t.about_md.strip():
                counts[t] = counts.get(t, 0) + 1
    return max(counts, key=lambda t: (counts[t], t.name), default=None)


def plan_detail(request, slug):
    plan = get_object_or_404(_plans_for(request.user), slug=slug)
    open_ids = set(plan_problem_ids([plan])[plan.pk])
    solved = solved_ids(request.user, open_ids)
    problems = Problem.objects.filter(pk__in=open_ids).prefetch_related("tags").in_bulk()
    sections = []
    for section in plan.sections.prefetch_related("items"):
        # a section with no open problem yet still shows its intro and theory ("tez orada")
        rows = [problems[i.problem_id] for i in section.items.all() if i.problem_id in problems]
        done = sum(p.pk in solved for p in rows)
        sections.append({"section": section, "intro_html": _render_statement(section.intro_md),
                         "problems": rows, "done": done, "complete": bool(rows) and done == len(rows),
                         "topic": _section_topic(section.intro_md, rows)})
    for p in problems.values():
        p.solved = p.pk in solved
    next_id = plan_sections(request.user, [plan])[plan.pk]["next_id"]
    return render(request, "learn/plan.html", {
        "plan": plan, "sections": sections, "progress": plan_progress(request.user, [plan])[plan.pk],
        "description_html": _render_statement(plan.description_md),
        "next_problem": problems.get(next_id),
    })


# ---- topics ("Qo‘llanma") -------------------------------------------------------

def _excerpt(md: str) -> str:
    """First prose line of a topic's theory, markdown marks stripped, for its card."""
    for line in md.splitlines():
        line = line.strip()
        if line and not line.startswith(("#", "```", "|", ">", "-", "*", "$$")):
            return line.replace("**", "").replace("`", "")
    return ""


def topics(request):
    """Qo‘llanma: every topic with written theory, problems or not yet. Tags without theory
    are plain filters on Masalalar."""
    counts = {r["tag"].pk: r for r in skill_map(request.user)}
    rows = []
    for tag in Tag.objects.exclude(about_md=""):
        r = counts.get(tag.pk) or {"tag": tag, "solved": 0, "total": 0, "pct": 0}
        r["excerpt"] = _excerpt(tag.about_md)
        rows.append(r)
    rows.sort(key=lambda r: (-r["total"], r["tag"].name))
    return render(request, "learn/topics.html", {
        "groups": [(value, label, [r for r in rows if r["tag"].kind == value]) for value, label in Tag.Kind.choices],
        "n_without_theory": Tag.objects.filter(about_md="").count() if request.user.is_staff else 0,
    })


def topic_detail(request, name):
    tag = get_object_or_404(Tag, name=name)
    problems = list(open_problems().filter(tags=tag).prefetch_related("tags").order_by("id"))
    if not problems and not tag.about_md.strip():
        raise Http404
    solved = solved_ids(request.user, [p.pk for p in problems])
    for p in problems:
        p.solved = p.pk in solved
    levels = dict(Problem.Difficulty.choices)
    by_level = [(levels[v], [p for p in problems if p.difficulty == v]) for v in levels]
    return render(request, "learn/topic.html", {
        "tag": tag, "theory_html": _render_statement(tag.about_md), "n": len(problems), "done": len(solved),
        "by_level": [(label, ps) for label, ps in by_level if ps],
        "plans": (StudyPlan.objects.filter(Q(sections__items__problem__in=problems)
                                           | Q(sections__intro_md__contains=f"/learn/topics/{tag.name}/"),
                                           is_public=True).distinct()),
    })


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

