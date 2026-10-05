"""sitemap.xml: the public pages a search engine should find, one sitemap per kind under an index. Staff
tools, personal pages, profiles with nothing on them and the problems of a round that hasn't started stay
out; robots.txt and the pages' own robots meta keep crawlers away from them too. lastmod is when the page
last really changed: an edit, a round starting or ending, a profile's latest solve."""
from django.contrib import sitemaps
from django.db.models import Exists, OuterRef, Subquery
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.contests.models import Contest, Participation
from apps.learn.models import StudyPlan
from apps.problems.models import Problem
from apps.submissions.models import UserProblemSolved


class Sections(sitemaps.Sitemap):
    def items(self):
        return ["home", "problems:list", "learn:hub", "contests:list", "rating", "top", "honor"]

    def location(self, name):
        return reverse(name)


class Problems(sitemaps.Sitemap):
    def items(self):
        # the problem list's own rule
        return (Problem.objects.filter(is_public=True).exclude(contests__start__gt=timezone.now())
                .distinct().order_by("pk").only("slug", "updated"))

    def location(self, problem):
        return reverse("problems:detail", args=[problem.slug])

    def lastmod(self, problem):
        return problem.updated


class Courses(sitemaps.Sitemap):
    def items(self):
        return StudyPlan.objects.filter(is_public=True).order_by("order", "pk").only("slug", "updated")

    def location(self, plan):
        return reverse("learn:course", args=[plan.slug])

    def lastmod(self, plan):
        return plan.updated


def _public_contests():
    # a round for one group is no page for the public to land on
    return Contest.objects.filter(require_group__isnull=True).order_by("-start").only("pk", "start", "end", "updated")


class Contests(sitemaps.Sitemap):
    def items(self):
        return _public_contests()

    def location(self, contest):
        return reverse("contests:detail", args=[contest.pk])

    def lastmod(self, contest):
        # its problems open at the start and its numbers settle at the end
        now = timezone.now()
        return max(moment for moment in (contest.updated, contest.start, contest.end) if moment <= now)


class Standings(sitemaps.Sitemap):
    """A round's results, once it has begun: what people search for after a round."""

    def items(self):
        return _public_contests().filter(start__lte=timezone.now())

    def location(self, contest):
        return reverse("contests:standings", args=[contest.pk])

    def lastmod(self, contest):
        return contest.end if contest.end <= timezone.now() else None


class Profiles(sitemaps.Sitemap):
    """Users with something to show: a public problem solved or a rated round. The rest say noindex
    themselves (accounts/profile.html), as do blocked users."""

    def items(self):
        solved = UserProblemSolved.objects.filter(user=OuterRef("pk"), problem__is_public=True)
        rated = Participation.objects.filter(user=OuterRef("pk"), rating_after__isnull=False)
        return (User.objects.filter(Exists(solved) | Exists(rated), is_active=True)
                .annotate(last_solve=Subquery(solved.order_by("-solved_at").values("solved_at")[:1]),
                          last_round=Subquery(rated.order_by("-contest__end").values("contest__end")[:1]))
                .order_by("pk").only("username"))

    def location(self, user):
        return reverse("profile", args=[user.username])

    def lastmod(self, user):
        return max((moment for moment in (user.last_solve, user.last_round) if moment), default=None)


SITEMAPS = {"sections": Sections, "problems": Problems, "courses": Courses, "contests": Contests,
            "standings": Standings, "profiles": Profiles}
