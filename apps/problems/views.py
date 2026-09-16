import markdown
from django.shortcuts import get_object_or_404, render

from .models import Language, Problem


def problem_list(request):
    problems = Problem.objects.filter(is_public=True).order_by("id")
    return render(request, "problems/list.html", {"problems": problems})


def problem_detail(request, slug):
    problem = get_object_or_404(Problem, slug=slug, is_public=True)
    return render(request, "problems/detail.html", {
        "problem": problem,
        "statement_html": markdown.markdown(problem.statement_md, extensions=["tables", "fenced_code"]),
        "languages": Language.objects.filter(is_active=True),
    })
