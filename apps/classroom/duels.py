"""1v1 quiz duels, played on two clocks. Opening a duel starts the challenger's run at once on QUESTIONS
questions in one language, so nobody has to wait for anyone; the opponent gets the same
questions and their own run when they join. Each question has PER_QUESTION from the moment it is first
shown; a run left half-way ends RUN_LIMIT after its start, unseen questions counting as wrong. More right
answers wins; equal is a draw (time is only the 20 seconds a question gets, never a tie-break). Duel Elo moves once both runs
are over, by each player's own K (k_factor), as in chess: high for a newcomer, low at the top.

A duel names its opponent (a friend, who has WAIT_FOR to accept) or leaves the seat open: find_opponent
puts the next player who asks in that language into the open duel whose owner's duel rating is
closest to theirs, or opens a new one for them. A pair may play PAIR_LIMIT duels in 24 hours (Elo at half after the first PAIR_FULL_K). Each duel mixes levels by the pair's duel rating (MIX) and takes the questions
the two have seen least; the right answers are shown only once both runs are over. Duels before the quiz were coding races (mode "code"); they are history only."""
import random
from collections import Counter
from datetime import datetime, timedelta
from typing import NamedTuple

from django.db import IntegrityError, transaction
from django.db.models import Count, F, Q
from django.db.models.functions import Abs
from django.utils import timezone

from apps.accounts.models import User

from .models import Duel, DuelAnswer, DuelQuestion
from .quiz_check import norm

QUESTIONS = 5
PER_QUESTION = timedelta(seconds=20)
GRACE = timedelta(seconds=2)  # an answer's trip to the server at the last second
RUN_LIMIT = timedelta(minutes=5)
WAIT_FOR = timedelta(days=3)  # for someone to join an open duel, or for a friend to accept
START_RATING = 1200
OPEN = (Duel.Status.PENDING, Duel.Status.ACTIVE)
LANGUAGES = DuelQuestion.Lang.choices
BUSY = "Avval boshlagan duelingizni tugating."
NO_ADMIN = "Admin akkaunti duelda qatnasha olmaydi."


def can_duel(user) -> bool:
    """The admin account stays out of duels: it can't open, join or accept one, and nobody can invite it."""
    return not user.is_superuser


def k_factor(rating: int, played: int) -> int:
    """Chess-style K: 40 for the first 30 finished duels, so a new rating finds its place fast; then 20;
    10 from 2000 up, where a rating should be steady."""
    if played < 30:
        return 40
    return 10 if rating >= 2000 else 20


def elo(a: int, b: int, score: float, ka: int, kb: int) -> tuple[int, int]:
    """Rating changes of a and b for a's score (1 win, 0.5 draw, 0 loss)."""
    expected = 1 / (1 + 10 ** ((b - a) / 400))
    return round(ka * (score - expected)), round(kb * ((1 - score) - (1 - expected)))


PAIR_WINDOW = timedelta(hours=24)
PAIR_FULL_K = 10  # the first duels of a pair in 24 hours move the rating in full,
PAIR_LIMIT = 20  # the rest, up to this many, at half; the next one can't be sent, accepted or matched
COUNTED = (Duel.Status.PENDING, Duel.Status.ACTIVE, Duel.Status.FINISHED)  # a declined or expired one doesn't use a slot
PAIR_FULL = "Bu raqib bilan so‘nggi 24 soatda 20 ta duel o‘ynadingiz — keyinroq davom eting."


def pair_weight(duel) -> float:
    """How much of its K a duel's Elo counts: the same two trading duels all day would only pass points
    back and forth, so after PAIR_FULL_K finished duels between them in the 24 hours before this one it
    counts half. Counted from the data (not a counter), so replay() gives the same answer."""
    pair = [duel.challenger_id, duel.opponent_id]
    n = Duel.objects.filter(status=Duel.Status.FINISHED, mode=Duel.Mode.QUIZ, challenger_id__in=pair,
                            opponent_id__in=pair, created__lt=duel.created,
                            created__gte=duel.created - PAIR_WINDOW).count()
    return 1.0 if n < PAIR_FULL_K else 0.5


def pair_count(a_id: int, b_id: int, exclude=None) -> int:
    """Duels of this pair that used a slot in the last 24 hours."""
    qs = Duel.objects.filter(mode=Duel.Mode.QUIZ, status__in=COUNTED, challenger_id__in=[a_id, b_id],
                             opponent_id__in=[a_id, b_id], created__gte=timezone.now() - PAIR_WINDOW)
    return qs.exclude(pk=exclude).count() if exclude else qs.count()


def full_pairs(user_id: int) -> set[int]:
    """The people `user_id` has used all PAIR_LIMIT duels with in the last 24 hours."""
    seen = Counter()
    for c, o in (Duel.objects.filter(Q(challenger_id=user_id) | Q(opponent_id=user_id), mode=Duel.Mode.QUIZ,
                                     status__in=COUNTED, opponent__isnull=False,
                                     created__gte=timezone.now() - PAIR_WINDOW).values_list("challenger_id", "opponent_id")):
        seen[o if c == user_id else c] += 1
    return {uid for uid, n in seen.items() if n >= PAIR_LIMIT}


# ---- seasons ------------------------------------------------------------------------------------------
SEASON_KEEP = 0.5  # a new month keeps this share of how far a rating is from START_RATING
SEASON_MIN_DUELS = 3  # the podium is for players with at least this many finished duels that month


def season_of(moment) -> str:
    """The month (YYYY-MM, local time) a moment falls in."""
    return timezone.localtime(moment).strftime("%Y-%m")


def duel_season(duel) -> str:
    """The season a finished duel counts for: the month it ended (it created, if no clock was kept)."""
    return season_of(max(filter(None, [duel.ends_at, duel.opponent_ends_at, duel.created])))


def _month_no(season: str) -> int:
    y, m = season.split("-")
    return int(y) * 12 + int(m)


def soften(rating: int, steps: int = 1) -> int:
    """The rating after `steps` season changes: pulled part of the way back to START_RATING."""
    for _ in range(max(steps, 0)):
        rating = START_RATING + round((rating - START_RATING) * SEASON_KEEP)
    return rating


def carried(rating: int, was: str, now: str) -> int:
    """A player's rating as the season `now` starts, when it was last settled in season `was` ("" = never)."""
    return soften(rating, _month_no(now) - _month_no(was)) if was and was < now else rating


def current_season() -> str:
    return season_of(timezone.now())


def season_ends():
    """When the running season ends: the first moment of next month, local time."""
    now = timezone.localtime()
    y, m = (now.year + 1, 1) if now.month == 12 else (now.year, now.month + 1)
    return timezone.make_aware(datetime(y, m, 1), timezone.get_current_timezone())


def season_tables() -> dict[str, list[dict]]:
    """For every season with finished duels: players' rating after their last duel in it, with how many they played.
    One pass over the duels, applying the same month changes as settle()."""
    rating, last, table = {}, {}, {}
    for d in Duel.objects.filter(status=Duel.Status.FINISHED).order_by("created", "pk"):
        season = duel_season(d)
        for uid, delta in ((d.challenger_id, d.challenger_delta), (d.opponent_id, d.opponent_delta)):
            r = carried(rating.get(uid, START_RATING), last.get(uid, ""), season) + (delta or 0)
            rating[uid], last[uid] = r, season
            row = table.setdefault(season, {}).setdefault(uid, {"user_id": uid, "rating": r, "duels": 0})
            row["rating"], row["duels"] = r, row["duels"] + 1
    return {s: sorted(rows.values(), key=lambda r: (-r["rating"], -r["duels"], r["user_id"])) for s, rows in table.items()}


def close_seasons() -> None:
    """Store the podium of every finished month that has none yet. Cheap to call: it only does the pass when a past
    month has duels but no stored result."""
    from .models import DuelSeasonResult

    now = current_season()
    done = set(DuelSeasonResult.objects.values_list("season", flat=True))
    past = {duel_season(d) for d in Duel.objects.filter(status=Duel.Status.FINISHED).only(
        "created", "ends_at", "opponent_ends_at")}
    todo = {s for s in past if s < now and s not in done}
    if not todo:
        return
    tables = season_tables()
    for season in sorted(todo):
        eligible = [r for r in tables.get(season, []) if r["duels"] >= SEASON_MIN_DUELS][:3]
        for rank, r in enumerate(eligible, 1):
            DuelSeasonResult.objects.get_or_create(season=season, rank=rank, defaults={
                "user_id": r["user_id"], "rating": r["rating"], "duels": r["duels"]})
        if not eligible:  # a quiet month: leave a marker, or it would be worked out again on every visit
            DuelSeasonResult.objects.get_or_create(season=season, rank=0, defaults={"user": None, "rating": 0, "duels": 0})


# ---- one player's run ----------------------------------------------------------------------------------
class Run(NamedTuple):
    start: datetime
    end: datetime
    answers: list  # DuelAnswer rows by index: the questions shown so far

    def closed(self, a, now) -> bool:
        """Answered, or its time is up."""
        return a.answered_at is not None or now > a.shown_at + PER_QUESTION + GRACE

    def over(self, now) -> bool:
        return now >= self.end or (len(self.answers) == QUESTIONS and all(self.closed(a, now) for a in self.answers))

    @property
    def right(self) -> int:
        return sum(1 for a in self.answers if a.correct)

    def spent(self, now) -> timedelta:
        """Time on the questions: an answered one as taken, any other its full PER_QUESTION."""
        total = timedelta()
        for a in self.answers:
            took = a.answered_at - a.shown_at if a.answered_at else PER_QUESTION
            total += min(took, PER_QUESTION)
        return total + PER_QUESTION * (QUESTIONS - len(self.answers))


def run(duel, user_id) -> Run | None:
    """None until that player's clock starts (an opponent who hasn't joined yet)."""
    clock = duel.clock(user_id)
    if clock is None:
        return None
    answers = list(DuelAnswer.objects.filter(duel=duel, user_id=user_id).select_related("question").order_by("index"))
    return Run(clock[0], clock[1], answers)


def _winner(duel, now) -> int | None:
    """The winner's id, 0 for a draw, None while a run still goes on."""
    a, b = run(duel, duel.challenger_id), run(duel, duel.opponent_id)
    if a is None or b is None or not a.over(now) or not b.over(now):
        return None
    if a.right == b.right:
        return 0
    return duel.challenger_id if a.right > b.right else duel.opponent_id


def is_right(question, given: str) -> bool:
    if question.options:
        return given == question.answer
    return norm(given) != "" and norm(given) in {norm(question.answer), *map(norm, question.accept)}


def current(duel, user, now=None):
    """The question `user` is on, shown from now if it wasn't yet: the last one shown while its time
    runs, else the next one. None when the run is over."""
    now = now or timezone.now()
    r = run(duel, user.pk)
    if r is None or r.over(now):
        return None
    if r.answers and not r.closed(r.answers[-1], now):
        return r.answers[-1]
    index = len(r.answers)
    try:
        with transaction.atomic():
            return DuelAnswer.objects.create(duel=duel, user=user, index=index, question_id=duel.questions[index],
                                             shown_at=now)
    except IntegrityError:  # a second tab got there first
        return DuelAnswer.objects.select_related("question").get(duel=duel, user=user, index=index)


def answer(duel, user, index: int, given: str, now=None) -> DuelAnswer | None:
    """Record an answer to question `index`; one too late counts as wrong. The first answer stays."""
    now = now or timezone.now()
    a = DuelAnswer.objects.select_related("question").filter(duel=duel, user=user, index=index).first()
    if a is None or a.answered_at is not None:
        return a
    a.answered_at, a.answer = now, given.strip()[:200]
    a.correct = now <= a.shown_at + PER_QUESTION + GRACE and is_right(a.question, a.answer)
    a.save(update_fields=["answered_at", "answer", "correct"])
    settle(duel)
    return a


# ---- starting duels --------------------------------------------------------------------------------------
def _lock(user) -> None:
    """One duel start per user at a time, so a double click can't open two."""
    User.objects.select_for_update().filter(pk=user.pk).first()


def _busy(user, now) -> bool:
    """A run of yours still goes on."""
    for duel in Duel.objects.filter(Q(challenger=user) | Q(opponent=user), status__in=OPEN, mode=Duel.Mode.QUIZ):
        r = run(duel, user.pk)
        if r is not None and not r.over(now):
            return True
    return False


def _seen(users) -> set[int]:
    return set(DuelAnswer.objects.filter(user__in=users).values_list("question_id", flat=True))


# (beginner, easy, medium) questions of the five, by the pair's average duel rating: mostly easy ones for
# everybody, a medium only for the strong
MIX = ((1100, (3, 2, 0)), (1500, (2, 3, 0)), (10 ** 9, (1, 3, 1)))


def _mix(users) -> tuple[int, int, int]:
    ids = [getattr(u, "pk", u) for u in users]
    ratings = list(User.objects.filter(pk__in=ids).values_list("duel_rating", flat=True)) or [START_RATING]
    avg = sum(ratings) / len(ratings)
    return next(mix for limit, mix in MIX if avg < limit)


def _pick(users, language: str) -> list[int] | None:
    """QUESTIONS questions in the level mix, the ones none of `users` has seen first, then the ones asked
    least often overall (so the bank wears evenly); shorter levels are topped up from the others."""
    rows = list(DuelQuestion.objects.filter(language=language, is_active=True).values_list("pk", "level"))
    if len(rows) < QUESTIONS:
        return None
    seen = _seen(users)
    asked = dict(DuelAnswer.objects.filter(question_id__in=[pk for pk, _ in rows]).values("question_id")
                 .annotate(n=Count("id")).values_list("question_id", "n"))
    order = {pk: (pk in seen, asked.get(pk, 0), random.random()) for pk, _ in rows}
    by_level = {lvl: sorted((pk for pk, l in rows if l == lvl), key=order.get) for lvl in ("beginner", "easy", "medium")}
    picked: list[int] = []
    for lvl, n in zip(("beginner", "easy", "medium"), _mix(users)):
        picked += by_level[lvl][:n]
    if len(picked) < QUESTIONS:  # a level with too few: the best of the rest
        rest = sorted((pk for pk, _ in rows if pk not in picked), key=order.get)
        picked += rest[:QUESTIONS - len(picked)]
    random.shuffle(picked)
    return picked


def _valid(language: str) -> str:
    if language not in dict(LANGUAGES):
        return "Tilni tanlang."
    return ""


def _open(challenger, language: str, questions: list[int], opponent=None) -> Duel:
    now = timezone.now()
    return Duel.objects.create(challenger=challenger, opponent=opponent, language=language,
                               questions=questions, started_at=now, ends_at=now + RUN_LIMIT)


def _join(duel, user) -> None:
    now = timezone.now()
    duel.opponent = user
    duel.opponent_started_at, duel.opponent_ends_at = now, now + RUN_LIMIT
    duel.status = Duel.Status.ACTIVE
    duel.save(update_fields=["opponent", "opponent_started_at", "opponent_ends_at", "status"])


def joinable(user):
    """Open duels `user` could be put into: someone else's, still waiting."""
    return (Duel.objects.filter(mode=Duel.Mode.QUIZ, status=Duel.Status.PENDING, opponent__isnull=True,
                                created__gt=timezone.now() - WAIT_FOR)
            .exclude(challenger=user).exclude(challenger_id__in=full_pairs(user.pk)))


def joinable_counts(user) -> dict[str, int]:
    """How many open duels wait in each language, for the picker."""
    return {lang: n for lang, n in
            joinable(user).order_by().values("language").annotate(n=Count("id"))
            .values_list("language", "n")}


def find_opponent(user, language: str) -> tuple[Duel | None, str]:
    """Join the open duel in this language whose owner's duel rating is closest to yours (then
    the longest-waiting), preferring questions you haven't seen; or open one: your run starts now, and
    whoever asks next gets your questions."""
    error = _valid(language)
    if error:
        return None, error
    if not can_duel(user):
        return None, NO_ADMIN
    with transaction.atomic():
        _lock(user)
        if _busy(user, timezone.now()):
            return None, BUSY
        candidates = list(joinable(user).filter(language=language)
                          .annotate(gap=Abs(F("challenger__duel_rating") - user.duel_rating))
                          .order_by("gap", "created", "pk").values_list("pk", "questions")[:10])
        seen = _seen([user])
        candidates.sort(key=lambda c: len(seen.intersection(c[1])))  # stable: closest rating among the freshest
        for pk, _ in candidates:
            # skip_locked: someone else is joining it right now; don't queue behind them
            duel = (Duel.objects.select_for_update(skip_locked=True)
                    .filter(pk=pk, status=Duel.Status.PENDING, opponent__isnull=True).first())
            if duel is not None:
                _join(duel, user)
                return duel, ""
        questions = _pick([user], language)
        if questions is None:
            return None, "Bu tilda savollar hali yetarli emas — boshqasini tanlang."
        return _open(user, language, questions), ""


def challenge(challenger, opponent_username: str, language: str) -> tuple[Duel | None, str]:
    """Open a duel reserved for one opponent; the challenger's run starts now."""
    if not can_duel(challenger):
        return None, NO_ADMIN
    opponent = User.objects.filter(username=opponent_username.strip(), is_active=True, is_superuser=False).first()
    if opponent is None:
        return None, "Bunday foydalanuvchi yo‘q."
    if opponent.pk == challenger.pk:
        return None, "O‘zingizni chaqira olmaysiz."
    error = _valid(language)
    if error:
        return None, error
    with transaction.atomic():
        _lock(challenger)
        if _busy(challenger, timezone.now()):
            return None, BUSY
        pair = [challenger.pk, opponent.pk]
        if Duel.objects.filter(status__in=OPEN, challenger_id__in=pair, opponent_id__in=pair).exists():
            return None, "Bu raqib bilan ochiq duel bor."
        if pair_count(*pair) >= PAIR_LIMIT:
            return None, PAIR_FULL
        questions = _pick(pair, language)
        if questions is None:
            return None, "Bu tilda savollar hali yetarli emas — boshqasini tanlang."
        duel = _open(challenger, language, questions, opponent=opponent)
        from apps.accounts.notifications import notify
        from apps.accounts.telegram import notify_duel_challenge
        notify(opponent.pk, "duel", f"duel:{duel.pk}:challenge",
               f"{challenger.username} sizni duelga chaqirdi ({duel.get_language_display()})", f"/classroom/duels/{duel.pk}/")
        transaction.on_commit(lambda: notify_duel_challenge(duel.pk))
        return duel, ""


def accept(duel, user) -> str:
    """Start the invited opponent's run; "" on success, else why not."""
    if not can_duel(user):
        return NO_ADMIN
    with transaction.atomic():
        _lock(user)
        duel = Duel.objects.select_for_update().get(pk=duel.pk)
        if duel.opponent_id != user.pk or duel.status != Duel.Status.PENDING:
            return "Bu chaqiriq endi ochiq emas."
        if timezone.now() - duel.created > WAIT_FOR:
            duel.status = Duel.Status.EXPIRED
            duel.save(update_fields=["status"])
            return "Chaqiriq muddati o‘tgan."
        if _busy(user, timezone.now()):
            return BUSY
        if pair_count(duel.challenger_id, user.pk, exclude=duel.pk) >= PAIR_LIMIT:
            return PAIR_FULL
        _join(duel, user)
    return ""


def decline(duel, user) -> None:
    """The invited opponent turns a challenge down. The challenger can't take one back: their run
    started when they made it."""
    Duel.objects.filter(pk=duel.pk, status=Duel.Status.PENDING, opponent=user).update(status=Duel.Status.DECLINED)


# ---- the result ---------------------------------------------------------------------------------------
def _played(user_id) -> int:
    """Finished duels behind a player, for their K."""
    return Duel.objects.filter(Q(challenger_id=user_id) | Q(opponent_id=user_id), status=Duel.Status.FINISHED).count()


def settle(duel) -> None:
    """Finish a duel whose two runs are over; expire one nobody joined in time."""
    now = timezone.now()
    with transaction.atomic():
        duel = Duel.objects.select_for_update().get(pk=duel.pk)
        if duel.status == Duel.Status.PENDING and now - duel.created > WAIT_FOR:
            duel.status = Duel.Status.EXPIRED
            duel.save(update_fields=["status"])
            return
        if duel.status != Duel.Status.ACTIVE or duel.mode != Duel.Mode.QUIZ:
            return
        winner = _winner(duel, now)
        if winner is None:
            return
        a, b = User.objects.get(pk=duel.challenger_id), User.objects.get(pk=duel.opponent_id)
        score = 0.5 if winner == 0 else (1.0 if winner == a.pk else 0.0)
        season = duel_season(duel)  # a new month starts everyone's rating part of the way back to the middle
        ra, rb = carried(a.duel_rating, a.duel_season, season), carried(b.duel_rating, b.duel_season, season)
        weight = pair_weight(duel)
        da, db = elo(ra, rb, score, k_factor(ra, _played(a.pk)) * weight, k_factor(rb, _played(b.pk)) * weight)
        duel.status, duel.winner_id = Duel.Status.FINISHED, winner or None
        duel.challenger_delta, duel.opponent_delta = da, db
        duel.finished_at = now  # both runs are over: the duel's own date, not when it was created
        duel.save(update_fields=["status", "winner", "challenger_delta", "opponent_delta", "finished_at"])
        User.objects.filter(pk=a.pk).update(duel_rating=ra + da, duel_season=season)
        User.objects.filter(pk=b.pk).update(duel_rating=rb + db, duel_season=season)
    from apps.accounts.badges import award  # a finished duel can lift both players' duel badges
    from apps.accounts.notifications import notify
    from apps.accounts.telegram import notify_duel_result
    for player, other in ((a, b), (b, a)):
        award(player, {"duels"})
        head = "G‘alaba" if duel.winner_id == player.pk else "Durang" if duel.winner_id is None else "Mag‘lubiyat"
        notify(player.pk, "duel", f"duel:{duel.pk}:result", f"{head}: {other.username} bilan duel tugadi",
               f"/classroom/duels/{duel.pk}/")
    notify_duel_result(duel.pk)


def settle_open(user) -> None:
    for duel in Duel.objects.filter(Q(challenger=user) | Q(opponent=user), status__in=OPEN):
        settle(duel)


def replay(duels, users) -> None:
    """Rebuild duel ratings from START_RATING over finished duels, oldest first, with k_factor and the monthly
    softening: each keeps its result, the deltas are worked out again. `duels`/`users` are querysets. The
    `finished_at` of a duel is left alone: it records real history, not something to work out again."""
    rating, played, season_of_user = {}, {}, {}
    for d in duels.filter(status="finished").order_by("created", "pk"):
        a, b = d.challenger_id, d.opponent_id
        season = duel_season(d)
        ra = carried(rating.get(a, START_RATING), season_of_user.get(a, ""), season)
        rb = carried(rating.get(b, START_RATING), season_of_user.get(b, ""), season)
        score = 0.5 if d.winner_id is None else (1.0 if d.winner_id == a else 0.0)
        weight = pair_weight(d)
        da, db = elo(ra, rb, score, k_factor(ra, played.get(a, 0)) * weight, k_factor(rb, played.get(b, 0)) * weight)
        duels.filter(pk=d.pk).update(challenger_delta=da, opponent_delta=db)
        rating[a], rating[b] = ra + da, rb + db
        season_of_user[a] = season_of_user[b] = season
        played[a], played[b] = played.get(a, 0) + 1, played.get(b, 0) + 1
    users.exclude(pk__in=rating).exclude(duel_rating=START_RATING).update(duel_rating=START_RATING, duel_season="")
    for pk, r in rating.items():
        users.filter(pk=pk).update(duel_rating=r, duel_season=season_of_user[pk])
