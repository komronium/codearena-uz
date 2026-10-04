"""sitemap.xml: the public pages a search engine should find. Staff tools, personal pages and the
problems of a round that hasn't started stay out; robots.txt keeps crawlers away from them too."""
from django.contrib import sitemaps
from django.urls import reverse
from django.utils import timezone

from apps.contests.models import Contest
from apps.learn.models import StudyPlan
from apps.problems.models import Problem


class Sections(sitemaps.Sitemap):
    def items(self):
        return ["home", "problems:list", "learn:hub", "contests:list", "rating", "top", "honor"]

    def location(self, name):
        return reverse(name)


class Problems(sitemaps.Sitemap):
    def items(self):
        # the problem list's own rule
        return (Problem.objects.filter(is_public=True).exclude(contests__start__gt=timezone.now())
                .distinct().order_by("pk").only("slug"))

    def location(self, problem):
        return reverse("problems:detail", args=[problem.slug])


class Courses(sitemaps.Sitemap):
    def items(self):
        return StudyPlan.objects.filter(is_public=True).order_by("order", "pk").only("slug")

    def location(self, plan):
        return reverse("learn:course", args=[plan.slug])


class Contests(sitemaps.Sitemap):
    def items(self):
        # a round for one group is no page for the public to land on
        return Contest.objects.filter(require_group__isnull=True).order_by("-start").only("pk")

    def location(self, contest):
        return reverse("contests:detail", args=[contest.pk])


SITEMAPS = {"sections": Sections, "problems": Problems, "courses": Courses, "contests": Contests}
