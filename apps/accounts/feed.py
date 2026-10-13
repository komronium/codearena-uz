"""The friends feed: what the people you follow, and your classmates, did lately. Derived from what is recorded (first
solves, duel wins, badge levels), so there is nothing to keep in step; only public problems are named."""
import datetime

from django.db.models import Q
from django.utils import timezone

from .models import Follow, User, UserBadge

LIMIT = 40
DAYS = 14


def circle(user) -> set[int]:
    """Whose doings the user sees: who they follow plus the members of their classes and their students."""
    ids = set(Follow.objects.filter(user=user).values_list("target_id", flat=True))
    for group in user.student_groups.all():
        ids |= set(group.members.values_list("pk", flat=True)) | {group.teacher_id}
    for group in user.taught_groups.all():
        ids |= set(group.members.values_list("pk", flat=True))
    ids.discard(user.pk)
    return ids


def events(user) -> list[dict]:
    from apps.classroom.models import Duel
    from apps.submissions.models import UserProblemSolved

    people = circle(user)
    if not people:
        return []
    since = timezone.now() - datetime.timedelta(days=DAYS)
    names = {u.pk: u for u in User.objects.filter(pk__in=people, is_active=True)}
    out = []
    for s in (UserProblemSolved.objects.filter(user_id__in=names, solved_at__gte=since, problem__is_public=True)
              .select_related("problem").order_by("-solved_at")[:LIMIT]):
        out.append({"at": s.solved_at, "user": names[s.user_id], "kind": "solve", "problem": s.problem})
    for d in (Duel.objects.filter(winner_id__in=names, status=Duel.Status.FINISHED, mode=Duel.Mode.QUIZ,
                                  created__gte=since).select_related("challenger", "opponent").order_by("-created")[:LIMIT]):
        loser = d.opponent if d.winner_id == d.challenger_id else d.challenger
        out.append({"at": d.created, "user": names[d.winner_id], "kind": "duel", "versus": loser})
    from .badges import BY_KEY, METALS, ROMAN
    for b in UserBadge.objects.filter(user_id__in=names, earned_at__gte=since).order_by("-earned_at")[:LIMIT]:
        fam = BY_KEY.get(b.family)
        if fam:
            out.append({"at": b.earned_at, "user": names[b.user_id], "kind": "badge", "badge": fam.name,
                        "level": ROMAN[b.tier], "icon": fam.icon})
    out.sort(key=lambda e: e["at"], reverse=True)
    return group(out)[:LIMIT]


GROUP_WINDOW = datetime.timedelta(hours=6)


def group(rows: list[dict]) -> list[dict]:
    """Eight solves by one person in a row read as one line, not eight: a person's consecutive solves (or badges)
    within a few hours of each other merge into one entry carrying the list."""
    out: list[dict] = []
    for e in rows:
        last = out[-1] if out else None
        if (e["kind"] in ("solve", "badge") and last and last["kind"] == e["kind"] and last["user"] == e["user"]
                and last["first_at"] - e["at"] <= GROUP_WINDOW):
            last["items"].append(e)
            continue
        if e["kind"] in ("solve", "badge"):
            out.append({"kind": e["kind"], "user": e["user"], "at": e["at"], "first_at": e["at"], "items": [e]})
        else:
            out.append(e)
    return out
