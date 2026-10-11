from django import template
from django.core.cache import cache

register = template.Library()


@register.simple_tag
def site_counts() -> dict:
    """The sign-in pages' three figures (open problems, rounds, judged solutions), cached for ten minutes."""
    counts = cache.get("site-counts")
    if counts is None:
        from apps.contests.models import Contest
        from apps.problems.skills import open_problems
        from apps.submissions.models import Submission
        counts = {"problems": open_problems().count(), "contests": Contest.objects.count(),
                  "submissions": Submission.objects.count()}
        cache.set("site-counts", counts, 600)
    return counts
