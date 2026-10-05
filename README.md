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
    python manage.py rqworker default run rejudge
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

## Front end

Everything the browser loads is served from `static/`: no CDN, so the site works
where a CDN is slow or blocked. `frontend/build.mjs` makes it from the versions
pinned in `frontend/package.json` — Tailwind CSS (scanning `templates/` and
`apps/`), the open fonts (Inter, JetBrains Mono, Fira Code; SIL OFL — fallbacks behind the
Anthropic Sans/Mono files kept in `static/fonts`, and editor options), htmx, the Lucide
icons the templates use, highlight.js, KaTeX, EasyMDE and the CodeMirror modules
behind `templates/_importmap.html`. The outputs are committed, so deploys need no
Node. After adding a Tailwind class or an icon to a template:

    cd frontend && npm ci && npm run build   # then commit static/ and templates/_importmap.html

The look (Xon-atlas) lives in `frontend/src/app.css`: colours are CSS variables at the top —
white paper, nil for actions, tun nili for the menu rail, and the atlas colours only where
they mean something (zumrad easy/accepted/live, za’faron medium/medal/streak, malina
hard/wrong, osmon beginner/info) — with a matching dark set; every text pairing at 4.5:1 or
more. The ikat mark is `templates/_brand_mark.html`, the rail `templates/_rail.html`;
`.ca-abr` is the atlas strip used on the landing hero and the profile banner only.

`tests/test_frontend.py` fails when the committed build is stale (it runs where
Node and `frontend/node_modules` exist) and when a template loads a third-party
script or stylesheet.

## Docker compose (dev)

    cp .env.example .env
    sudo mkdir -p /var/codearena/work && sudo chmod 777 /var/codearena/work
    for l in python cpp java node; do docker build -t codearena-judge-$l judge/images/$l; done
    docker compose up --build
    docker compose exec web python manage.py migrate
    docker compose exec web python manage.py seed

## Deploy (VPS, https://codearena.uz)

Ubuntu/Debian with Docker Engine + compose plugin installed. Everything runs
inside compose: gunicorn + whitenoise (`web`), judge worker (`worker`),
`scheduler` (points sweep every 5 min), Postgres, Redis.

    git clone <repo> /opt/codearena && cd /opt/codearena
    cp .env.prod.example .env
    # edit .env: SECRET_KEY (python3 -c "import secrets;print(secrets.token_urlsafe(50))"), POSTGRES_PASSWORD
    sudo install -m 0644 deploy/codearena.tmpfiles.conf /etc/tmpfiles.d/codearena.conf
    sudo systemd-tmpfiles --create /etc/tmpfiles.d/codearena.conf
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
    sudo ufw allow 80/tcp && sudo ufw allow 443/tcp

First thing after start: log in as `admin`, open `/accounts/password_reset/`
or Boshqaruv → Foydalanuvchilar and change the `admin` password.

Update: `git pull && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`
(migrate + collectstatic run on every `web` start). Logs:
`docker compose logs -f web worker scheduler`. Backup:
`docker compose exec db pg_dump -U codearena codearena > backup.sql`.

Nginx serves `codearena.uz` and `www.codearena.uz` on ports 80/443 and proxies to
the web container through `/run/codearena/gunicorn.sock`; the web container has no
published host port. Point both DNS names to the VPS, then issue the TLS certificate
with Certbot (`certbot --nginx -d codearena.uz -d www.codearena.uz --redirect`).
Certbot installs automatic renewal; verify it with `certbot renew --cert-name
codearena.uz --dry-run`.

## Search engines

What Google reads is built in (`apps/home`): `robots.txt` (staff and personal pages, students'
avatars and a list's search/sort/random addresses stay out), `sitemap.xml` (an index of one
sitemap per kind: sections, problems, courses, contests, standings, profiles with something on
them, each with `lastmod`), a canonical URL, description, robots meta and Open Graph/X tags on
every page, and JSON-LD: `WebSite` + `Organization` on the home page (the site name and logo
over a result), `BreadcrumbList` on problems, courses, contests and profiles, `ProfilePage` on
profiles. Google's result icon is `static/img/favicon-96x96.png` (it reads no SVG), plus
`/favicon.ico`, the Apple touch icon and `/manifest.webmanifest`.

Once per domain, in [Google Search Console](https://search.google.com/search-console): add a
*Domain* property for `codearena.uz` and verify it with the DNS TXT record it gives (or put the
HTML-tag code in `GOOGLE_SITE_VERIFICATION`), submit `https://codearena.uz/sitemap.xml`, and ask
URL Inspection to index the home page. Bing Webmaster Tools can import the property from Search
Console; Yandex Webmaster takes `YANDEX_VERIFICATION`. `SITE_SAME_AS` lists the site's own
channels (Telegram, Instagram...) for the Organization. Sitelinks under the result are Google's
own choice: clear titles, the top bar and the footer's plain links are what it picks them from.

## Contests, rating, integrity

Contests/problems are authored in Boshqaruv (`/moderation/`, staff only). A contest's problems stay hidden (404) from everyone
except registered participants until `end`; unregistered visitors see only
the label + points on `/contests/<id>/`.

Rating is never applied automatically: after the contest ends and cheaters are
disqualified (they rank last), staff press Boshqaruv → Musobaqalar → Reytingni
hisoblash. CLI equivalent:

    python manage.py recalc_rating [contest_id]       # is_rated contests only; no-op once applied

The maths is Codeforces' (`apps/contests/rating.py`): Elo seeds, each contestant
moves halfway to the rating that matches their place, and an anti-inflation fee
keeps the changes summing to just below zero. Newcomers are rated from 1000 but
shown 0; their first six rated contests add +360, 250, 180, 110, 70, 30 on top of
the change. Tiers (`apps/accounts/tiers.py`) run from Boshlovchi (below 700) to
Afsonaviy Grandmaster (1900+). A contest can be a division: Div. 1 rates 1900+,
Div. 2 below 1900, Div. 3 below 1600, Div. 4 below 1400; the others take part
out of competition, unrated. After deploying a change to the rating maths, rebuild
every rating once (manual rating edits are lost):

    docker compose exec web python manage.py recalc_rating --replay

Similarity is checked on demand from the contest's Nazorat hisoboti, for the
problems staff pick (same-language AC pairs, both 4+ lines, >= 90%):

    python manage.py flag_similarity <contest_id> --problems A,C

Solves and practice points are derived (`apps/submissions/solves.py`): a solve is
the user's earliest eligible AC (practice, or contest after the contest is
published and the user is not disqualified), and `practice_points` is the
current price of the solved problems, excluding problems the user authored.
The scheduler's `recalc_points` reprices problems and resyncs every total every
5 minutes. After deploying this change, rebuild every solve once:

    docker compose exec web python manage.py recalc_practice_points

Publishing a contest is a manual staff action after it ends: Boshqaruv →
Musobaqalar → Masalalarni ochish. It makes the problems public and lets
participants' contest ACs count as practice solves. Disqualified participants'
contest ACs never count, and disqualifying after publish takes those solves
back. The old `close_ended_contests` command still exists but is intentionally
not scheduled; it only opens problems and does not publish.

After fixing a problem's tests, staff rejudge it from Boshqaruv → Masalalar
(the ↻ button): its finished submissions go back to the low-priority `rejudge`
RQ queue, and verdicts, solves, points and standings follow the new results.
Ratings already applied do not change.

`recalc_rating` requires `Contest.is_rated=True` and `Contest.has_ended`; it's
a no-op if `rating_applied` is already set. Disqualifying or re-qualifying
someone after that recomputes the contest's rating when it is still the latest
rated contest of its participants; otherwise ratings stay and staff get a warning.

Teacher-only per-contest report is at `/integrity/contest/<id>/` (`is_staff`
required): browser events, plus server-side evidence the browser can't hide —
submits with no tracker heartbeat, code that never appeared in the editor
snapshots, code jumps, one device shared by two participants, one participant on
two devices at once — and similarity flags (contest ACs, the last attempt of
those without AC, and solutions from before the contest). Every staff action
that changes a result (DQ, rejudge, publish, rating, flag review, deletes) is in
the audit log at `/integrity/audit/`; a disqualified participant sees the reason
on the contest page.

`Contest.require_group` / `allowed_ip_prefix` restrict who can register and
submit ("supervised mode") — checked again on every submit, not just at
registration.

## Learning and classroom

- **Homework** (`/classroom/`): a group's teacher (or staff) gives a problem set with a
  deadline; the grid shows each student as on time / late / tried, with CSV export.
  Only public problems can be assigned.
- **Hints and editorials**: staff add hints on the problem form, each costing a share of
  the price if opened before the solve (capped at 90 %); the editorial opens after AC.
  Both are locked while a contest or a duel uses the problem.
- **Code review**: a group's teacher comments on a student's submission by line; the
  student sees an unread badge and can reply.
- **Skill map / next problem**: per-tag progress on the profile; "Keyingi masala" on the
  problem list picks from the weakest tags at the student's level.
- **Daily problem**: picked automatically per Tashkent day; solving it on its day keeps
  the streak and gives +5 practice points.
- **Virtual contests**: after a contest is published, anyone who didn't take part can
  replay it on their own clock and see where they would have placed. Unrated.
- **Duels** (`/classroom/duels/`): 1v1 on a problem neither player tried, 30 minutes,
  first AC wins, separate duel rating.

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
