"""Server-side evidence for the contest report: what a participant can't hide by blocking
the browser tracker. Each piece is a hint for staff, never a verdict on its own."""
import re
from dataclasses import dataclass, field
from datetime import timedelta
from itertools import combinations

from apps.submissions.models import Submission

from .models import AiMatch, CodeSnapshot, DeviceSeen, SimilarityFlag
from .similarity import similarity
from django.utils.translation import gettext as _t, gettext_lazy as _tl

SILENT_S = 90             # no tracker heartbeat for this long before a submit
UNSEEN_AFTER_S = 60       # the submit-time snapshot may land a little after the submission
UNSEEN_LOOKBACK = timedelta(minutes=10)
UNSEEN_MIN_SIMILARITY = 0.9
JUMP_CHARS = 150          # appeared between two snapshots (at most one ~10 s tick of editing)

WEIGHTS = {"ai_mark": 15, "mark_shared": 15, "mark_source": 10, "ai_match": 9, "silent": 6, "unseen": 8, "jump": 3,
           "shared_device": 10, "multi_device": 5, "similar": 8}
LABELS = {"ai_mark": _tl("AI belgisi"), "mark_shared": _tl("Boshqaning AI belgisi"), "mark_source": _tl("Belgisi boshqada chiqdi"),
          "ai_match": _tl("AI yechimiga o‘xshash"), "silent": _tl("Tracker o‘chiq"), "unseen": _tl("Muharrirda yozilmagan"), "jump": _tl("Kod sakrashi"),
          "shared_device": _tl("Umumiy qurilma"), "multi_device": _tl("Ikki qurilma"), "similar": _tl("O‘xshash kod")}


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
                kind, _t("{labels_get_problem_id}: {len_bad} ta yuborish").format(labels_get_problem_id=labels.get(problem_id, '?'), len_bad=len(bad)), problem_id, bad[-1]))

    for (user_id, problem_id), rows in snaps.items():
        # the first snapshot is the baseline: a starter template can be big
        grew = max((len(b.source) - len(a.source) for a, b in zip(rows, rows[1:])), default=0)
        if grew >= JUMP_CHARS:
            out.setdefault(user_id, []).append(Evidence(
                "jump", _t("{labels_get_problem_id}: {grew} belgi birdaniga paydo bo‘lgan").format(labels_get_problem_id=labels.get(problem_id, '?'), grew=grew), problem_id))

    _ai_marks(contest, labels, subs, out)
    _ai_matches(contest, labels, out)
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
            "shared_device", _t("Bir qurilmadan: {names}").format(names=", ".join(sorted(names.get(o, str(o)) for o in others)))))

    by_user: dict[int, list[DeviceSeen]] = {}
    for d in seen:
        by_user.setdefault(d.user_id, []).append(d)
    for u, devices in by_user.items():
        # ponytail: pairwise over one user's devices; a handful per contest at most
        if any(a.first_at <= b.last_at and b.first_at <= a.last_at for a, b in combinations(devices, 2)):
            out.setdefault(u, []).append(Evidence(
                "multi_device", _t("Bir vaqtda {len_devices} ta qurilmada ishlagan").format(len_devices=len(devices))))


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
                "similar", _t("{label}: {other_user_username} bilan {pct}% o‘xshash").format(label=label, other_user_username=other.user.username, pct=pct), a.problem_id, me))


def _ai_marks(contest, labels, subs, out):
    """A submission whose code carries a name a statement's hidden AI note asked for (apps.problems.ai_marks):
    the statement went to an AI and its answer came back. One line per problem, with its last such submission.
    The name is the reader's own copy (`javob_qz_k3`), so a copy that is someone else's shows who passed the
    statement or the answer on: "mark_shared" for the one who submitted it, "mark_source" for the one it names."""
    from apps.accounts.models import User
    from apps.problems.ai_marks import owner, pattern, tokens
    from apps.problems.models import Problem

    wanted = {p.pk: {t: pattern(t) for t in tokens(p.statement_md, p.input_md, p.output_md)}
              for p in Problem.objects.filter(pk__in=list(labels)).only("statement_md", "input_md", "output_md")}
    own: dict[tuple[int, int], tuple[list[Submission], set[str]]] = {}
    others: dict[tuple[int, int, int], tuple[list[Submission], set[str]]] = {}  # (user, problem, whose copy)
    for sub in subs:
        for token, rx in wanted.get(sub.problem_id, {}).items():
            for m in rx.finditer(sub.source):
                whose = owner(m.group(1))
                if whose is None or whose == sub.user_id:
                    bad, names = own.setdefault((sub.user_id, sub.problem_id), ([], set()))
                else:
                    bad, names = others.setdefault((sub.user_id, sub.problem_id, whose), ([], set()))
                if not bad or bad[-1] is not sub:
                    bad.append(sub)
                names.add(m.group(0))
    for (user_id, problem_id), (bad, names) in own.items():
        out.setdefault(user_id, []).append(Evidence(
            "ai_mark", _t("{problem}: kodda «{names}»").format(problem=labels.get(problem_id, "?"), names=", ".join(sorted(names))), problem_id, bad[-1]))
    handles = dict(User.objects.filter(pk__in={w for _, _, w in others} | {u for u, _, _ in others})
                   .values_list("pk", "username"))
    for (user_id, problem_id, whose), (bad, names) in others.items():
        label = labels.get(problem_id, "?")
        out.setdefault(user_id, []).append(Evidence(
            "mark_shared", _t("{problem}: kodda {user} nusxasining belgisi «{names}»").format(
                problem=label, user=handles.get(whose, whose), names=", ".join(sorted(names))), problem_id, bad[-1]))
        out.setdefault(whose, []).append(Evidence(
            "mark_source", _t("{problem}: belgisi {user} kodida chiqdi «{names}»").format(
                problem=label, user=handles.get(user_id, user_id), names=", ".join(sorted(names))), problem_id))


def _ai_matches(contest, labels, out):
    """Submissions close to an AI's own answer to the problem (ai_match). One line per problem, its closest."""
    best: dict[tuple[int, int], AiMatch] = {}
    for m in AiMatch.objects.filter(submission__contest=contest).select_related("submission"):
        key = (m.submission.user_id, m.submission.problem_id)
        if key not in best or m.score > best[key].score:
            best[key] = m
    for (user_id, problem_id), m in best.items():
        out.setdefault(user_id, []).append(Evidence(
            "ai_match", _t("{label}: {pct}% o‘xshash").format(label=labels.get(problem_id, "?"), pct=round(m.score * 100)),
            problem_id, m.submission))


def history(contest, user_ids) -> dict[int, dict[str, int]]:
    """What staff decided about these users in other rounds: rounds played, disqualified, problems voided.
    Decisions only (not raw signals), so a repeat is visible without recomputing old evidence."""
    from apps.contests.models import Participation, VoidedProblem

    out = {u: {"played": 0, "dq": 0, "voided": 0} for u in user_ids}
    for user_id, dq in (Participation.objects.filter(user_id__in=user_ids).exclude(contest=contest)
                        .values_list("user_id", "disqualified")):
        out[user_id]["played"] += 1
        out[user_id]["dq"] += bool(dq)
    for user_id in (VoidedProblem.objects.filter(participation__user_id__in=user_ids)
                    .exclude(participation__contest=contest).values_list("participation__user_id", flat=True)):
        out[user_id]["voided"] += 1
    return out
