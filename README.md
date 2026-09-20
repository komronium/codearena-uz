# CodeArena

Competitive programming platform for students. Django + HTMX, Docker judge.

## Dev (host)

    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    for l in python cpp java node; do docker build -t codearena-judge-$l judge/images/$l; done
    python manage.py migrate && python manage.py seed
    mkdir -p work
    # terminal 1
    docker run -d -p 6379:6379 redis:7
    python manage.py rqworker default
    # terminal 2
    python manage.py runserver

Login `admin` / `admin` (only set on first-ever seed of an empty DB — an
existing `admin` account keeps whatever password it already has). Open
http://localhost:8000/problems/a-plus-b/ and submit
`a,b=map(int,input().split());print(a+b)` → `AC`. Try `print(input())` → `WA`,
`while 1:pass` → `TLE`. Python has no separate compile step, so a syntax error
like `print(` surfaces as `RE`, not `CE` — `CE` only happens for a language
with a real `compile_cmd` (C++, Java — both seeded).

Languages: Python 3, C++ (g++ -O2), Java, JavaScript (Node 20).

## Docker compose

    cp .env.example .env
    sudo mkdir -p /var/codearena/work && sudo chmod 777 /var/codearena/work
    for l in python cpp java node; do docker build -t codearena-judge-$l judge/images/$l; done
    docker compose up --build
    docker compose exec web python manage.py migrate
    docker compose exec web python manage.py seed

## Contests, rating, integrity

Contests/problems/standings are authored via `/admin` (`Contest` inline
`ContestProblem`). A contest's problems stay hidden (404) from everyone
except registered participants until `end`; unregistered visitors see only
the label + points on `/contests/<id>/`.

Three commands are meant to run via cron shortly after contests end. All
three are idempotent and, run with no `<id>`, sweep every ended contest that
still needs the action — no scheduler process, no per-contest bookkeeping:

    python manage.py close_ended_contests            # flips ContestProblem.problem.is_public
    python manage.py flag_similarity [contest_id]    # AC-pair similarity >= 0.85 -> SimilarityFlag
    python manage.py recalc_rating [contest_id]       # is_rated contests only; no-op once applied

Example crontab (every 5 minutes is enough — these are cheap, idempotent no-ops
when nothing changed):

    */5 * * * * cd /path/to/codearena && .venv/bin/python manage.py close_ended_contests >> /var/log/codearena-cron.log 2>&1
    */5 * * * * cd /path/to/codearena && .venv/bin/python manage.py flag_similarity >> /var/log/codearena-cron.log 2>&1
    */5 * * * * cd /path/to/codearena && .venv/bin/python manage.py recalc_rating >> /var/log/codearena-cron.log 2>&1

`recalc_rating` requires `Contest.is_rated=True` and `Contest.has_ended`; it's
a no-op if `rating_applied` is already set. Teacher-only per-contest report
(focus events + similarity flags) is at `/integrity/contest/<id>/`
(`is_staff` required).

`Contest.require_group` / `allowed_ip_prefix` restrict who can register and
submit ("supervised mode") — checked again on every submit, not just at
registration.

## Problems, moderation, SQL problems

Any logged-in user can submit a problem (`/moderation/submit/`) with its test
cases in one form. Staff submissions go live immediately; student submissions
land as `Problem.status="pending"` and need approval in the moderation queue
(`/moderation/`, staff-only) before `is_public` flips true. The author (or
staff) can always preview/submit against their own non-public problem.

`Problem.kind` is `"code"` (default — stdin/stdout program, judged via
`judge.runner` + the per-language Docker sandbox) or `"sql"` (a query
problem: submitted SQL runs once against a `SQLDataset` fixture DB and the
result rows are compared to `SQLDataset.expected_result`, row-order-insensitive).
SQL problems are judged by `judge.sql_judge` using Python's stdlib `sqlite3`
directly in the worker process — no Docker image, no new dependency. The
student's query is sandboxed with `sqlite3.Connection.set_authorizer()`
(only SELECT/read/function calls are allowed — no INSERT/UPDATE/DELETE/
DROP/ATTACH/PRAGMA) and a `set_progress_handler()` wall-clock timeout
(`problem.tl_ms`). Authoring a SQL problem (schema/seed/expected result) is
admin-only for now, via the `SQLDataset` inline on the Problem admin page —
the self-serve `/moderation/submit/` form only creates `kind="code"` problems.

## Password reset

Registration now requires an email (`RegisterForm` — enforced unique at the
form level). Password reset uses Django's built-in views at
`/accounts/password-reset/`. `EMAIL_BACKEND` defaults to the console backend
(prints the email, no real send) — set these env vars for a real send:

    EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
    EMAIL_HOST=... EMAIL_PORT=587 EMAIL_HOST_USER=... EMAIL_HOST_PASSWORD=...
    EMAIL_USE_TLS=1 DEFAULT_FROM_EMAIL=noreply@yourdomain

No email-verification-on-signup gate — registration works with an unverified
email, same as before. Add one later if fake/typo'd emails become a problem.

## Contest clarifications

`/contests/<id>/clarifications/` is a Q&A board for a running contest.
Registered participants (and staff) can ask a question, optionally tied to
one problem. An unanswered question is visible only to its asker and staff;
once staff answers it, it's visible to every participant — standard CP
clarification-board behavior, so answers get shared but questions in flight
don't leak a hint to everyone.

## Tests

    pytest                                             # unit
    JUDGE_TESTS=1 JUDGE_WORK_DIR=$PWD/work pytest      # + docker sandbox
