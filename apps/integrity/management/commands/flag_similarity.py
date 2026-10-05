from datetime import timedelta
from itertools import combinations

from django.core.management.base import BaseCommand, CommandError
from django.db.models import F, Q
from django.utils import timezone

from apps.accounts.models import User
from apps.contests.models import Contest
from apps.integrity.models import SimilarityFlag
from apps.integrity.similarity import MIN_LINES, THRESHOLD, code_lines, similarity
from apps.submissions.models import Submission

PRIOR_MAX = 300
# --pending waits this long after a round's end, so the judge has finished its last submissions
SETTLE = timedelta(minutes=10)


class Command(BaseCommand):
    help = ("Flag AC-submission pairs above the similarity threshold for a contest (spec §4.2). "
            "Idempotent. Omit contest_id to process every ended contest; --pending only the rounds "
            "that ended since their last sweep (the scheduler's); --user one participant's every attempt.")

    def add_arguments(self, parser):
        parser.add_argument("contest_id", type=int, nargs="?", default=None)
        parser.add_argument("--problems", default="", help="comma-separated labels (A,C) to check; default all")
        parser.add_argument("--pending", action="store_true",
                            help="every problem of each round ended 10+ minutes ago and not swept since")
        parser.add_argument("--user", default="", help="with contest_id: this handle's every attempt, all problems")

    def handle(self, *args, **opts):
        if opts["pending"]:
            now = timezone.now()
            total = 0
            for contest in Contest.objects.filter(Q(similarity_checked_at__isnull=True)
                                                  | Q(similarity_checked_at__lt=F("end")), end__lte=now - SETTLE):
                total += self._flag(contest)
                contest.similarity_checked_at = now
                contest.save(update_fields=["similarity_checked_at"])
            self.stdout.write(self.style.SUCCESS(f"{total} similarity flag(s) created"))
            return
        if opts["contest_id"] is not None:
            try:
                contest = Contest.objects.get(pk=opts["contest_id"])
            except Contest.DoesNotExist:
                raise CommandError(f"no contest {opts['contest_id']}")
            if opts["user"]:
                user = User.objects.filter(username=opts["user"]).first()
                if user is None:
                    raise CommandError(f"no user {opts['user']}")
                created = flag_user(contest, user)
            else:
                labels = [x.strip() for x in opts["problems"].split(",") if x.strip()]
                created = self._flag(contest, labels)
            self.stdout.write(self.style.SUCCESS(f"{created} similarity flag(s) created"))
            return

        total = 0
        for contest in Contest.objects.filter(end__lte=timezone.now()):
            total += self._flag(contest)
        self.stdout.write(self.style.SUCCESS(f"{total} similarity flag(s) created"))

    def _flag(self, contest, labels=None) -> int:
        """Keep exactly one flag per (problem, user pair, kind): the most similar pair, if
        both sides have MIN_LINES+ lines of code and score >= THRESHOLD. Kinds: two
        participants of this contest, or a participant and a prior solution (made before
        the contest started: practice, a past contest, the author's own).
        Unreviewed flags that no longer qualify (older, looser rules) are dropped;
        reviewed ones stay — a human already looked at them — and so do a deep check's."""
        created = 0
        keep: set[int] = set()
        cps = contest.contest_problems.all()
        if labels:
            cps = cps.filter(label__in=labels)
        problem_ids = list(cps.values_list("problem_id", flat=True))
        for problem_id in problem_ids:
            subs = _candidates(contest, problem_id)
            best: dict[tuple, tuple[float, Submission, Submission]] = {}
            for a, b in combinations(subs, 2):
                # different languages read too differently for a text similarity score to mean anything
                if a.user_id == b.user_id or a.language_id != b.language_id:
                    continue
                score = similarity(a.source, b.source)
                key = ("peer", *sorted((a.user_id, b.user_id)))
                if score >= THRESHOLD and score > best.get(key, (0,))[0]:
                    best[key] = (score, *((a, b) if a.pk < b.pk else (b, a)))
            prior = _prior(contest, problem_id)
            for a in subs:
                for b in prior:
                    if a.user_id == b.user_id or a.language_id != b.language_id:
                        continue  # your own old code is not a copy
                    score = similarity(a.source, b.source)
                    key = ("prior", a.user_id, b.user_id)
                    if score >= THRESHOLD and score > best.get(key, (0,))[0]:
                        best[key] = (score, a, b)  # the contest submission is always side a
            for (kind, *_), (score, lo, hi) in best.items():
                flag = _existing(contest, problem_id, kind, lo, hi)
                if flag is None:
                    flag = SimilarityFlag.objects.create(submission_a=lo, submission_b=hi, score=score)
                    created += 1
                elif not flag.reviewed and (not flag.deep or score >= flag.score):
                    flag.submission_a, flag.submission_b, flag.score, flag.deep = lo, hi, score, False
                    flag.save(update_fields=["submission_a", "submission_b", "score", "deep"])
                keep.add(flag.pk)
        SimilarityFlag.objects.filter(submission_a__contest=contest, submission_a__problem_id__in=problem_ids,
                                      reviewed=False, deep=False).exclude(pk__in=keep).delete()
        return created


def flag_user(contest, user) -> int:
    """The deep check of one suspect: every attempt they made in the round, not only their AC or
    last try, against every attempt of the other participants and the solutions from before the
    round, on every problem. Adds flags and raises a flag's score when it finds a closer pair; never
    drops one, since it sees only this participant's side. Returns how many flags are new."""
    created = 0
    for problem_id in contest.contest_problems.values_list("problem_id", flat=True):
        subs = [s for s in Submission.objects.filter(contest=contest, problem_id=problem_id).order_by("created", "id")
                if code_lines(s.source) >= MIN_LINES]
        mine = [s for s in subs if s.user_id == user.pk]
        if not mine:
            continue
        best: dict[tuple, tuple[float, Submission, Submission]] = {}
        for a in mine:
            for b in [s for s in subs if s.user_id != user.pk] + _prior(contest, problem_id):
                if b.user_id == user.pk or a.language_id != b.language_id:
                    continue
                prior = b.contest_id != contest.pk
                key = ("prior", user.pk, b.user_id) if prior else ("peer", *sorted((user.pk, b.user_id)))
                score = similarity(a.source, b.source)
                if score >= THRESHOLD and score > best.get(key, (0,))[0]:
                    # the contest submission is side a of a prior flag; a peer flag's earlier id goes first
                    best[key] = (score, *((a, b) if prior or a.pk < b.pk else (b, a)))
        for (kind, *_), (score, lo, hi) in best.items():
            flag = _existing(contest, problem_id, kind, lo, hi)
            if flag is None:
                SimilarityFlag.objects.create(submission_a=lo, submission_b=hi, score=score, deep=True)
                created += 1
            elif not flag.reviewed and score > flag.score:
                flag.submission_a, flag.submission_b, flag.score, flag.deep = lo, hi, score, True
                flag.save(update_fields=["submission_a", "submission_b", "score", "deep"])
    return created


def _candidates(contest, problem_id) -> list[Submission]:
    """Every contest AC, plus the last attempt of each participant who never got AC:
    a copy that failed on a detail is still a copy."""
    subs = list(Submission.objects.filter(contest=contest, problem_id=problem_id).order_by("created", "id"))
    solved = {s.user_id for s in subs if s.verdict == Submission.Verdict.AC}
    last_try = {s.user_id: s for s in subs if s.user_id not in solved}
    picked = [s for s in subs if s.verdict == Submission.Verdict.AC] + list(last_try.values())
    return [s for s in picked if code_lines(s.source) >= MIN_LINES]


def _prior(contest, problem_id) -> list[Submission]:
    """The latest pre-contest submission of each user for the problem."""
    # ponytail: newest PRIOR_MAX users only, compared in Python; move to a per-problem
    # fingerprint index if a reused problem ever has thousands of prior solvers.
    subs = (Submission.objects.filter(problem_id=problem_id, created__lt=contest.start)
            .exclude(contest=contest).order_by("-created", "-id"))
    latest: dict[int, Submission] = {}
    for s in subs.iterator():
        if s.user_id not in latest and code_lines(s.source) >= MIN_LINES:
            latest[s.user_id] = s
            if len(latest) >= PRIOR_MAX:
                break
    return list(latest.values())


def _existing(contest, problem_id, kind, a, b):
    base = SimilarityFlag.objects.filter(submission_a__problem_id=problem_id, submission_a__contest=contest)
    if kind == "prior":
        return (base.filter(submission_a__user=a.user_id, submission_b__user=b.user_id)
                .exclude(submission_b__contest=contest).first())
    peers = base.filter(submission_b__contest=contest)
    return (peers.filter(submission_a__user=a.user_id, submission_b__user=b.user_id)
            | peers.filter(submission_a__user=b.user_id, submission_b__user=a.user_id)).first()
