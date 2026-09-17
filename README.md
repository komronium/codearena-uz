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

## Tests

    pytest                                             # unit
    JUDGE_TESTS=1 JUDGE_WORK_DIR=$PWD/work pytest      # + docker sandbox
