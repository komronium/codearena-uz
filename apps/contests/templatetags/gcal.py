from datetime import timezone as dt_timezone
from urllib.parse import urlencode

from django import template
from django.urls import reverse

register = template.Library()


@register.simple_tag(takes_context=True)
def google_calendar_url(context, contest) -> str:
    """A link that opens Google Calendar's "new event" form with the round filled in (title, time, a link
    back), so adding it downloads nothing. Google applies the user's own default reminders."""
    def stamp(moment):
        return moment.astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    request = context.get("request")
    url = reverse("contests:detail", args=[contest.pk])
    url = request.build_absolute_uri(url) if request else url
    return "https://calendar.google.com/calendar/render?" + urlencode({
        "action": "TEMPLATE", "text": f"{contest.title} — CodeArena",
        "dates": f"{stamp(contest.start)}/{stamp(contest.end)}",
        "details": f"CodeArena musobaqasi, {contest.duration_label}.\n{url}", "location": url,
    })
