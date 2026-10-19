import random
from collections import Counter

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.db.models.functions import Coalesce
from django.http import Http404, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import Follow, User
from apps.accounts.tiers import tier_color

from . import duels
from apps.accounts.badges import board as badge_board
from .models import Duel, DuelAnswer, DuelQuestion


@login_required
def duel_list(request):
    duels.settle_open(request.user)
    error = ""
    if request.method == "POST":
        language = request.POST.get("language", "")
        if "find" in request.POST:
            duel, error = duels.find_opponent(request.user, language)
        else:
            duel, error = duels.challenge(request.user, request.POST.get("opponent", ""), language)
        if duel is not None:
            return redirect("classroom:duel_play", duel.pk)
    # newest end first: a finished duel by when it ended, an open one by when it was made (Duel.ended_at)
    mine = (Duel.objects.filter(Q(challenger=request.user) | Q(opponent=request.user))
            .select_related("challenger", "opponent", "winner")
            .order_by(Coalesce("finished_at", "created").desc(), "-pk"))
    joinable = duels.joinable_counts(request.user)
    finished = [d for d in mine if d.status == Duel.Status.FINISHED]
    record = {"wins": sum(1 for d in finished if d.winner_id == request.user.pk),
              "losses": sum(1 for d in finished if d.winner_id and d.winner_id != request.user.pk)}
    record["draws"] = len(finished) - record["wins"] - record["losses"]
    # the duel board: everyone with a finished duel, by duel rating
    played = Counter()
    for pair in Duel.objects.filter(status=Duel.Status.FINISHED).values_list("challenger_id", "opponent_id"):
        played.update(pair)
    played.pop(None, None)
    board = list(User.objects.filter(pk__in=played, is_active=True).order_by("-duel_rating", "username")
                 .only("username", "rating", "duel_rating")[:10])
    for u in board:
        u.duels = played[u.pk]
    rank = (User.objects.filter(pk__in=played, is_active=True, duel_rating__gt=request.user.duel_rating).count() + 1
            if request.user.pk in played else None)
    open_duels = [d for d in mine if d.status in duels.OPEN
                  and not (d.status == Duel.Status.PENDING and d.opponent_id == request.user.pk)]
    # how far you are through each running duel: "3 / 5 savol"
    done = dict(DuelAnswer.objects.filter(duel__in=open_duels, user=request.user, answered_at__isnull=False)
                .values_list("duel_id").annotate(n=Count("id")))
    for d in open_duels:
        d.my_done = done.get(d.pk, 0)
    return render(request, "classroom/duels.html", {
        "record": record, "board": board, "duel_rank": rank, "duelists": len(played),
        "incoming": [d for d in mine if d.status == Duel.Status.PENDING and d.opponent_id == request.user.pk],
        "open": open_duels,
        # an open duel nobody joined was never a duel: it stays out of the record
        "history": [d for d in mine if d.status not in duels.OPEN and d.opponent_id][:30],
        "error": error, "languages": duels.LANGUAGES, "joinable": joinable,
        "form": request.POST if error else {"opponent": request.GET.get("opponent", "")[:150]}, "per_question": int(duels.PER_QUESTION.total_seconds()),
        "n_questions": duels.QUESTIONS, "badges": badge_board(request.user, {"duels"}),
    })


@login_required
def duel_people(request):
    """Who to challenge, for the duel form's finder (handles are hard to remember): with nothing typed the people
    you follow and the people you have duelled, else up to 8 active users whose handle holds the text, the
    exact handle first, then those starting with it."""
    q = request.GET.get("q", "").strip()[:30]
    people = User.objects.filter(is_active=True).exclude(pk=request.user.pk)
    followed = set(Follow.objects.filter(user=request.user).values_list("target_id", flat=True))
    if q:
        found = (people.filter(username__icontains=q)
                 .annotate(rank=Case(When(username__iexact=q, then=Value(0)),
                                     When(username__istartswith=q, then=Value(1)),
                                     default=Value(2), output_field=IntegerField()))
                 .order_by("rank", "username")[:8])
    else:
        pairs = (Duel.objects.filter(Q(challenger=request.user) | Q(opponent=request.user), opponent__isnull=False)
                 .order_by("-pk").values_list("challenger_id", "opponent_id")[:30])
        rivals = {b if a == request.user.pk else a for a, b in pairs}
        found = people.filter(pk__in=followed | rivals).order_by("username")[:8]
    return JsonResponse({"results": [{"username": u.username, "color": tier_color(u.rating), "duel": u.duel_rating,
                                      "followed": u.pk in followed} for u in found]})


def _my_duel(request, pk):
    duel = get_object_or_404(Duel.objects.select_related("challenger", "opponent", "winner"), pk=pk)
    if request.user.pk not in duel.players() and not request.user.is_staff:
        raise Http404
    return duel


@login_required
@require_POST
def duel_rematch(request, pk):
    """Revansh: the same opponent and language, new questions; your run starts now, as any challenge."""
    duel = _my_duel(request, pk)
    other = duel.opponent if request.user.pk == duel.challenger_id else duel.challenger
    if other is None or request.user.pk not in duel.players():
        raise Http404
    new, error = duels.challenge(request.user, other.username, duel.language or "python")
    if new is None:
        messages.error(request, error)
        return redirect("classroom:duel", duel.pk)
    return redirect("classroom:duel_play", new.pk)


@login_required
@require_POST
def duel_answer(request, pk):
    duel = _my_duel(request, pk)
    if request.POST.get("accept") == "1":
        if duel.opponent_id != request.user.pk:
            raise Http404
        error = duels.accept(duel, request.user)
        if error:
            messages.error(request, error)
        else:
            return redirect("classroom:duel_play", duel.pk)
    else:
        duels.decline(duel, request.user)
    return redirect("classroom:duel", duel.pk)


@login_required
def duel_detail(request, pk):
    duel = _my_duel(request, pk)
    duels.settle(duel)
    duel.refresh_from_db()
    board = _duel_board(duel, request.user)
    state = f"{duel.status}.{duel.opponent_id or 0}.{board['my_over']}"
    if request.headers.get("HX-Request"):
        seen = request.GET.get("seen")
        if seen and seen != state:  # someone joined, a run ended, or the duel did: the whole page changes
            return HttpResponse(headers={"HX-Refresh": "true"})
        template = "classroom/_duel_status.html"
    else:
        template = "classroom/duel.html"
    return render(request, template, {"duel": duel, "state": state, **board})


def _rival(me, other) -> dict:
    """What you know about the other player: their duel record and your score against each other."""
    played = Duel.objects.filter(status=Duel.Status.FINISHED, mode=Duel.Mode.QUIZ).filter(
        Q(challenger=other) | Q(opponent=other))
    wins = played.filter(winner=other).count()
    total = played.count()
    h2h = played.filter(Q(challenger=me) | Q(opponent=me))
    return {"user": other, "wins": wins, "losses": total - wins - played.filter(winner__isnull=True).count(),
            "total": total, "you": h2h.filter(winner=me).count(), "them": h2h.filter(winner=other).count()}


def _secs(t) -> str:
    return f"{t.total_seconds():.1f}".replace(".", ",")


def _duel_board(duel, viewer) -> dict:
    """Both players' runs side by side, open to both like a live standings row: how many right, the time
    spent, and a cell per question (right, wrong, on it, not yet). The questions themselves, with the
    answers, only once your own run is over, so nobody sees them before playing."""
    now = timezone.now()
    rows, runs = [], {}
    for u, delta in ((duel.challenger, duel.challenger_delta), (duel.opponent, duel.opponent_delta)):
        r = duels.run(duel, u.pk) if u and duel.mode == Duel.Mode.QUIZ else None
        runs[u.pk if u else None] = r
        cells = []
        if r is not None:
            for a in r.answers:
                state = "ok" if a.correct else ("bad" if r.closed(a, now) else "now")
                took = min(a.answered_at - a.shown_at, duels.PER_QUESTION) if a.answered_at else None
                cells.append({"state": state, "secs": _secs(took) if took is not None else ""})
            if r.over(now):
                cells += [{"state": "bad", "secs": ""}] * (duels.QUESTIONS - len(cells))
            cells += [{"state": "", "secs": ""}] * (duels.QUESTIONS - len(cells))
        rows.append({"user": u, "run": r, "delta": delta, "winner": u is not None and duel.winner_id == u.pk,
                     "over": r is not None and r.over(now), "right": r.right if r else 0,
                     "spent": _secs(r.spent(now)) if r is not None and r.over(now) else "", "cells": cells})
    mine = runs.get(viewer.pk)
    my_over = mine is not None and mine.over(now)
    review = []
    watcher = viewer.is_staff and viewer.pk not in duel.players()  # staff sees both players' answers any time
    if duel.mode == Duel.Mode.QUIZ and (my_over or watcher):
        if watcher:
            sides = [(u.username, runs.get(u.pk)) for u in (duel.challenger, duel.opponent) if u]
        else:
            other = duel.opponent if viewer.pk == duel.challenger_id else duel.challenger
            sides = [("Siz", mine), ("Raqib" if other is None else other.username, runs.get(other.pk) if other else None)]
        sides = [(label, r, {a.index: a for a in r.answers} if r else {}, r is not None and r.over(now) or watcher)
                 for label, r in sides]
        questions = DuelQuestion.objects.in_bulk(duel.questions)
        for i, qid in enumerate(duel.questions):
            q = questions.get(qid)
            if q is None:
                continue
            review.append({"n": i + 1, "q": q, "answers": [
                {"label": label, "a": by_index.get(i), "pending": not shown, "unseen": r is None or i >= len(r.answers)}
                for label, r, by_index, shown in sides]})
    # the end, from your side: won, lost or drawn, the score and your rating change; and a rematch either way
    result = None
    if duel.status == Duel.Status.FINISHED and viewer.pk in duel.players() and duel.mode == Duel.Mode.QUIZ:
        me_row = next(r for r in rows if r["user"] and r["user"].pk == viewer.pk)
        them = next((r for r in rows if r["user"] and r["user"].pk != viewer.pk), None)
        other = them["user"] if them else None
        result = {"state": "draw" if duel.winner_id is None else ("win" if duel.winner_id == viewer.pk else "loss"),
                  "mine": me_row["right"], "theirs": them["right"] if them else 0, "delta": me_row["delta"] or 0,
                  "other": other,
                  "offer": (Duel.objects.filter(challenger=other, opponent=viewer, status=Duel.Status.PENDING,
                                                created__gt=duel.created).first() if other else None),
                  "sent": (Duel.objects.filter(challenger=viewer, opponent=other, status__in=duels.OPEN,
                                               created__gt=duel.created).first() if other else None)}
    rival = None
    if duel.opponent_id and viewer.pk in duel.players() and (result or duel.status == Duel.Status.PENDING):
        rival = _rival(viewer, duel.challenger if viewer.pk == duel.opponent_id else duel.opponent)
    return {
        "result": result, "rival": rival,
        "players": rows, "review": review, "my_over": my_over,
        "my_playing": mine is not None and not my_over,
        "my_started": bool(mine and mine.answers),
        "per_question": int(duels.PER_QUESTION.total_seconds()), "n_questions": duels.QUESTIONS,
        "expires": duel.created + duels.WAIT_FOR,
    }


def _shuffled(options, seed) -> list:
    out = list(options)
    random.Random(seed).shuffle(out)
    return out


@login_required
def duel_play(request, pk):
    """Your run: one question at a time with its own 20 seconds (from when the server first showed it, so a
    reload doesn't reset it). An answer gets only its verdict, right or wrong (never the right answer: that
    waits for the review after the run), and the next question follows by itself. The page sends answers
    with fetch and gets the verdict as JSON; without script, the verdict page moves on with a refresh."""
    duel = _my_duel(request, pk)
    if duel.mode != Duel.Mode.QUIZ or request.user.pk not in duel.players():
        return redirect("classroom:duel", duel.pk)
    play_url = reverse("classroom:duel_play", args=[duel.pk])
    if request.method == "POST":
        try:
            index = int(request.POST.get("index", ""))
        except ValueError:
            return HttpResponseBadRequest()
        a = duels.answer(duel, request.user, index, request.POST.get("answer", ""))
        if request.headers.get("X-Duel-Answer") == "1":
            if a is None:
                return JsonResponse({"next": play_url})
            verdict = _verdict(duel, request.user, a)
            ghost = _ghost(duel, request.user, a.index)
            return JsonResponse({"verdict": verdict["state"], "next": verdict["next"],
                                 "ghost": ghost["now"] if ghost else None})
        return redirect(play_url + f"?after={index}")
    asked = request.GET.get("ghost")
    if asked is not None and asked.isdigit():
        if not DuelAnswer.objects.filter(duel=duel, user=request.user, index=int(asked)).exists():
            return JsonResponse({"state": "none"})  # only a question you have been shown
        ghost = _ghost(duel, request.user, int(asked))
        return JsonResponse(ghost["now"] if ghost else {"state": "none"})
    after = request.GET.get("after")
    if after is not None and after.isdigit():
        a = DuelAnswer.objects.filter(duel=duel, user=request.user, index=int(after)).first()
        r = duels.run(duel, request.user.pk)
        if a is not None and r is not None and r.closed(a, timezone.now()):
            return render(request, "classroom/duel_play.html", {
                "duel": duel, "verdict": _verdict(duel, request.user, a), "n": a.index + 1,
                "n_questions": duels.QUESTIONS, "cells": _my_cells(r), "language": duel.get_language_display()})
    current = duels.current(duel, request.user)
    if current is None:
        return redirect("classroom:duel", duel.pk)
    q = current.question
    r = duels.run(duel, request.user.pk)
    return render(request, "classroom/duel_play.html", {
        "duel": duel, "a": current, "q": q, "n": current.index + 1, "n_questions": duels.QUESTIONS,
        "remaining_ms": max(0, int((current.shown_at + duels.PER_QUESTION - timezone.now()).total_seconds() * 1000)),
        "per_question": int(duels.PER_QUESTION.total_seconds()),
        "options": _shuffled(q.options, f"{duel.pk}-{request.user.pk}-{current.index}"),
        "cells": _my_cells(r), "language": duel.get_language_display(),
        "my_right": r.right, "ghost": _ghost(duel, request.user, current.index),
    })


def _ghost(duel, me, index: int) -> dict | None:
    """The opponent as a ghost beside your run: how they did on the questions before this one (right,
    wrong, or not there yet) and on this one, when they answered it, so the page can show it as your clock
    reaches that moment. Never their answer, only right or wrong and the time. None with no opponent."""
    other = duel.opponent if me.pk == duel.challenger_id else duel.challenger
    if other is None:
        return None
    r = duels.run(duel, other.pk)
    if r is None:
        return {"name": other.username, "absent": True, "past": [], "right": 0, "now": {"state": "absent"}}
    now = timezone.now()
    by_index = {a.index: a for a in r.answers}

    def cell(i):
        a = by_index.get(i)
        if a is None or not r.closed(a, now):
            return {"state": "bad" if r.over(now) else "wait"}  # a question they never saw counts wrong
        late = a.answered_at is None or a.answered_at > a.shown_at + duels.PER_QUESTION + duels.GRACE
        took = min(a.answered_at - a.shown_at, duels.PER_QUESTION) if a.answered_at else duels.PER_QUESTION
        return {"state": "ok" if a.correct else ("late" if late or not a.answer else "bad"),
                "took_ms": int(took.total_seconds() * 1000), "secs": f"{took.total_seconds():.1f}".replace(".", ",")}
    past = [cell(i) for i in range(index)]
    return {"name": other.username, "absent": False, "past": past,
            "right": sum(1 for c in past if c["state"] == "ok"), "now": cell(index)}


def _verdict(duel, user, a) -> dict:
    """How an answered (or timed out) question went, and where the run goes next."""
    late = a.answered_at is None or a.answered_at > a.shown_at + duels.PER_QUESTION + duels.GRACE
    state = "ok" if a.correct else ("late" if late or not a.answer else "bad")
    r = duels.run(duel, user.pk)
    over = r is None or r.over(timezone.now())
    return {"state": state, "last": over,
            "next": reverse("classroom:duel", args=[duel.pk]) if over else reverse("classroom:duel_play", args=[duel.pk])}


def _my_cells(r) -> list[str]:
    now = timezone.now()
    cells = ["ok" if a.correct else ("bad" if r.closed(a, now) else "now") for a in r.answers]
    return cells + [""] * (duels.QUESTIONS - len(cells))
