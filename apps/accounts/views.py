from django.contrib.auth import login
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from apps.problems.models import Problem

from .forms import RegisterForm
from .models import User


def register(request):
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("problems:list")
    return render(request, "registration/register.html", {"form": form})


def top(request):
    qs = User.objects.order_by("-practice_points", "username")
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    return render(request, "accounts/top.html", {"users": page})


def rating(request):
    qs = User.objects.order_by("-rating", "username")
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    return render(request, "accounts/rating.html", {"users": page})


def profile(request, username):
    profile_user = get_object_or_404(User, username=username)
    solved = Problem.objects.filter(userproblemsolved__user=profile_user, is_public=True).order_by("title")
    return render(request, "accounts/profile.html", {"profile_user": profile_user, "solved": solved})
