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
    python manage.py rqworker default run
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

## Docker compose (dev)

    cp .env.example .env
    sudo mkdir -p /var/codearena/work && sudo chmod 777 /var/codearena/work
    for l in python cpp java node; do docker build -t codearena-judge-$l judge/images/$l; done
    docker compose up --build
    docker compose exec web python manage.py migrate
    docker compose exec web python manage.py seed

## Deploy (VPS, http://SERVER_IP:2009)

Ubuntu/Debian with Docker Engine + compose plugin installed. Everything runs
inside compose: gunicorn + whitenoise (`web`), judge worker (`worker`),
`scheduler` (points sweep every 5 min), Postgres, Redis.

    git clone <repo> /opt/codearena && cd /opt/codearena
    cp .env.prod.example .env
    # edit .env: SECRET_KEY (python3 -c "import secrets;print(secrets.token_urlsafe(50))"),
    #            ALLOWED_HOSTS=SERVER_IP, CSRF_TRUSTED_ORIGINS=http://SERVER_IP:2009, POSTGRES_PASSWORD
    sudo mkdir -p /var/codearena/work && sudo chmod 777 /var/codearena/work
    for l in python cpp java node; do docker build -t codearena-judge-$l judge/images/$l; done
    docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

Once, after the first deploy:

    # nightly DB dump to /var/backups/codearena, 14-day retention
    (sudo crontab -l 2>/dev/null; echo "30 3 * * * /opt/codearena/deploy/backup.sh") | sudo crontab -
    # cap container logs (otherwise json-file logs grow unbounded); restarts docker
    sudo cp deploy/docker-daemon.json /etc/docker/daemon.json && sudo systemctl restart docker
    docker compose exec web python manage.py seed            # languages + admin (admin/admin)
    docker compose exec web python manage.py seed_problems --author admin
    sudo ufw allow 2009/tcp

First thing after start: log in as `admin`, open `/accounts/password_reset/`
or Boshqaruv → Foydalanuvchilar and change the `admin` password.

Update: `git pull && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`
(migrate + collectstatic run on every `web` start). Logs:
`docker compose logs -f web worker scheduler`. Backup:
`docker compose exec db pg_dump -U codearena codearena > backup.sql`.

Behind a domain + HTTPS later: put Caddy/nginx in front of :2009, set
`USE_HTTPS=1`, `ALLOWED_HOSTS=example.com`, `CSRF_TRUSTED_ORIGINS=https://example.com`.

## Contests, rating, integrity

Contests/problems are authored in Boshqaruv (`/moderation/`, staff only). A contest's problems stay hidden (404) from everyone
except registered participants until `end`; unregistered visitors see only
the label + points on `/contests/<id>/`.

Rating is never applied automatically: after the contest ends and cheaters are
disqualified (they rank last), staff press Boshqaruv → Musobaqalar → Reytingni
hisoblash. CLI equivalent:

    python manage.py recalc_rating [contest_id]       # is_rated contests only; no-op once applied

Similarity is checked on demand from the contest's Nazorat hisoboti, for the
problems staff pick (same-language AC pairs, both 4+ lines, >= 90%):

    python manage.py flag_similarity <contest_id> --problems A,C

Publishing contest problems (making them public + awarding practice points)
is a manual staff action: Boshqaruv → Musobaqalar → Ochish. The old
`close_ended_contests` command still exists but is intentionally not
scheduled.

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
