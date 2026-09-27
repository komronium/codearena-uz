from django.utils import timezone
from django.utils.functional import SimpleLazyObject


def streak(request):
    """The header's streak pill. Lazy: htmx partials and pages that don't draw the
    header never run its queries. It only reads today's problem: picking one is left
    to the pages that show it (home, the problem list), so a header never writes."""
    if not request.user.is_authenticated:
        return {}

    def pill():
        from .daily import streaks
        from .models import DailyProblem, DailySolve

        daily = DailyProblem.objects.filter(date=timezone.localdate()).select_related("problem").first()
        return {"daily": daily, "current": streaks(request.user)[0],
                "done": daily is not None and DailySolve.objects.filter(user=request.user, daily=daily).exists()}

    return {"streak_pill": SimpleLazyObject(pill)}
