"""sitemap.xml: the public pages a search engine should find, one sitemap per kind under an index. Staff
tools, personal pages, profiles with nothing on them and the problems of a round that hasn't started stay
out; robots.txt and the pages' own robots meta keep crawlers away from them too. lastmod is when the page
last really changed: an edit, a round starting or ending, a profile's latest solve. Each page is listed in both
languages (/uz/... for Uzbek) with hreflang links to the other; a problem or course is listed only in the languages
it is written in or has a confirmed translation for, as its other page says noindex."""
from django.contrib import sitemaps
from django.db.models import Exists, OuterRef, Subquery
from django.urls import reverse
from django.utils import timezone, translation

from apps.accounts.language import localize
from apps.accounts.models import User
from apps.contests.models import Contest, Participation
from apps.learn.models import StudyPlan
from apps.problems.models import Problem
from apps.submissions.models import UserProblemSolved
from apps.translations.service import ready_ids


class Localized(sitemaps.Sitemap):
    """A sitemap of pages that exist in every language: path() is the page's plain address, location() puts the
    language of the entry in front of it. The pages of a model with translatable text list `translated` (the model)."""
    i18n = True
    alternates = True
    x_default = True
    translated = None  # the model whose English text readers must have, or None when every page has one

    def location(self, item):
        return localize(self.path(item), translation.get_language())

    def get_languages_for_item(self, item):
        if self.translated is None:
            return self._languages()
        if not hasattr(self, "_ready"):
            self._ready = {lang: ready_ids(self.translated, lang) for lang in self._languages()}
        # a language's address needs text in it: the author wrote it there, or an admin confirmed its translation
        return [lang for lang in self._languages() if item.pk in self._ready[lang]]


class Sections(Localized):
    def items(self):
        return ["home", "problems:list", "learn:hub", "contests:list", "rating", "top", "honor"]

    def path(self, name):
        return reverse(name)


class Problems(Localized):
    translated = Problem

    def items(self):
        # the problem list's own rule
        return (Problem.objects.filter(is_public=True).exclude(contests__start__gt=timezone.now())
                .distinct().order_by("pk").only("slug", "updated"))

    def path(self, problem):
        return reverse("problems:detail", args=[problem.slug])

    def lastmod(self, problem):
        return problem.updated


class Courses(Localized):
    translated = StudyPlan

    def items(self):
        return StudyPlan.objects.filter(is_public=True).order_by("order", "pk").only("slug", "updated")

    def path(self, plan):
        return reverse("learn:course", args=[plan.slug])

    def lastmod(self, plan):
        return plan.updated


def _public_contests():
    return Contest.objects.filter(is_draft=False).order_by("-start").only("pk", "start", "end", "updated")


class Contests(Localized):
    def items(self):
        return _public_contests()

    def path(self, contest):
        return reverse("contests:detail", args=[contest.pk])

    def lastmod(self, contest):
        # its problems open at the start and its numbers settle at the end
        now = timezone.now()
        return max(moment for moment in (contest.updated, contest.start, contest.end) if moment <= now)


class Standings(Localized):
    """A round's results, once it has begun: what people search for after a round."""

    def items(self):
        return _public_contests().filter(start__lte=timezone.now())

    def path(self, contest):
        return reverse("contests:standings", args=[contest.pk])

    def lastmod(self, contest):
        return contest.end if contest.end <= timezone.now() else None


class Profiles(Localized):
    """Users with something to show: a public problem solved or a rated round. The rest say noindex
    themselves (accounts/profile.html), as do blocked users."""

    def items(self):
        solved = UserProblemSolved.objects.filter(user=OuterRef("pk"), problem__is_public=True)
        rated = Participation.objects.filter(user=OuterRef("pk"), rating_after__isnull=False)
        return (User.objects.filter(Exists(solved) | Exists(rated), is_active=True)
                .annotate(last_solve=Subquery(solved.order_by("-solved_at").values("solved_at")[:1]),
                          last_round=Subquery(rated.order_by("-contest__end").values("contest__end")[:1]))
                .order_by("pk").only("username"))

    def path(self, user):
        return reverse("profile", args=[user.username])

    def lastmod(self, user):
        return max((moment for moment in (user.last_solve, user.last_round) if moment), default=None)


SITEMAPS = {"sections": Sections, "problems": Problems, "courses": Courses, "contests": Contests,
            "standings": Standings, "profiles": Profiles}
