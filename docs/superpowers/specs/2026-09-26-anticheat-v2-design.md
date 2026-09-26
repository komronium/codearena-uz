# Anti-cheat v2 (sub-project B) — Design Spec

Date: 2026-09-26
Program: CodeArena improvement, sub-projects A → B → C → D
(A honest results · B anti-cheat v2 · C unique features · D UI/UX overhaul)

## Goal

Make cheating leave evidence even when the cheater blocks the browser tracker, and make
every staff decision about cheating traceable. Evidence goes to staff; the platform
never punishes on its own.

## Decisions (user, 2026-09-26)

| Topic | Decision |
|---|---|
| Scope | Silent tracker + unseen code · device & account sharing · similarity v2 · audit log + DQ transparency |
| Code that never appeared in the editor | Flag for staff; the submission is judged normally |
| DQ after the rating was applied | Recompute the contest's rating if it is still the latest rated contest of its participants; otherwise leave ratings and warn staff |

## Audit findings this spec fixes

1. The tracker is client-only. Blocking `/integrity/event/` or submitting with `curl`
   produces no events, so a cheater scores lower risk than an honest student.
2. Code pasted in from elsewhere shows up only as a "jump" on the per-user replay page;
   the contest report never cross-checks a submission against the editor snapshots.
3. No IP or device is recorded: two accounts on one laptop, or one account on two
   machines at the same time, are invisible.
4. `flag_similarity` compares contest ACs only: a copied attempt that never got AC, or a
   copy of an older solution (practice, a past contest, the author's own), is missed.
5. Staff actions (DQ, rejudge, publish, rating) leave no trail, and a disqualified
   participant is never told why.
6. A DQ after `rating_applied` leaves the cheater's rating gain in place.

## 1. Telemetry: heartbeat and device

- `Participation.last_seen_at` (nullable): the last heartbeat from this participant.
- New model `integrity.DeviceSeen(contest, user, device, ip, first_at, last_at)`, unique
  on `(contest, user, device)`; `ip` is the last one seen.
- Device id: a random UUID in `localStorage["ca-device"]`, created on first use; the
  tracker sends it with each heartbeat and fills a hidden `device` input on the submit
  form. It is not a fingerprint: clearing storage makes a new one, which itself shows up
  as a second device.
- `POST /integrity/beat/` (`contest_id`, `device`): participant only; upserts
  `DeviceSeen`, sets `last_seen_at`. Rate limit 6 per minute per user. The tracker beats
  on load and every 30 s while any contest workspace page is open.
- `Submission` gains `device` (blank), `ip` (nullable) and `tracker_seen_at` (nullable,
  a copy of `Participation.last_seen_at` at submit time, contest submissions only).

## 2. Evidence engine (`apps/integrity/evidence.py`)

`contest_evidence(contest) -> dict[user_id, list[Evidence]]`, where `Evidence` has
`kind`, `weight`, `text` (Uzbek) and optionally `submission`/`problem` for links. The
contest report ranks by the weight sum and lists each participant's evidence.

| Kind | Rule | Weight |
|---|---|---|
| `silent` | contest submission with no heartbeat in the 90 s before it (`tracker_seen_at` null or older) | 6 |
| `unseen` | contest submission whose code never appeared in that user's editor snapshots of the problem (no snapshot up to 60 s after it matches exactly or with similarity ≥ 0.9) | 8 |
| `jump` | ≥ 150 characters appeared between two snapshots ≤ 15 s apart (once per user and problem) | 3 |
| `shared_device` | a device id used by 2+ users in this contest | 10 |
| `multi_device` | one user on 2+ devices whose seen intervals overlap | 5 |
| `similar` | an unreviewed similarity flag | 8 |
| `too_fast` / `back_and_solve` | existing heuristics | 4 |
| events | paste 5, fast 3, copy 2, leave 1, each full minute away 1 | as before |

IPs are shown in the report but never scored: a classroom shares one NAT address.

## 3. Similarity v2

Per contest problem, candidates are every contest AC plus, for a participant without an
AC, their last contest attempt. They are compared pairwise (as now) and against
**prior solutions**: the latest submission per user of the same problem made before the
contest started (practice, past contests, the author's own), newest 300, `MIN_LINES`+.
Same language only, same threshold. A prior-solution flag stores the contest
submission as `submission_a`; its card says "Musobaqadan oldingi yechim".

## 4. Audit log and DQ transparency

- New model `integrity.AuditEntry(actor, action, contest, subject, note, at)`; `actor`,
  `contest`, `subject` are `SET_NULL` so the record outlives them. Actions: `disqualify`,
  `requalify`, `rejudge`, `publish`, `rating_apply`, `rating_recompute`, `flag_review`,
  `problem_delete`, `contest_delete`.
- Staff page `/integrity/audit/` (filter `?contest=`), 50 per page; the contest report
  shows that contest's last entries.
- A disqualified participant sees a banner with the reason on the contest page and its
  problem pages.

## 5. DQ after the rating was applied

`apps/contests/rating.py` takes the apply logic out of `recalc_rating` and adds
`rollback(contest)` and `is_latest(contest)`. The rating is latest when none of its
rated participants has a rated participation in a contest that ended later. Rollback
subtracts each participant's delta (so a manual rating edit made since is kept) and
clears `rating_before/after` and `rating_applied`. Disqualify/requalify on an applied
contest then does: latest → rollback + apply + `rating_recompute` audit entry;
otherwise → a warning that ratings stay.

## Migrations

`contests/0007_participation_last_seen_at`, `submissions/0006_submission_telemetry`,
`integrity/0004_deviceseen`, `integrity/0005_auditentry`.

## Tasks

- B1 Telemetry (heartbeat endpoint, device id, submission fields).
- B2 Evidence engine and report.
- B3 Similarity v2.
- B4 Audit log and DQ banner.
- B5 Rating recompute on DQ.
- B6 Final verification (suite, migrations check, ruff).

## Out of scope

Proctoring (webcam, screen share), lockdown browser, AST-level similarity, automatic
punishment.
