"""Server-side evidence for the contest report: what a participant can't hide by blocking
the browser tracker. Each piece is a hint for staff, never a verdict on its own."""
from dataclasses import dataclass, field
from datetime import timedelta
from itertools import combinations

from apps.submissions.models import Submission

from .models import CodeSnapshot, DeviceSeen, SimilarityFlag
from .similarity import similarity

SILENT_S = 90             # no tracker heartbeat for this long before a submit
UNSEEN_AFTER_S = 60       # the submit-time snapshot may land a little after the submission
UNSEEN_LOOKBACK = timedelta(minutes=10)
UNSEEN_MIN_SIMILARITY = 0.9
JUMP_CHARS = 150          # appeared between two snapshots (at most one ~10 s tick of editing)

WEIGHTS = {"silent": 6, "unseen": 8, "jump": 3, "shared_device": 10, "multi_device": 5, "similar": 8}
LABELS = {"silent": "Tracker o‘chiq", "unseen": "Muharrirda yozilmagan", "jump": "Kod sakrashi",
          "shared_device": "Umumiy qurilma", "multi_device": "Ikki qurilma", "similar": "O‘xshash kod"}


@dataclass
class Evidence:
    kind: str
    text: str
    problem_id: int | None = None
    submission: Submission | None = field(default=None, repr=False)

    @property
    def weight(self) -> int:
        return WEIGHTS[self.kind]

    @property
    def label(self) -> str:
        return LABELS[self.kind]


def contest_evidence(contest) -> dict[int, list[Evidence]]:
    """user id -> evidence, in a stable order (by kind, then problem label)."""
    out: dict[int, list[Evidence]] = {}
    labels = dict(contest.contest_problems.values_list("problem_id", "label"))
    subs = list(Submission.objects.filter(contest=contest).order_by("created", "id"))
    snaps: dict[tuple[int, int], list[CodeSnapshot]] = {}
    for s in CodeSnapshot.objects.filter(contest=contest).order_by("at", "id"):
        snaps.setdefault((s.user_id, s.problem_id), []).append(s)

    # A contest from before the heartbeat (or the snapshots) has none for anyone, which
    # says nothing about its participants.
    # ponytail: a contest whose every participant blocks the tracker looks the same;
    # key this on the deploy date if that ever happens.
    checks = []
    if any(s.tracker_seen_at for s in subs) or DeviceSeen.objects.filter(contest=contest).exists():
        checks.append(("silent", _is_silent))
    if snaps:
        checks.append(("unseen", _is_unseen))
    for kind, check in checks:
        hits: dict[tuple[int, int], list[Submission]] = {}
        for sub in subs:
            if check(sub, snaps.get((sub.user_id, sub.problem_id), [])):
                hits.setdefault((sub.user_id, sub.problem_id), []).append(sub)
        for (user_id, problem_id), bad in hits.items():
            # the kind's label says what happened; the report lists one kind's problems on one line
            out.setdefault(user_id, []).append(Evidence(
                kind, f"{labels.get(problem_id, '?')}: {len(bad)} ta yuborish", problem_id, bad[-1]))

    for (user_id, problem_id), rows in snaps.items():
        # the first snapshot is the baseline: a starter template can be big
        grew = max((len(b.source) - len(a.source) for a, b in zip(rows, rows[1:])), default=0)
        if grew >= JUMP_CHARS:
            out.setdefault(user_id, []).append(Evidence(
                "jump", f"{labels.get(problem_id, '?')}: {grew} belgi birdaniga paydo bo‘lgan", problem_id))

    _devices(contest, subs, out)
    _similar(contest, labels, out)
    order = list(WEIGHTS)
    for items in out.values():
        items.sort(key=lambda e: (order.index(e.kind), e.text))  # the text starts with the problem's label
    return out


def _is_silent(sub, _snaps) -> bool:
    return sub.tracker_seen_at is None or (sub.created - sub.tracker_seen_at).total_seconds() > SILENT_S


def _is_unseen(sub, snaps) -> bool:
    window = [s for s in snaps
              if sub.created - UNSEEN_LOOKBACK <= s.at <= sub.created + timedelta(seconds=UNSEEN_AFTER_S)]
    want = _normalized(sub.source)
    if any(_normalized(s.source) == want for s in window):
        return False
    before = [s for s in window if s.at <= sub.created][-3:]
    after = [s for s in window if s.at > sub.created][:1]
    return not any(similarity(sub.source, s.source) >= UNSEEN_MIN_SIMILARITY for s in before + after)


def _normalized(source: str) -> str:
    return "\n".join(line.rstrip() for line in source.strip().splitlines())


def _devices(contest, subs, out):
    users_by_device: dict[str, set] = {}
    seen = list(DeviceSeen.objects.filter(contest=contest).select_related("user"))
    names = {d.user_id: d.user.username for d in seen}
    for d in seen:
        users_by_device.setdefault(d.device, set()).add(d.user_id)
    for sub in subs:
        if sub.device:
            users_by_device.setdefault(sub.device, set()).add(sub.user_id)
    if any(len(u) > 1 for u in users_by_device.values()):
        from apps.accounts.models import User

        missing = {u for users in users_by_device.values() for u in users} - names.keys()
        names |= dict(User.objects.filter(pk__in=missing).values_list("pk", "username"))
    shared: dict[int, set] = {}
    for users in users_by_device.values():
        for u in users:
            if len(users) > 1:
                shared.setdefault(u, set()).update(users - {u})
    for u, others in shared.items():
        out.setdefault(u, []).append(Evidence(
            "shared_device", "Bir qurilmadan: " + ", ".join(sorted(names.get(o, str(o)) for o in others))))

    by_user: dict[int, list[DeviceSeen]] = {}
    for d in seen:
        by_user.setdefault(d.user_id, []).append(d)
    for u, devices in by_user.items():
        # ponytail: pairwise over one user's devices; a handful per contest at most
        if any(a.first_at <= b.last_at and b.first_at <= a.last_at for a, b in combinations(devices, 2)):
            out.setdefault(u, []).append(Evidence(
                "multi_device", f"Bir vaqtda {len(devices)} ta qurilmada ishlagan"))


def _similar(contest, labels, out):
    flags = (SimilarityFlag.objects.filter(submission_a__contest=contest, reviewed=False)
             .select_related("submission_a__user", "submission_b__user"))
    for f in flags:
        a, b = f.submission_a, f.submission_b
        pct = round(f.score * 100)
        label = labels.get(a.problem_id, "?")
        for me, other in ((a, b), (b, a)):
            if me.contest_id != contest.pk:
                continue  # a prior solution's author isn't a participant of this contest
            out.setdefault(me.user_id, []).append(Evidence(
                "similar", f"{label}: {other.user.username} bilan {pct}% o‘xshash", a.problem_id, me))
