from django import template

from apps.accounts.tiers import streak_badges

from ..daily import month_strip, streaks, week_strip
from ..models import DailySolve

register = template.Library()


@register.simple_tag
def daily_stats(daily, user) -> dict:
    """What the problem list's daily box shows beside the problem: how many solved it today and
    a few of them, and for a signed-in user the run, this week's days and the next streak badge."""
    solves = DailySolve.objects.filter(daily=daily).select_related("user").order_by("-pk")
    out = {"solvers": solves.count(), "recent": [s.user for s in solves[:5]]}
    if user.is_authenticated:
        cur, best = streaks(user)
        out.update(streak=cur, best=best, week=week_strip(user), month=month_strip(user),
                   next_badge=streak_badges(cur, best)["next"])
    return out
