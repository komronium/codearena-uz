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
from .progress import plan_problem_ids, plan_progress, solved_ids


def _plans_for(user):
    plans = StudyPlan.objects.all()
    return plans if user.is_staff else plans.filter(is_public=True)


def hub(request):
    plans = list(_plans_for(request.user))
    progress = plan_progress(request.user, plans)
    for p in plans:
        p.progress = progress[p.pk]
    quest = [p for p in plans if p.in_quest]
    here = next((p for p in quest if not p.progress["completed"]), None) if request.user.is_authenticated else None
    levels = dict(Problem.Difficulty.choices)
    by_level = [(levels[v], [p for p in plans if p.level == v]) for v in levels]
    return render(request, "learn/hub.html", {
        "quest": quest, "here": here,
        # quest stages already show their progress above
        "going": [p for p in plans if not p.in_quest and 0 < p.progress["done"] < p.progress["total"]],
        "by_level": [(label, ps) for label, ps in by_level if ps],
    })


def plan_detail(request, slug):
    plan = get_object_or_404(_plans_for(request.user), slug=slug)
    open_ids = set(plan_problem_ids([plan])[plan.pk])
    solved = solved_ids(request.user, open_ids)
    problems = Problem.objects.filter(pk__in=open_ids).prefetch_related("tags").in_bulk()
    sections = []
    for section in plan.sections.prefetch_related("items"):
        rows = [problems[i.problem_id] for i in section.items.all() if i.problem_id in problems]
        if rows:
            sections.append({"section": section, "intro_html": _render_statement(section.intro_md),
                             "problems": rows, "done": sum(p.pk in solved for p in rows)})
    for p in problems.values():
        p.solved = p.pk in solved
    return render(request, "learn/plan.html", {
        "plan": plan, "sections": sections, "progress": plan_progress(request.user, [plan])[plan.pk],
        "description_html": _render_statement(plan.description_md),
    })


# ---- topics ("Mavzular") -------------------------------------------------------

def topics(request):
    rows = skill_map(request.user)
    return render(request, "learn/topics.html", {
        "groups": [(label, [r for r in rows if r["tag"].kind == value]) for value, label in Tag.Kind.choices],
    })


def topic_detail(request, name):
    tag = get_object_or_404(Tag, name=name)
    problems = list(open_problems().filter(tags=tag).prefetch_related("tags").order_by("id"))
    if not problems:
        raise Http404
    solved = solved_ids(request.user, [p.pk for p in problems])
    for p in problems:
        p.solved = p.pk in solved
    levels = dict(Problem.Difficulty.choices)
    by_level = [(levels[v], [p for p in problems if p.difficulty == v]) for v in levels]
    return render(request, "learn/topic.html", {
        "tag": tag, "theory_html": _render_statement(tag.about_md), "n": len(problems), "done": len(solved),
        "by_level": [(label, ps) for label, ps in by_level if ps],
        "plans": (StudyPlan.objects.filter(is_public=True, sections__items__problem__in=problems).distinct()),
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

