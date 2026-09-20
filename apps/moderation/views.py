from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from apps.problems.models import Problem

from .forms import ProblemForm, TestCaseFormSet


def _unique_slug(title: str) -> str:
    base = slugify(title) or "masala"
    slug, n = base, 2
    while Problem.objects.filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


@login_required
def submit(request):
    if request.method == "POST":
        form = ProblemForm(request.POST)
        formset = TestCaseFormSet(request.POST, instance=form.instance, prefix="testcases")
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                problem = form.save(commit=False)
                problem.author = request.user
                problem.slug = _unique_slug(problem.title)
                if request.user.is_staff:
                    problem.status = Problem.Status.APPROVED
                    problem.is_public = True
                else:
                    problem.status = Problem.Status.PENDING
                    problem.is_public = False
                problem.save()
                formset.save()
            return redirect("problems:detail", problem.slug)
    else:
        form = ProblemForm()
        formset = TestCaseFormSet(prefix="testcases")
    return render(request, "moderation/submit.html", {"form": form, "formset": formset})


@staff_member_required
def queue(request):
    problems = (Problem.objects.filter(status=Problem.Status.PENDING)
                .select_related("author").order_by("created"))
    return render(request, "moderation/queue.html", {"problems": problems})


@staff_member_required
@require_POST
def approve(request, pk):
    problem = get_object_or_404(Problem, pk=pk, status=Problem.Status.PENDING)
    problem.status = Problem.Status.APPROVED
    problem.is_public = True
    problem.save(update_fields=["status", "is_public"])
    return redirect("moderation:queue")


@staff_member_required
@require_POST
def reject(request, pk):
    problem = get_object_or_404(Problem, pk=pk, status=Problem.Status.PENDING)
    problem.status = Problem.Status.REJECTED
    problem.save(update_fields=["status"])
    return redirect("moderation:queue")
