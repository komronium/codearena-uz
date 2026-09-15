# CodeArena — Design Spec

Date: 2026-09-15
Status: approved (chat), pending implementation plan

## Goal

Open competitive-programming platform (robocontest.uz / Codeforces style) aimed at
2nd-year students who know if/else/for/input. Problems are stdin/stdout. Four
languages at launch. Rating, leaderboards, contests. Measures against AI-assisted
cheating.

## Decisions

| Topic | Decision |
|---|---|
| Scale | Open registration, target thousands of users; start on one VPS |
| Stack | Django + HTMX + Tailwind (CDN) + CodeMirror 6 (CDN); Postgres; Redis + RQ |
| Problem format | stdin/stdout only; full program per submission |
| Languages | Python 3, C++ (g++), Java, JavaScript (Node). Changeable via `Language` table |
| Judge | Docker container per test run, driven by RQ worker (approach A). Interface allows swap to `isolate` later |
| Rating | Both: Elo after rated contests + practice points from first AC |
| Infra | docker-compose: web, postgres, redis, judge-worker (worker has docker.sock) |
| Anti-AI | Contest-mode client restrictions, post-contest similarity, problem design, IP/group restrictions |

## 1. Data model

App `accounts`
- `User(AbstractUser)`: `rating int default 1500`, `practice_points int default 0`, `role enum student|teacher|admin`
- `Group(name, teacher FK User, members M2M User)`

App `problems`
- `Problem(slug unique, title, statement_md, statement_image nullable, difficulty enum easy|medium|hard, tl_ms, ml_mb, points, is_public, author FK, tags M2M Tag, created)`
- `TestCase(problem FK, input text, expected text, is_sample bool, order int)`
- `Language(code unique, name, docker_image, compile_cmd nullable, run_cmd, tl_multiplier float, is_active)`

App `submissions`
- `Submission(user FK, problem FK, contest FK nullable, language FK, source text, verdict enum, exec_ms, mem_kb, passed int, total int, created)`
- `TestResult(submission FK, testcase FK, verdict, exec_ms, stdout_excerpt)` — stored for every executed test
- Verdict enum: `PENDING RUNNING AC WA TLE MLE RE CE`
- `UserProblemSolved(user, problem, first_ac_submission, unique(user, problem))` — practice points awarded once

App `contests`
- `Contest(title, description_md, start, end, type enum icpc|score, is_rated, allowed_ip_prefix nullable, require_group FK nullable, rating_applied bool)`
- `ContestProblem(contest FK, problem FK, label char, order, points)`
- `Participation(user FK, contest FK, score, penalty, rank, rating_before, rating_after, unique(user, contest))`

App `integrity`
- `FocusEvent(user FK, contest FK, kind enum blur|focus|paste|copy, at)`
- `SimilarityFlag(submission_a FK, submission_b FK, score float, reviewed bool, note text)`

Indexes: `Submission(user, problem)`, `Submission(contest, created)`, `User(-rating)`, `User(-practice_points)`.

## 2. Judge

```
judge/
  runner.py     run_submission(submission_id)  # RQ task
  sandbox.py    compile(lang, src_dir) -> (ok, log)
                run_test(lang, src_dir, input, tl_ms, ml_mb) -> (stdout, verdict, exec_ms)
  compare.py    outputs_match(expected, actual) -> bool  # rstrip each line, ignore trailing blank lines
  images/{python,cpp,java,node}/Dockerfile
```

Flow:
1. View creates `Submission(PENDING)` and enqueues `run_submission`.
2. Worker sets `RUNNING`, writes source to temp dir, runs `compile_cmd` in container (if any). CE → store log, done.
3. For each `TestCase` in order: `docker run --rm --network none --memory {ml}m --memory-swap {ml}m --cpus 1 --pids-limit 64 --read-only --tmpfs /tmp -i --user nobody {image} {run_cmd}` with input on stdin, wrapped in `timeout`. Effective TL = `tl_ms * lang.tl_multiplier`.
4. Exit code 124 → TLE; exit 137 → MLE; nonzero → RE; mismatch → WA. Stop on first non-AC. Save `passed/total`.
5. On AC outside contest: create `UserProblemSolved` if absent, add `problem.points` to `user.practice_points` (atomic `F()` update).

Security: source enters container via bind-mount of a per-submission temp dir (read-only); container non-root; only judge-worker container has `/var/run/docker.sock`; web never runs code. Worker concurrency = 2 per VPS initially.

UI feedback: submission page polls `hx-get` every 1s until verdict is terminal.

## 3. Contests and rating

- Contest problems hidden from non-participants until `end`; `is_public` flips on end.
- Registration: any user before `end`, subject to `require_group` and `allowed_ip_prefix` (checked on register and on each submit).
- ICPC ordering: solved desc, penalty asc; penalty = minutes from start to first AC + 20 × wrong attempts on solved problems.
- Score ordering: sum of `ContestProblem.points` for solved problems, ties by last AC time.
- Standings view cached 30s (Django cache, Redis backend). Freeze not in v1.
- Rating: management command `recalc_rating <contest_id>`, idempotent via `rating_applied`. Elo-style: expected rank from pairwise win probabilities against all participants, delta = K × (seed − actual) with K=40 for first 10 rated contests, else 20. Writes `Participation.rating_before/after`, updates `User.rating`.
- Leaderboards: `/rating` (by `rating`), `/top` (by `practice_points`), both paginated.

## 4. Anti-AI measures

1. **Contest mode (client)**: on contest problem page, `paste`/`copy`/`cut` events on the editor are prevented; `visibilitychange` and `window.blur` are POSTed to `/integrity/event/` as `FocusEvent`. Deterrent only. Teacher sees per-participant counts on contest report page.
2. **Similarity (server, post-contest)**: RQ job after `end` compares every pair of AC submissions per problem (normalized token stream, `difflib.SequenceMatcher.ratio()`); pairs ≥ 0.85 create `SimilarityFlag`. Teacher reviews in admin. No "AI-style" classifier — unreliable, out of scope.
3. **Problem design (process)**: `statement_image` supported; guidance doc for authors — contextual, image/table-driven, Uzbek phrasing, single-use contest problems.
4. **Supervised mode**: `allowed_ip_prefix` + `require_group` on `Contest`. Viva is a teacher process; `SimilarityFlag.note` holds outcome.

## 5. UI

Pages: `/problems` (list, filter by tag/difficulty, solved marker), `/problems/<slug>` (statement, samples, editor, language select, submit), `/submissions/<id>` (verdict polling, per-test results), `/submissions` (mine), `/contests`, `/contests/<id>` (problems, register, standings tab), `/rating`, `/top`, `/profile/<username>`, `/integrity/contest/<id>` (teacher report).
Authoring via Django admin (inline `TestCase`, `ContestProblem`). Custom authoring UI out of scope.

## 6. Testing

- Judge integration test (requires Docker, skipped unless `JUDGE_TESTS=1`): A+B in all four languages → AC; plus WA, TLE (busy loop), RE (div by zero), CE (syntax error) in Python.
- `compare.py` unit tests: whitespace variants.
- Rating: fixture contest with 4 participants, assert deltas; second run is no-op.
- Standings: ICPC penalty and tie cases.
- Contest gating: hidden problem 404 before end, IP prefix rejection.

## Build phases

1. Skeleton, accounts, problems, admin, Python judge, submit + verdict page — working MVP.
2. C++/Java/Node images, practice points, `/top`, `/profile`.
3. Contests, standings, `recalc_rating`, `/rating`.
4. Integrity: focus events, IP/group gating, similarity job, teacher report.

## Out of scope (v1)

Function-signature problems, standings freeze, WebSocket, custom authoring UI, AI-style detection, multi-server judge (interface is ready for it), OAuth.
