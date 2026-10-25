"""Plain dicts for the public API. Only what the site already shows to anyone: no emails, no source code, no drafts,
no problems of a round that has not begun. Times are ISO 8601 in UTC."""
import datetime as dt

from django.urls import reverse
from django.utils import timezone

from apps.accounts.countries import COUNTRIES
from apps.accounts.tiers import rating_tier, tier_color


def iso(moment):
    return moment.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z") if moment else None


def absolute(request, name, *args):
    return request.build_absolute_uri(reverse(name, args=args))


def status_of(contest, now=None) -> str:
    now = now or timezone.now()
    return "upcoming" if now < contest.start else "running" if now < contest.end else "past"


def board_hidden(contest) -> bool:
    """A personal-clock round keeps its problems and results shut until it ends: a late starter must not learn them."""
    return bool(contest.personal_minutes) and not contest.has_ended


def contest_problems_shown(contest) -> bool:
    return contest.has_started and not board_hidden(contest)


def contest_item(request, contest, n_participants=None) -> dict:
    n_problems = contest.contest_problems.count() if not hasattr(contest, "n_problems") else contest.n_problems
    return {
        "id": contest.pk,
        "key": str(contest.pk),
        "title": contest.title,
        "url": absolute(request, "contests:detail", contest.pk),
        "standings_url": absolute(request, "contests:standings", contest.pk),
        "start_time": iso(contest.start),
        "end_time": iso(contest.end),
        "duration_minutes": int((contest.end - contest.start).total_seconds() // 60),
        "personal_minutes": contest.personal_minutes or None,
        "status": status_of(contest),
        "kind": contest.kind,
        "number": contest.number,
        "division": contest.division or contest.named_division or None,
        "open_division": contest.division == 0,
        "rules": contest.type,
        "is_rated": contest.is_rated,
        "rating_applied": contest.rating_applied,
        "n_problems": n_problems,
        "n_participants": contest.n_participants if n_participants is None else n_participants,
        "authors": [a.username for a in contest.authors.all()],
        "updated": iso(contest.updated),
    }


def contest_problem_item(request, cp) -> dict:
    return {
        "label": cp.label,
        "title": cp.problem.title,
        "slug": cp.problem.slug,
        "url": absolute(request, "problems:detail", cp.problem.slug),
        "points": cp.points,
        "difficulty": cp.problem.difficulty,
        "rating": cp.problem.rating or None,
    }


def contest_detail(request, contest, description) -> dict:
    data = contest_item(request, contest)
    problems = (list(contest.contest_problems.select_related("problem").order_by("order", "pk"))
                if contest_problems_shown(contest) else [])
    data |= {
        "description_md": description,
        "language": contest.source_lang,
        "problems_hidden": not contest_problems_shown(contest),
        "problems": [contest_problem_item(request, cp) for cp in problems],
        "badge": contest.badge or None,
        "published": contest.published_at is not None,
        "calendar_url": absolute(request, "contests:calendar", contest.pk),
    }
    return data


def standings_row(request, row, labels) -> dict:
    """One participant's line. `place` is None for the round's authors (out of competition) and for the disqualified;
    `out_of_competition` also marks players outside the division's rating range, who are on the board but not rated."""
    user, part = row["user"], row["participation"]
    place = None if row["author"] or row["disqualified"] else row["rank"]
    return {
        "member": user.username,
        "name": user.get_full_name() or None,
        "country": user.country or None,
        "place": place,
        "score": row["score"],
        "solved": row["solved"],
        "penalty": row["penalty"],
        "rating_before": part.rating_before,
        "rating_after": part.rating_after,
        "rating_change": row["rating_delta"],
        "author": row["author"],
        "disqualified": row["disqualified"],
        "out_of_competition": row["author"] or row["out"],
        "problems": {label: result for label, c in zip(labels, row["cells"]) if (result := _cell(c)) is not None},
        "url": absolute(request, "profile", user.username),
    }


def _cell(c) -> dict | None:
    """A problem's result for one participant; None when they never touched it."""
    if not c["solved"] and not c["wrong"]:
        return None
    if c["solved"]:
        return {"result": "+", "points": c["points"], "wrong_tries": c["wrong"], "time": c["time"],
                "minutes": c["minutes"], "first_solve": bool(c.get("first")), "solved_at": iso(c["ac_at"])}
    return {"result": f"-{c['wrong']}", "points": 0, "wrong_tries": c["wrong"]}


def user_item(request, user, rank=None) -> dict:
    return {
        "username": user.username,
        "name": user.get_full_name() or None,
        "url": absolute(request, "profile", user.username),
        "rating": user.rating,
        "tier": rating_tier(user.rating),
        "tier_color": tier_color(user.rating),
        "rank": rank,
        "country": user.country or None,
        "country_name": str(COUNTRIES.get(user.country, "")) or None,
        "city": user.location or None,
        "school": user.school or None,
        "club": user.club.name if user.club_id else None,
        "practice_points": user.practice_points,
        "duel_rating": user.duel_rating,
        "joined": iso(user.date_joined),
    }


def rating_change_item(request, p) -> dict:
    return {
        "contest_id": p.contest_id,
        "contest": p.contest.title,
        "url": absolute(request, "contests:detail", p.contest_id),
        "date": iso(p.contest.end),
        "place": p.rank,
        "rating_before": p.rating_before,
        "rating_after": p.rating_after,
        "rating_change": p.rating_after - p.rating_before,
    }


def problem_item(request, problem, lang=None) -> dict:
    from apps.translations.mixin import confirmed_text

    def text(name):
        return (confirmed_text(problem, name, lang) if lang else None) or getattr(problem, name)

    return {
        "slug": problem.slug,
        "title": text("title"),
        "url": absolute(request, "problems:detail", problem.slug),
        "difficulty": problem.difficulty,
        "rating": problem.rating or None,
        "kind": problem.kind,
        "points": problem.points,
        "time_limit_ms": problem.tl_ms,
        "memory_limit_mb": problem.ml_mb,
        "tags": [t.name for t in problem.tags.all()],
        "language": problem.source_lang,
        "created": iso(problem.created),
        "updated": iso(problem.updated),
    }


def problem_detail(request, problem, lang=None) -> dict:
    from apps.translations.mixin import confirmed_text

    def text(name):
        return (confirmed_text(problem, name, lang) if lang else None) or getattr(problem, name)

    return problem_item(request, problem, lang) | {
        "statement_md": text("statement_md"),
        "input_md": text("input_md"),
        "output_md": text("output_md"),
        "samples": [{"input": t.input, "output": t.expected} for t in problem.samples],
    }
