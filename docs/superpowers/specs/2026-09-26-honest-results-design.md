# Honest Results (sub-project A) — Design Spec

Date: 2026-09-26
Status: design approved in chat; spec pending review
Program: CodeArena improvement, sub-projects A → B → C → D
(A honest results · B anti-cheat v2 · C unique features · D UI/UX overhaul)

## Goal

Every number CodeArena shows — verdicts, contest standings, practice points, solved
markers, the rating board — must be correct, and a submitted program must not be able
to influence how it is judged. A fixes the business-logic bugs found in the audit,
closes the judge-isolation holes, and adds the staff tools (rejudge) needed to keep
results correct after a test fix.

## Decisions (user, 2026-09-26)

| Topic | Decision |
|---|---|
| Practice points | Live: total = sum of the current price of each solved problem |
| Contest penalty | Only WA/TLE/MLE/RE/OLE are penalized; CE and not-yet-judged submissions are free |
| Contest problem freshness | Rated contests: fresh problems only (enforced). Unrated: allowed, with a warning |
| Rejudge | Included |
| Rating board | Users with no rated contest are not listed; their profile says "Reytingsiz" |
| Own problems | Authors earn no practice points for problems they authored |
| Judge isolation | Split users inside the one container per submission (probe-verified) |
| Spec commit | Not committed (user's CLAUDE.md: no commits unless asked) |

## Audit findings this spec fixes

1. `apps/contests/standings.py:25,28` counts CE and PENDING/RUNNING submissions as wrong attempts.
2. `recalc_points` reprices problems every 5 minutes, but `User.practice_points` keeps
   the price paid at solve time (`judge/runner.py:147`), so `/top` drifts.
3. Contest problem sets are not validated; a public, already-solved problem can be put in a rated contest.
4. `contest_publish` turns disqualified participants' contest ACs into practice points.
5. Deleting a problem that anyone solved raises `ProtectedError`
   (`UserProblemSolved.first_ac_submission` is `PROTECT`, the problem delete cascades).
6. `TestCase` has no ordering; `judge/runner.py:66` runs `problem.testcases.all()`, so
   on Postgres the test order (and which test is "Test 1") can change after an edit.
7. Judge: the solution runs as the same user as the runner script, so it can read every
   hidden test input in `/work/tests`, append forged lines to `/out/result`, and reach the
   runner's stdout via `/proc/1/fd/1`. There is no output-size cap: output goes to a host
   bind-mount, and the worker reads it whole into memory (`judge/sandbox.py:99`).
   Containers keep default capabilities and allow privilege gain.
8. `/integrity/event/` and `/integrity/snapshot/` have no rate limit (snapshots are up to 64 KB).

## 1. Solves and practice points

### Rules

- A user has solved a problem if and only if they have an **eligible AC** for it. The
  `UserProblemSolved` row points at the earliest eligible AC (by `created`, then `id`).
- An AC submission is eligible when either:
  - it is a practice submission (`contest` is null), or
  - its contest has been published (`Contest.published_at` is set) and the user's
    participation in that contest is not disqualified.
- `User.practice_points` = sum of the current `Problem.points` over the user's solved
  problems, excluding problems where `problem.author == user`.
- Solved markers, `/top`, the problem list "solved" filter and the profile keep reading
  `UserProblemSolved`; the author exclusion applies to points only.

### Module: `apps/submissions/solves.py` (new)

```python
def refresh_solves(problem_id: int, user_ids: Iterable[int] | None = None) -> None:
    """Make UserProblemSolved rows for this problem follow the eligibility rule, for the
    given users (None = everyone with a solve row or an eligible AC for it), then sync
    those users' practice points."""

def sync_practice_points(user_ids: Iterable[int] | None = None) -> None:
    """One UPDATE: practice_points = Coalesce(Subquery(sum of current points of solved,
    non-authored problems), 0). None = every user."""
```

`refresh_solves` algorithm:
1. Load eligible ACs for the problem (filtered to `user_ids` when given), ordered by
   `created, id`, with `(id, user_id, contest_id)`.
2. Load the disqualified `(user_id, contest_id)` pairs for contests containing the problem;
   skip ACs that match one. First remaining AC per user = the wanted solve.
3. Users to reconcile = `user_ids`, or (when None) everyone with an existing solve row for
   the problem plus everyone with a wanted solve.
4. In one transaction, per user: delete the row when no solve is wanted; create it when
   missing (`get_or_create`, which is safe against a concurrent worker); move
   `first_ac_submission` when it points at a different submission.
5. `sync_practice_points(users)`.

### Callers

| Caller | Call |
|---|---|
| `judge.runner` after saving any final verdict (code and SQL) | `refresh_solves(problem_id, [user_id])` — replaces `_award_points_if_first_ac` |
| `moderation.contest_publish` | sets `published_at`, then `refresh_solves(p)` for each contest problem |
| `contests.disqualify` (toggle), when the contest is published | `refresh_solves(p, [user_id])` for each contest problem |
| Rejudge | through the runner, per re-judged submission |
| `recalc_points` (scheduler, every 5 min) | after repricing: `sync_practice_points()` for everyone — this is what makes points live |
| `recalc_practice_points` command | kept as a thin wrapper around `sync_practice_points()` |
| `seed_demo` | calls `sync_practice_points()` after it creates demo solves |

Consequences users will see once, right after deploy: every total moves to the live
value on the first sweep, and authors lose the points for their own problems.

### Data model

- `Contest.published_at = DateTimeField(null=True, blank=True)`, set by publish (first
  publish only; publishing again keeps the original time and re-runs `refresh_solves`).
- `UserProblemSolved.first_ac_submission`: `on_delete` becomes `CASCADE` (it is derived
  data; this is also the `ProtectedError` fix).
- Data migration: an ended contest counts as already published when a
  `UserProblemSolved` row points at one of its submissions (the trace the old publish
  leaves), or when it has at least one problem and all of its problems are public. Such
  contests get `published_at = end`.

## 2. Contest standings

- `compute_standings` counts a submission as a wrong attempt only when its verdict is in
  `PENALIZED = {"WA", "TLE", "MLE", "RE", "OLE"}`. This applies both to the "wrong" count
  shown in a cell and to the 20-minute penalty. CE, PENDING and RUNNING are ignored.
- `attempted` (used by `recalc_rating` to decide who took part) is unchanged: any
  submission counts.

## 3. Contest integrity

### 3.1 Freshness check (rated contests)

In `ContestProblemFormSet.clean()`, when `self.instance.is_rated` is true and the contest
has not ended (the form has already copied the POSTed values onto `self.instance`):
each non-deleted row's problem gets a field error on `problem` when
- `problem.is_public` is true: "Ochiq masala — reytingli musobaqaga faqat yashirin, yangi masala qo‘shiladi.", or
- the problem belongs to another contest: "Bu masala boshqa musobaqada ishlatilgan."

Editing a contest that has ended skips the check (its problems are public after publish).

### 3.2 Warning (unrated contests)

After a successful save of an unrated contest, `messages.warning` lists the labels of
problems that are public or used in another contest ("participants may already know
them"). Nothing is blocked.

`base.html` renders every message with the same `.ca-alert` style; it gets a level class
(error → `ca-alert-bad`, warning → new `ca-alert-warn`) so warnings and errors are distinguishable.

### 3.3 Publish

`contest_publish` (ended contests only, as today): make the contest's problems public,
set `published_at` if unset, run `refresh_solves` for each contest problem. The success
message reports how many solves now come from this contest. Disqualified participants
get nothing, because the eligibility rule excludes them.

### 3.4 Disqualification after publish

`disqualify` toggles the flag as today. When the contest is published it then runs
`refresh_solves(p, [user_id])` for each contest problem: disqualifying removes the
contest-derived solves (falling back to a practice AC when the user has one), and
re-qualifying restores them.

### 3.5 Problem delete guard

`problem_delete` refuses (with `messages.error`, suggesting to hide the problem instead)
when the problem is used in any contest or has submissions from anyone other than its
author. Otherwise it deletes as today; the `CASCADE` change removes the crash.

## 4. Rejudge

- URL `moderation:problem_rejudge`: `POST /moderation/problems/<pk>/rejudge/`, staff only.
- The view takes the problem's submissions whose verdict is terminal (in-flight
  PENDING/RUNNING ones are left alone). In one transaction it deletes their
  `TestResult`s and resets them: `verdict=PENDING, passed=0, total=0, exec_ms=0,
  mem_kb=0, compile_log=""`. On commit it enqueues `run_submission` for each, oldest
  first, on the new `rejudge` queue.
- The runner needs no rejudge-specific code: it judges a PENDING submission and then
  finalizes it, so solves, points and standings follow the new verdicts. Finalizing
  (drop the contest standings cache + `refresh_solves`) runs after every final verdict,
  on every path: tests judged, CE, SQL judged, SQL error. Today the CE path returns
  before the cache drop; with rejudge an AC can become CE, so that path must finalize too.
- Messages: success "N ta urinish qayta tekshirishga yuborildi."; plus a warning naming any
  contest with this problem whose rating is already applied ("reyting o‘zgarmaydi").
- UI: a rejudge button on each row of `moderation/problems.html`, confirmed with
  `confirm()` like the delete button next to it, showing the number of submissions. The
  list view annotates the submission count (`distinct=True`, alongside the existing test count).
- Queue: `RQ_QUEUES["rejudge"]` (timeout 600). Workers listen `default run rejudge`, in that
  order, so live submissions and trial runs always go first.
  Files: `config/settings/base.py`, `docker-compose.yml`, `docker-compose.prod.yml`, `README.md`.

## 5. Judge sandbox

### 5.1 Container flags

- Common to compile and run: `--cap-drop ALL`, `--security-opt no-new-privileges`,
  `--ulimit core=0`, plus today's `--network none --cpus 1 --pids-limit 64 --read-only --tmpfs /tmp`.
- Compile: `--user nobody` (unchanged behavior, fewer privileges).
- Run: `--user root --cap-add SETUID --cap-add SETGID --cap-add DAC_OVERRIDE`,
  `--ulimit fsize=<output limit bytes>`.
  The runner script is the only root process. `DAC_OVERRIDE` lets it read files owned by
  the worker's host user (uid 1000 in dev, 0 in prod) regardless of mode bits.

### 5.2 Host-side permissions

- `tests/` directory `0700`, `*.in` files `0600`; `out/` directory `0755`; `run.sh` `0700`.
- Source file stays `0644`; `src_dir` stays `0755` (interpreted) / `0777` (compiled: the
  compile container writes the binary as `nobody`).

### 5.3 Runner script

Per test, the runner (root) starts the solution with
`su -s /bin/sh nobody -c <shlex-quoted "exec timeout -s KILL {tl} {run_cmd}">`, feeding the
test file on stdin and redirecting stdout to `/out/$n.out` (the runner opens both, the
solution only inherits the descriptors). After each test it runs
`su -s /bin/sh nobody -c 'kill -9 -1'` to kill anything the solution left running.
`busybox time -f %M -o /tmp/mem` still wraps the command; its report maps
"terminated by signal 9" → rc 137 (as today) and "terminated by signal 25" (SIGXFSZ) → rc 153.

Verified by probe on all four images (python, cpp, java, node), 2026-09-26:
- the runner reads a `0600` test; the solution gets "Permission denied"
- the solution cannot create or append `/out/result`, and cannot open `/proc/1/fd/1`
- `kill -9 -1` as `nobody` removes an orphan `sleep`
- `PATH` survives `su` (java at `/opt/java/openjdk/bin` is found), `HOME=/`, cwd `/work`
- the output cap: busybox time reports "terminated by signal 25", rc 25, and the output
  file is cut at exactly the limit
- a TLE kill still reports "terminated by signal 9"

### 5.4 Verdicts and output limit

- Host mapping: rc 0 → OK; rc 153 → **OLE**; rc 137 with `ms >= TL` → TLE; rc 137 → MLE; otherwise RE.
- `run_tests(..., output_limit: int = DEFAULT_OUTPUT_LIMIT)`, `DEFAULT_OUTPUT_LIMIT = 16 MiB`.
  `run_submission` passes `max(DEFAULT_OUTPUT_LIMIT, 2 × largest expected output in bytes)`, so
  a problem with a large legitimate answer never gets OLE; trial runs use the default.
  Because the file is capped, the worker never reads more than the limit into memory.
- New verdict `Submission.Verdict.OLE` (added to `TERMINAL`), shown as "OL" with title
  "Output Limit — chiqish hajmi chegarasi oshdi" in the TL/ML (warn) style; `.ca-test-OLE`
  gets the warn color; the "Urinishlar" verdict filter gets ("OLE", "OL"). The staff
  submissions filter reads `Submission.Verdict.values`, so it picks OLE up automatically.

### 5.5 Test order

`TestCase.Meta.ordering = ["order", "id"]`. The runner, trial samples (`Problem.samples`)
and the moderation formset all follow it.

## 6. Rating board

- `/accounts/rating/` lists only users with at least one participation whose
  `rating_after` is set (`contest_count > 0`); the total shown counts only them.
- Profile of a user with no rated contest: rating value "—", tier chip "Reytingsiz"
  (gray), rating rank "—". Rating rank is computed among rated active users, and its
  denominator is the number of rated active users (points rank keeps all active users).
- Username colors elsewhere are unchanged (1200 is already the gray tier).

## 7. Integrity endpoint rate limits

- `_rate_limited` moves from `apps/submissions/views.py` to `apps/submissions/ratelimit.py`
  as `rate_limited(user_id, kind, limit)` (same fixed 60-second window); submissions views import it.
- `/integrity/event/`: 60 per minute per user. `/integrity/snapshot/`: 20 per minute per user
  (the client sends one every 10 seconds plus one per submit/page exit). Over the limit:
  HTTP 429, nothing stored. A client flooding events hits the limit only after leaving a
  large, visible event trail, so the limit hides nothing from staff.

## 8. Migrations

| App | Migration |
|---|---|
| problems | `TestCase` ordering (`AlterModelOptions`) |
| submissions | `Verdict` choices gain OLE; `first_ac_submission` `on_delete=CASCADE` |
| contests | `Contest.published_at`; data migration backfilling it (§1) |

## 9. Testing

Unit tests (default `pytest`):
- standings: CE and PENDING are not penalized and not shown as wrong; OLE is.
- solves: practice AC creates a solve; a contest AC does not until publish; publish
  creates it; disqualification removes it and falls back to a practice AC; re-qualifying
  restores it; an AC turning into WA moves the solve to the next eligible AC or removes it.
- points: live repricing changes totals after `recalc_points`; own problems give 0 points;
  `recalc_practice_points` still works.
- data migration: the published backfill heuristic.
- contest form: rated rejects a public problem and a problem from another contest; unrated
  saves and shows the warning; editing an ended rated contest is not blocked.
- problem delete: blocked with a contest or others' submissions; allowed otherwise, including
  when the author solved it (no `ProtectedError`).
- rejudge: terminal submissions reset and enqueued on `rejudge`, in-flight ones untouched,
  rated-contest warning shown; staff only.
- runner: tests run in `order`; a rejudged AC → WA removes the solve and points.
- rating board hides unrated users; profile shows "Reytingsiz".
- integrity endpoints return 429 past the limit.

Docker tests (`JUDGE_TESTS=1`):
- a solution cannot read another test's input (try to open `/work/tests/0001.in` → WA/RE, never AC).
- a solution cannot forge results (appending to `/out/result` fails; the verdict is unchanged).
- an output flood gives OLE, and the output file stays within the limit.
- an orphan forked by one test is gone before the next test.
- A+B is still AC in all four languages; peak memory is still recorded.

## Out of scope

- Recomputing ratings after a rejudge (staff get a warning instead).
- Proxy-aware client IP for `allowed_ip_prefix` (deploy is direct today).
- Anti-cheat v2 (sub-project B), new features (C), UI redesign (D).
