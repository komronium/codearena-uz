# Honest Results (sub-project A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every verdict, standing, solve, point total and rating-board entry that CodeArena shows correct, and stop a submitted program from influencing how it is judged.

**Architecture:** Solves and practice points become derived data maintained by one module (`apps/submissions/solves.py`); every caller that can change them (runner, publish, disqualify, sweep, rejudge) goes through it. The Docker judge splits users inside the one per-submission container: a root runner script, each test as `nobody`, with a total output cap. The remaining fixes are local: the standings penalty set, contest-problem freshness validation, delete guards, a rejudge action, the rating-board filter and rate limits on the integrity endpoints.

**Tech Stack:** Django 5.2 (Python 3.12 in the prod image), HTMX + Tailwind CDN templates, RQ via django-rq, Docker judge images (alpine/busybox), pytest + pytest-django.

**Spec:** `docs/superpowers/specs/2026-09-26-honest-results-design.md` (read it with this plan; the corrections below win where they differ).

## Global Constraints

- No new dependencies; `requirements.txt` stays unchanged.
- No Django admin. All staff tools live under `/moderation/` or existing staff views.
- UI copy is Uzbek (Latin). Use the exact strings given in the tasks; new strings use `‘` (U+2018) as the apostrophe. Do not reword existing strings unless a task says so.
- Code must run on Python 3.12 (prod image `python:3.12-slim-bookworm`), even though the dev venv is newer.
- Contest penalty set: `PENALIZED = {"WA", "TLE", "MLE", "RE", "OLE"}`.
- Output limit: `DEFAULT_OUTPUT_LIMIT = 16 * 1024 * 1024` bytes, total over all tests of one run.
- New verdict `OLE`: shown as "OL", title "Output Limit — chiqish hajmi chegarasi oshdi", warn style.
- Integrity rate limits: `/integrity/event/` 60 per minute per user, `/integrity/snapshot/` 20 per minute per user, fixed 60-second window, HTTP 429 when over.
- New RQ queue `rejudge` with `DEFAULT_TIMEOUT` 600. Workers listen `default run rejudge`, in that order.
- Migrations, exactly: `problems/0010_testcase_ordering`, `submissions/0004_submission_verdict_ole`, `contests/0006_contest_published_at`, `submissions/0005_userproblemsolved_cascade`.
- Git: do not `git commit` or `git push` unless the user explicitly approved commits for this plan. Every "Commit" step below is conditional on that approval; without it, skip the step and leave the changes in the working tree.
- Do not run `migrate` against the dev `db.sqlite3` as part of this plan (the test settings share it); pytest applies every migration to its own test database.
- Unit tests: `pytest -q`. Docker judge tests: `JUDGE_TESTS=1 JUDGE_WORK_DIR=$PWD/work pytest judge -q` (needs the four `codearena-judge-*` images; they are built on this machine).
- Comments explain why, not what. Deliberate shortcuts with a known ceiling get a `ponytail:` comment naming the ceiling and the upgrade path.

## Review Focus

1. Editing a rated contest that is running and holds its own hidden problems must still save; the freshness check may only flag problems that are public or used in another contest (Task 9 test `test_contest_edit_is_not_blocked_by_its_own_or_ended_problems`).
2. A problem whose correct answers are large (several MB of expected output) must still be judged AC, never OLE (Task 4 test `test_runner_output_limit_leaves_room_for_big_answers`).
3. A trial run ("Sinab ko‘rish") that floods stdout must show "OL", not the generic "Xato" chip (Task 3 test `test_ole_verdict_shows_as_output_limit`).
4. A double-clicked rejudge must not queue any submission twice (Task 11 test `test_rejudge_requeues_finished_submissions_once`).
5. Publishing a contest twice, and toggling a disqualification off and on, must neither double nor lose points (Task 8 tests `test_contest_publish_opens_problems_and_grants_points` and `test_disqualifying_after_publish_takes_contest_solves_back`).

## Spec corrections found while planning

These were found by probing and reading code after the spec was approved. The plan implements the corrected behavior; the user reviews them with this plan.

1. **OLE comes from the output size, not from SIGXFSZ.** Probe on 2026-09-26 with `--ulimit fsize=1048576`: only C++ dies of SIGXFSZ (rc 25). Python gets `OSError: [Errno 27] File too large` and exits 1 (would be RE); Java and Node ignore the failed writes and run until the time limit (would be TLE/MLE). The runner script therefore marks a test OLE (rc 153) when the output total reaches the limit, whatever the exit code, and does not grep for "signal 25".
2. **The output limit is a total over all tests of a run, not per test.** A per-file cap alone lets a submission with N tests make the worker read N × 16 MiB into memory. `run_submission` passes `max(DEFAULT_OUTPUT_LIMIT, 2 × total expected output bytes)` (spec said "2 × largest").
3. **The publish button shows while `published_at` is unset** (was: while some problem is hidden). Unrated contests may now use public problems, so the old condition could hide the button forever and such a contest's ACs would never count.
4. **`recalc_practice_points` rebuilds every solve, then syncs points** (spec: thin wrapper around `sync_practice_points()`). Run it once after deploy: it removes the solves the old publish gave disqualified participants and adds contest solves for contests the backfill marks as published.
5. **`contest_delete` refuses a contest that has submissions** (not in spec). `Submission.contest` is `SET_NULL`, so deleting a contest would turn its ACs, unpublished and disqualified ones included, into practice ACs that count as solves.
6. **The problems list counts finished submissions with a subquery**, not a second `Count` join (spec: `distinct=True`), so tests × submissions rows are never multiplied. The count shown is of finished submissions, which is exactly what a rejudge resets.
7. **A run that stops early with only passing tests is a failure** (not in spec; pre-existing bug found by probe on 2026-09-26). When the runner script inside the container dies before it finishes (for example because the submission used up the container's process limit, so the script cannot start its helper commands), the host sees only the results written so far, all passing, and `judge.runner` scores the submission AC with fewer tests passed than exist. `run_tests` now reports the next test as failed: RE, or TLE when the outer time guard stopped the container. The runner script itself only stops early after a failing test, so no honest run is affected.

## File map

| File | Responsibility | Tasks |
|---|---|---|
| `apps/contests/standings.py` | penalty only for `PENALIZED` verdicts | 1 |
| `apps/problems/models.py` + migration 0010 | `TestCase` ordering | 2 |
| `apps/submissions/models.py` + migrations 0004, 0005 | `OLE` verdict; UPS `CASCADE`; UPS docstring | 3, 6, 10 |
| `templates/submissions/_verdict.html`, `templates/base.html`, `templates/problems/detail.html`, `apps/submissions/views.py` | OLE display; message level classes | 3, 9 |
| `judge/sandbox.py` | container flags, uid split, output cap, OLE mapping, cut-short runs fail | 4 |
| `judge/runner.py` | output limit per problem; finalize every verdict via `refresh_solves` | 4, 6 |
| `apps/contests/models.py` + migration 0006 | `Contest.published_at` + backfill | 5 |
| `apps/submissions/solves.py` (new) | eligibility rule, `refresh_solves`, `sync_practice_points` | 5 |
| `apps/problems/management/commands/recalc_points.py`, `apps/accounts/management/commands/recalc_practice_points.py`, `apps/problems/management/commands/seed_demo.py` | live points, full rebuild | 7 |
| `apps/moderation/forms.py`, `templates/moderation/user_form.html` | `practice_points` read-only; contest freshness formset | 7, 9 |
| `apps/moderation/views.py`, `apps/moderation/urls.py`, `templates/moderation/contests.html`, `templates/moderation/problems.html` | publish, freshness warning, delete guards, rejudge | 8–11 |
| `apps/contests/views.py` | disqualify moves solves after publish | 8 |
| `apps/contests/services.py` | `reuse_reason` | 9 |
| `config/settings/base.py`, `docker-compose.yml`, `docker-compose.prod.yml`, `README.md` | `rejudge` queue; docs | 7, 8, 11 |
| `apps/accounts/views.py`, `templates/accounts/profile.html` | rating board and profile for unrated users | 12 |
| `apps/submissions/ratelimit.py` (new), `apps/submissions/views.py`, `apps/integrity/views.py` | shared rate limiter; integrity limits | 13 |

---

### Task 1: Standings penalize only judged wrong answers

**Files:**
- Modify: `apps/contests/standings.py`
- Test: `apps/contests/tests.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `apps.contests.standings.PENALIZED: set[str]`.

- [ ] **Step 1: Write the failing test**

Append after `test_score_ties_break_by_penalty` in `apps/contests/tests.py`:

```python
def test_only_judged_wrong_answers_cost_penalty(contest, problem_a, problem_b, python):
    ali = User.objects.create_user("ali", password="x")
    bob = User.objects.create_user("bob", password="x")
    Participation.objects.create(user=ali, contest=contest)
    Participation.objects.create(user=bob, contest=contest)

    # ali: a compile error and a still-pending run before the AC cost nothing
    _sub(ali, problem_a, contest, python, "CE", 1)
    _sub(ali, problem_a, contest, python, "PENDING", 2)
    _sub(ali, problem_a, contest, python, "AC", 10)
    # unsolved B: CE and RUNNING are not shown as wrong tries either
    _sub(ali, problem_b, contest, python, "CE", 3)
    _sub(ali, problem_b, contest, python, "RUNNING", 4)
    # bob: an output-limit failure is a real wrong try
    _sub(bob, problem_a, contest, python, "OLE", 1)
    _sub(bob, problem_a, contest, python, "AC", 10)

    rows = {r["user"]: r for r in compute_standings(contest)}
    assert rows[ali]["penalty"] == 10 and rows[ali]["cells"][0]["wrong"] == 0
    assert rows[ali]["cells"][1]["wrong"] == 0
    assert rows[bob]["penalty"] == 30 and rows[bob]["cells"][0]["wrong"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest apps/contests/tests.py::test_only_judged_wrong_answers_cost_penalty -q`
Expected: FAIL, `assert 50 == 10` (CE and PENDING each added 20 minutes).

- [ ] **Step 3: Implement**

In `apps/contests/standings.py`, add below the import:

```python
from apps.submissions.models import Submission

# Only a judged wrong answer is a wrong try: compile errors and submissions still in
# the queue cost no penalty and are not shown as tries.
PENALIZED = {"WA", "TLE", "MLE", "RE", "OLE"}
```

Replace the two counting lines inside `compute_standings`:

```python
                wrong = sum(1 for s in subs if s.verdict != "AC")
```
with
```python
                wrong = sum(1 for s in subs if s.verdict in PENALIZED)
```
and
```python
            wrong = sum(1 for s in subs if s.created < ac.created and s.verdict != "AC")
```
with
```python
            wrong = sum(1 for s in subs if s.created < ac.created and s.verdict in PENALIZED)
```

Leave `attempted` unchanged (any submission counts as taking part, used by `recalc_rating`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest apps/contests/tests.py -q`
Expected: all pass.

- [ ] **Step 5: Commit (only if the user approved commits)**

```bash
git add apps/contests/standings.py apps/contests/tests.py
git commit -m "fix: contest penalty counts only judged wrong answers, not CE or queued runs"
```

---

### Task 2: Tests run in their `order`

**Files:**
- Modify: `apps/problems/models.py` (class `TestCase`)
- Create: `apps/problems/migrations/0010_testcase_ordering.py` (generated)
- Test: `apps/submissions/tests.py`

**Interfaces:**
- Produces: `TestCase.Meta.ordering = ["order", "id"]`; `problem.testcases.all()` and `Problem.samples` come back in that order.

- [ ] **Step 1: Write the failing test**

Append after `test_runner_tle` in `apps/submissions/tests.py`:

```python
@patch("judge.runner.sandbox.run_tests", return_value=[])
@patch("judge.runner.sandbox.compile", return_value=(True, ""))
def test_runner_runs_tests_in_their_order(compile_, run_tests, problem, python, user):
    from judge.runner import run_submission
    TestCase.objects.create(problem=problem, input="first\n", expected="x\n", order=-1)
    s = Submission.objects.create(user=user, problem=problem, language=python, source="x")
    run_submission(s.pk)
    assert run_tests.call_args.args[2] == ["first\n", "1 2\n", "5 7\n"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest apps/submissions/tests.py::test_runner_runs_tests_in_their_order -q`
Expected: FAIL, the list starts with `"1 2\n"` (insertion order).

- [ ] **Step 3: Implement**

In `apps/problems/models.py`, give `TestCase` a `Meta` (commit a90329b dropped it):

```python
class TestCase(models.Model):
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name="testcases")
    input = models.TextField()
    expected = models.TextField()
    is_sample = models.BooleanField(default=False)
    order = models.IntegerField(default=0)

    class Meta:
        # "Test 1" must stay the same test after an edit; the runner and the samples use this.
        ordering = ["order", "id"]
```

Generate the migration:

Run: `python manage.py makemigrations problems -n testcase_ordering`
Expected: creates `apps/problems/migrations/0010_testcase_ordering.py` with one `AlterModelOptions(name="testcase", options={"ordering": ["order", "id"]})`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest apps/submissions/tests.py apps/problems/tests.py apps/moderation/tests.py -q`
Expected: all pass.

- [ ] **Step 5: Commit (only if the user approved commits)**

```bash
git add apps/problems/models.py apps/problems/migrations/0010_testcase_ordering.py apps/submissions/tests.py
git commit -m "fix: run tests in their order field so Test 1 stays Test 1"
```

---

### Task 3: `OLE` verdict and its display

**Files:**
- Modify: `apps/submissions/models.py` (`Submission.Verdict`, `Submission.TERMINAL`)
- Create: `apps/submissions/migrations/0004_submission_verdict_ole.py` (generated)
- Modify: `templates/submissions/_verdict.html`, `templates/base.html` (`.ca-test-*` rule), `apps/submissions/views.py` (`mine`), `templates/problems/detail.html` (trial `V` and `HINT` maps)
- Test: `apps/submissions/tests.py`

**Interfaces:**
- Produces: `Submission.Verdict.OLE == "OLE"`, `"OLE" in Submission.TERMINAL`. Task 4 returns `"OLE"` from `sandbox.run_tests`; Task 1 already penalizes it.

- [ ] **Step 1: Write the failing test**

Append after `test_status_compact_poll_stays_compact` in `apps/submissions/tests.py`:

```python
def test_ole_verdict_shows_as_output_limit(client, problem, python, user):
    Submission.objects.create(user=user, problem=problem, language=python, source="x", verdict="WA")
    s = Submission.objects.create(user=user, problem=problem, language=python, source="x", verdict="OLE",
                                  total=2)
    TestResult.objects.create(submission=s, testcase=problem.testcases.first(), verdict="OLE")
    client.force_login(user)
    status = client.get(reverse("submissions:status", args=[s.pk])).content
    assert b"ca-verdict-warn" in status and b"Output Limit" in status and b"ca-test-OLE" in status
    mine = client.get(reverse("submissions:mine") + "?verdict=OLE")
    assert list(mine.context["subs"]) == [s] and ("OLE", "OL") in mine.context["verdicts"]
    detail = client.get(reverse("problems:detail", args=[problem.slug])).content
    assert b'OLE: ["warn", "scissors", "OL"]' in detail and b"Chiqish hajmi chegarasi oshdi." in detail
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest apps/submissions/tests.py::test_ole_verdict_shows_as_output_limit -q`
Expected: FAIL (`OLE` is not terminal, so the status partial still polls and shows "Navbatda").

- [ ] **Step 3: Implement**

`apps/submissions/models.py`:

```python
    class Verdict(models.TextChoices):
        PENDING = "PENDING"
        RUNNING = "RUNNING"
        AC = "AC"
        WA = "WA"
        TLE = "TLE"
        MLE = "MLE"
        OLE = "OLE"
        RE = "RE"
        CE = "CE"

    TERMINAL = {"AC", "WA", "TLE", "MLE", "OLE", "RE", "CE"}
```

Run: `python manage.py makemigrations submissions -n submission_verdict_ole`
Expected: creates `apps/submissions/migrations/0004_submission_verdict_ole.py` with one `AlterField` on `submission.verdict`.

`templates/submissions/_verdict.html`, insert after the `MLE` branch:

```html
{% elif v == "OLE" %}
<span class="ca-verdict ca-verdict-warn" title="Output Limit — chiqish hajmi chegarasi oshdi"><i data-lucide="scissors" class="lu" aria-hidden="true"></i>OL</span>
```

`templates/base.html`, the test-square rule:

```css
    .ca-test-TLE, .ca-test-MLE, .ca-test-OLE { background: rgb(var(--ca-warn-rgb)); color: rgb(var(--ca-on-fill-rgb)); }
```

`apps/submissions/views.py`, in `mine`:

```python
    verdicts = [("AC", "AC"), ("WA", "WA"), ("TLE", "TL"), ("MLE", "ML"), ("OLE", "OL"), ("RE", "RE"), ("CE", "CE")]
```

`templates/problems/detail.html`, the trial maps (around line 513):

```js
    const V = { AC: ["ac", "check", "AC"], OK: ["ac", "check", "Bajarildi"], WA: ["bad", "x", "WA"],
                TLE: ["warn", "clock", "TL"], MLE: ["warn", "cpu", "ML"], OLE: ["warn", "scissors", "OL"],
                RE: ["bad", "triangle-alert", "RE"], CE: ["mute", "code", "CE"], IE: ["mute", "circle-alert", "Xato"] };
```

```js
    const HINT = { TLE: "Vaqt chegarasi oshdi.", MLE: "Xotira chegarasi oshdi.", OLE: "Chiqish hajmi chegarasi oshdi.",
                   RE: "Dastur xato bilan tugadi." };
```

(The staff submissions filter reads `Submission.Verdict.values`, so it lists OLE with no change.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest apps/submissions/tests.py -q`
Expected: all pass.

- [ ] **Step 5: Commit (only if the user approved commits)**

```bash
git add apps/submissions/models.py apps/submissions/migrations/0004_submission_verdict_ole.py \
  templates/submissions/_verdict.html templates/base.html apps/submissions/views.py \
  templates/problems/detail.html apps/submissions/tests.py
git commit -m "feat: OLE (output limit) verdict, shown as OL everywhere a verdict appears"
```

---

### Task 4: Judge isolation and the output cap

**Files:**
- Replace: `judge/sandbox.py` (full content below)
- Modify: `judge/runner.py` (`run_submission`, the `run_tests` call)
- Create: `judge/tests/test_sandbox_results.py` (unit, no Docker; `test_sandbox.py` is skipped as a whole without `JUDGE_TESTS=1`)
- Test: `judge/tests/test_sandbox.py`, `judge/tests/test_languages.py` (Docker, `JUDGE_TESTS=1`), `apps/submissions/tests.py` (unit)

**Interfaces:**
- Consumes: `"OLE"` verdict (Task 3).
- Produces: `judge.sandbox.DEFAULT_OUTPUT_LIMIT: int`; `run_tests(lang, src_dir: str, inputs: list[str], tl_ms: int, ml_mb: int, output_limit: int = DEFAULT_OUTPUT_LIMIT) -> list[tuple[str, str, int, int]]` with verdicts `OK | TLE | MLE | RE | OLE`; the list is shorter than `inputs` only when it ends in a failure. `compile()` is unchanged in signature.

Behavior verified by probe on 2026-09-26 with the prototype of this exact file, on all four images: A+B OK with memory recorded; a flood is OLE with the file cut at exactly the limit (python, cpp, java, node); reading `/work/tests/0001.in` → blocked; appending to `/out/result`, writing `/tmp/mem` or opening `/proc/1/fd/1` → PermissionError; an orphan `sleep` is gone by the next test; 3 × 300 KB with a 700 KB limit → OK, OK, OLE; TLE, MLE, RE, no-network unchanged; a run whose runner script dies after test 1 of 4 → OK, RE (the current sandbox returns only the OK, which the runner scores as AC).

- [ ] **Step 1: Write the failing tests**

Append to `judge/tests/test_sandbox.py`:

```python
def test_solution_cannot_read_test_inputs():
    d = _src("try:\n    print(open('/work/tests/0001.in').read().strip())\nexcept OSError:\n    print('blocked')")
    res = run_tests(Lang, d, ["1\n", "secret\n"], 1000, 64)
    assert [o for o, _, _, _ in res] == ["blocked\n", "blocked\n"]


def test_solution_cannot_forge_results():
    # A forged "test 2 passed" line would show up as a second result.
    d = _src("try:\n    open('/out/result', 'a').write('0001 0 0 0 0\\n')\nexcept OSError:\n    pass\nprint(1/0)")
    assert [v for _, v, _, _ in run_tests(Lang, d, ["", ""], 1000, 64)] == ["RE"]


def test_output_flood_is_ole_and_capped():
    d = _src("import sys\nwhile True: sys.stdout.write('x' * 65536)")
    res = run_tests(Lang, d, ["", ""], 2000, 64, output_limit=1 << 20)
    assert [v for _, v, _, _ in res] == ["OLE"]
    assert os.path.getsize(os.path.join(d, "out", "0000.out")) <= 1 << 20


def test_output_limit_counts_all_tests_together():
    d = _src("print('x' * 300_000)")
    res = run_tests(Lang, d, ["", "", ""], 2000, 64, output_limit=700_000)
    assert [v for _, v, _, _ in res] == ["OK", "OK", "OLE"]


def test_orphan_is_killed_before_next_test():
    d = _src("import subprocess\n"
             "if input() == '1':\n"
             "    subprocess.Popen(['sleep', '30'], start_new_session=True)\n"
             "    print('spawned')\n"
             "else:\n"
             "    r = subprocess.run(['pgrep', 'sleep'], capture_output=True)\n"
             "    print('alive' if r.stdout.strip() else 'gone')")
    res = run_tests(Lang, d, ["1\n", "2\n"], 2000, 64)
    assert [o for o, _, _, _ in res] == ["spawned\n", "gone\n"]
```

Append to `judge/tests/test_languages.py`:

```python
FLOOD_SOURCE = {
    "cpp": "#include <cstdio>\nint main(){static char b[65536]; for(auto&c:b)c='x';"
           " while(1) fwrite(b,1,sizeof b,stdout);}\n",
    "java": "public class Main{public static void main(String[] a){String s=\"x\".repeat(65536);"
            "while(true) System.out.print(s);}}\n",
    "node": "const s='x'.repeat(65536); while(true) process.stdout.write(s);\n",
}


@pytest.mark.parametrize("lang_code", ["cpp", "java", "node"])
def test_output_flood_is_ole(lang_code):
    # Only C++ dies of SIGXFSZ; Java and Node keep running with failed writes, so the
    # verdict has to come from the capped output size, not from how the program ended.
    lang = LANGS[lang_code]
    d = _src(lang_code, FLOOD_SOURCE[lang_code])
    ok, log = compile(lang, d)
    assert ok, log
    res = run_tests(lang, d, [""], 1000, 256, output_limit=1 << 20)
    assert [v for _, v, _, _ in res] == ["OLE"]
```

Append after `test_runner_runs_tests_in_their_order` in `apps/submissions/tests.py`:

```python
@patch("judge.runner.sandbox.run_tests", return_value=[])
@patch("judge.runner.sandbox.compile", return_value=(True, ""))
def test_runner_output_limit_leaves_room_for_big_answers(compile_, run_tests, problem, python, user):
    from judge import sandbox
    from judge.runner import run_submission
    s = Submission.objects.create(user=user, problem=problem, language=python, source="x")
    run_submission(s.pk)
    assert run_tests.call_args.kwargs["output_limit"] == sandbox.DEFAULT_OUTPUT_LIMIT
    big = "x" * (9 * 1024 * 1024)
    TestCase.objects.create(problem=problem, input="0\n", expected=big, order=2)
    s = Submission.objects.create(user=user, problem=problem, language=python, source="x")
    run_submission(s.pk)
    assert run_tests.call_args.kwargs["output_limit"] == 2 * (len("3\n") + len("12\n") + len(big))
```

Create `judge/tests/test_sandbox_results.py` (how the host reads the runner's result file; the container is faked, so it runs in the normal suite):

```python
from unittest.mock import patch

import pytest

from judge import sandbox


class Lang:  # duck-typed stand-in for problems.Language
    code = "python"
    docker_image = "unused"
    compile_cmd = ""
    run_cmd = "python3 main.py"
    tl_multiplier = 1.0


@pytest.mark.parametrize("result, timed_out, want", [
    ("0000 0 10.00 10.02 900\n", False, [("3\n", "OK"), ("", "RE")]),  # runner died after test 1
    ("0000 0 10.00 10.02 900\n", True, [("3\n", "OK"), ("", "TLE")]),  # outer guard stopped the container
    (None, False, [("", "RE")]),  # container never got going
])
def test_run_cut_short_is_never_a_pass(tmp_path, result, timed_out, want):
    """The runner script stops early only after a failing test, so results that end
    after passing tests mean the container died under it: the next test fails."""
    def fake_run(cmd, stdin, timeout_s, name):
        if result is not None:
            (tmp_path / "out" / "0000.out").write_text("3\n")
            (tmp_path / "out" / "result").write_text(result)
        return None, 20, timed_out

    with patch("judge.sandbox._run", fake_run):
        res = sandbox.run_tests(Lang, str(tmp_path), ["1 2\n", "5 7\n", "0 0\n", "9 9\n"], 1000, 64)
    assert [(out, v) for out, v, _, _ in res] == want
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest apps/submissions/tests.py::test_runner_output_limit_leaves_room_for_big_answers judge/tests/test_sandbox_results.py -q`
Expected: FAIL (`KeyError: 'output_limit'` or `AttributeError: ... DEFAULT_OUTPUT_LIMIT`); the two cut-short cases FAIL with `[('3\n', 'OK')]`; the "never got going" case passes already (it pins that behavior through the change).

Run: `JUDGE_TESTS=1 JUDGE_WORK_DIR=$PWD/work pytest judge -q`
Expected: the 5 new sandbox tests and 3 flood tests FAIL (`unexpected keyword argument 'output_limit'`, `'secret\n'` read, orphan `'alive\n'`); the old judge tests pass.

- [ ] **Step 3: Implement the sandbox**

Replace `judge/sandbox.py` with:

```python
"""Docker sandbox. One container per compile, one container per submission for
the tests (a runner script loops over them inside), since `docker run` costs
~0.5-1s and a problem has dozens of tests. Interface stable so it can be
swapped for `isolate` later."""
import os
import shlex
import subprocess
import time
import uuid

SOURCE_FILENAME = {"python": "main.py", "cpp": "main.cpp", "java": "Main.java", "node": "main.js"}

# Bytes of stdout one run may write over all of its tests together; judge.runner
# raises it for problems whose own answers are large.
DEFAULT_OUTPUT_LIMIT = 16 * 1024 * 1024

_BASE = ["docker", "run", "--rm", "--network", "none", "--cpus", "1", "--pids-limit", "64",
         "--read-only", "--tmpfs", "/tmp", "-i", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
         "--ulimit", "core=0", "-w", "/work"]
# The test runner is the only root process in its container: SETUID/SETGID let it `su`
# to nobody for each test, DAC_OVERRIDE lets it read test files owned by the worker's
# host user (uid 1000 in dev, 0 in prod) whatever their mode.
_RUNNER_USER = ["--user", "root", "--cap-add", "SETUID", "--cap-add", "SETGID", "--cap-add", "DAC_OVERRIDE"]

# Runs inside the (alpine/busybox) image as root; each test runs as `nobody`, which can
# read no test file (0600), write nothing in /out (0755, not its own) and not open PID 1's
# stdout. Stops at the first non-zero exit so a TLE solution doesn't burn TL x tests; WA
# is decided on the host and keeps going.
# /proc/uptime gives 10ms resolution without needing `date +%N`.
# `busybox time -f %M` records peak RSS (KB) as the last field (on failure busybox
# prefixes "Command exited with non-zero status N"). su, `sh -c "exec ..."` and busybox
# timeout all exec in one pid, so time measures the solution itself and a timeout kill
# hits it directly. time reports a SIGKILL as rc=9, so map that back to 137, which the
# TLE/MLE split below expects. `kill -9 -1` as nobody then removes anything the solution
# left running. Output: --ulimit fsize stops every file at the limit and the total over
# all tests is summed here; reaching the limit is OLE (rc 153) however the program ended,
# since only C++ dies of SIGXFSZ (Python exits on EFBIG, Java and Node keep going).
_RUNNER = """#!/bin/sh
t=0
for f in /work/tests/*.in; do
  n=$(basename "$f" .in)
  rm -f /tmp/mem
  s=$(cut -d' ' -f1 /proc/uptime)
  busybox time -f %M -o /tmp/mem su -s /bin/sh nobody -c {cmd} < "$f" > "/out/$n.out" 2>/dev/null
  rc=$?
  e=$(cut -d' ' -f1 /proc/uptime)
  su -s /bin/sh nobody -c 'kill -9 -1' 2>/dev/null
  grep -q "terminated by signal 9" /tmp/mem 2>/dev/null && rc=137
  t=$((t + $(wc -c < "/out/$n.out")))
  [ "$t" -ge {limit} ] && rc=153
  m=$(awk 'END{{print $NF}}' /tmp/mem 2>/dev/null)
  case "$m" in ''|*[!0-9]*) m=0;; esac  # keep the field numeric whatever busybox printed
  echo "$n $rc $s $e ${{m:-0}}" >> /out/result
  [ "$rc" -ne 0 ] && break
done
"""


def _run(cmd: list[str], stdin: str, timeout_s: float, name: str):
    start = time.monotonic()
    try:
        p = subprocess.run(cmd, input=stdin, capture_output=True, text=True, timeout=timeout_s)
        return p, int((time.monotonic() - start) * 1000), False
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "kill", name], capture_output=True)
        return None, int((time.monotonic() - start) * 1000), True


def compile(lang, src_dir: str) -> tuple[bool, str]:
    if not lang.compile_cmd:
        return True, ""
    name = f"ca-c-{uuid.uuid4().hex[:12]}"
    cmd = _BASE + ["--user", "nobody", "--name", name, "--memory", "512m", "--memory-swap", "512m",
                   "-v", f"{src_dir}:/work", lang.docker_image, "sh", "-c", lang.compile_cmd]
    p, _, timed_out = _run(cmd, "", 30, name)
    if timed_out:
        return False, "compile timeout"
    return p.returncode == 0, (p.stderr or "")[:4000]


def run_tests(lang, src_dir: str, inputs: list[str], tl_ms: int, ml_mb: int,
              output_limit: int = DEFAULT_OUTPUT_LIMIT) -> list[tuple[str, str, int, int]]:
    """Run every input in one container. Returns (stdout, verdict, ms, kb) per test in
    order, verdict in {OK, TLE, MLE, RE, OLE}; stops after the first non-OK test, so
    the list is shorter than `inputs` only when it ends in a failure. `output_limit`
    caps the bytes written to stdout over all tests together, so at most that much is
    ever read back here."""
    tests_dir, out_dir = os.path.join(src_dir, "tests"), os.path.join(src_dir, "out")
    os.makedirs(tests_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    for i, inp in enumerate(inputs):
        path = os.path.join(tests_dir, f"{i:04d}.in")
        with open(path, "w") as f:
            f.write(inp)
        os.chmod(path, 0o600)
    tl_s = tl_ms * lang.tl_multiplier / 1000
    runner = os.path.join(src_dir, "run.sh")
    with open(runner, "w") as f:
        f.write(_RUNNER.format(cmd=shlex.quote(f"exec timeout -s KILL {tl_s + 0.3:.2f} {lang.run_cmd}"),
                               limit=output_limit))
    # Only the root runner reads these; a test gets nothing but its own stdin.
    os.chmod(tests_dir, 0o700)
    os.chmod(runner, 0o700)
    os.chmod(out_dir, 0o755)

    name = f"ca-r-{uuid.uuid4().hex[:12]}"
    cmd = _BASE + _RUNNER_USER + ["--ulimit", f"fsize={output_limit}", "--name", name,
                                  "--memory", f"{ml_mb}m", "--memory-swap", f"{ml_mb}m",
                                  "-v", f"{src_dir}:/work:ro", "-v", f"{out_dir}:/out", lang.docker_image,
                                  "sh", "/work/run.sh"]
    # Outer guard only: per-test TL is enforced by `timeout` inside the container.
    _, _, timed_out = _run(cmd, "", len(inputs) * (tl_s + 0.5) + 10, name)

    results = []
    try:
        with open(os.path.join(out_dir, "result")) as f:
            lines = f.read().split("\n")
    except FileNotFoundError:
        lines = []  # the container never got going
    for line in lines:
        if not line.strip():
            continue
        n, rc, s, e, kb = line.split()
        ms, kb, rc = int((float(e) - float(s)) * 1000), int(kb), int(rc)
        if rc == 153:
            results.append(("", "OLE", ms, kb))
        elif rc == 137 and ms >= tl_ms * lang.tl_multiplier:
            results.append(("", "TLE", ms, kb))
        elif rc == 137:
            results.append(("", "MLE", ms, kb))
        else:
            try:
                with open(os.path.join(out_dir, f"{n}.out"), errors="replace") as f:
                    out = f.read()
            except FileNotFoundError:
                out = ""
            results.append((out, "OK" if rc == 0 else "RE", ms, kb))
    # The runner script stops early only after a failing test. Results that end after
    # passing tests mean the container died under it (e.g. no process slot left to run
    # its helper commands) or the outer guard stopped it: the next test fails, so a
    # cut-short run can never pass.
    if len(results) < len(inputs) and all(v == "OK" for _, v, _, _ in results):
        results.append(("", "TLE" if timed_out else "RE", 0, 0))
    return results
```

- [ ] **Step 4: Pass the per-problem limit from the runner**

In `judge/runner.py`, `run_submission`, replace:

```python
        final, passed, max_ms, max_kb = Submission.Verdict.AC, 0, 0, 0
        results = sandbox.run_tests(lang, src_dir, [tc.input for tc in tests], problem.tl_ms, problem.ml_mb)
```

with:

```python
        final, passed, max_ms, max_kb = Submission.Verdict.AC, 0, 0, 0
        # The cap covers all tests together; a problem with big answers gets room for them.
        output_limit = max(sandbox.DEFAULT_OUTPUT_LIMIT, 2 * sum(len(tc.expected.encode()) for tc in tests))
        results = sandbox.run_tests(lang, src_dir, [tc.input for tc in tests], problem.tl_ms, problem.ml_mb,
                                    output_limit=output_limit)
```

`run_trial` keeps the default limit (it calls `run_tests` positionally, unchanged).

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest apps/submissions/tests.py judge/tests/test_sandbox_results.py -q`
Expected: all pass.

Run: `JUDGE_TESTS=1 JUDGE_WORK_DIR=$PWD/work pytest judge -q`
Expected: all pass (about 2 minutes; Java compiles are the slow part).

- [ ] **Step 6: Commit (only if the user approved commits)**

```bash
git add judge/sandbox.py judge/runner.py judge/tests/test_sandbox.py judge/tests/test_languages.py \
  judge/tests/test_sandbox_results.py apps/submissions/tests.py
git commit -m "fix(judge): run each test as nobody, cap total output as OLE, never pass a cut-short run"
```

---

### Task 5: Solves engine and `Contest.published_at`

**Files:**
- Modify: `apps/contests/models.py` (`Contest`)
- Create: `apps/contests/migrations/0006_contest_published_at.py` (hand-written, full content below)
- Create: `apps/submissions/solves.py`
- Test: `apps/submissions/tests.py`, `apps/contests/tests.py`

**Interfaces:**
- Produces:
  - `Contest.published_at: datetime | None` (set by publish in Task 8).
  - `apps.submissions.solves.refresh_solves(problem_id: int, user_ids: Iterable[int] | None = None) -> None`: make the `UserProblemSolved` rows of the problem follow the eligibility rule for those users (`None` = everyone with a row or an eligible AC), then sync those users' points.
  - `apps.submissions.solves.sync_practice_points(user_ids: Iterable[int] | None = None) -> None`: one UPDATE, `practice_points` = sum of the current `points` of solved problems the user did not author (`None` = every user).
  - Migration function `backfill_published_at(apps, schema_editor)`.

- [ ] **Step 1: Write the failing tests**

Append to `apps/submissions/tests.py`:

```python
# ---- solves & practice points (apps.submissions.solves) -----------------------------

def _solve(user, problem):
    return (UserProblemSolved.objects.filter(user=user, problem=problem)
            .values_list("first_ac_submission_id", flat=True).first())


def test_contest_ac_counts_after_publish_unless_disqualified(problem, python, user):
    from apps.submissions.solves import refresh_solves
    contest = Contest.objects.create(title="Past", start=timezone.now() - timezone.timedelta(hours=3),
                                     end=timezone.now() - timezone.timedelta(hours=2))
    ContestProblem.objects.create(contest=contest, problem=problem, label="A")
    part = Participation.objects.create(user=user, contest=contest)
    contest_ac = Submission.objects.create(user=user, problem=problem, contest=contest, language=python,
                                           source="x", verdict="AC")
    refresh_solves(problem.pk, [user.pk])
    assert _solve(user, problem) is None  # not published yet

    contest.published_at = timezone.now()
    contest.save()
    refresh_solves(problem.pk)
    user.refresh_from_db()
    assert _solve(user, problem) == contest_ac.pk and user.practice_points == 10

    part.disqualified = True
    part.save()
    refresh_solves(problem.pk, [user.pk])
    user.refresh_from_db()
    assert _solve(user, problem) is None and user.practice_points == 0

    practice_ac = Submission.objects.create(user=user, problem=problem, language=python, source="x",
                                            verdict="AC")
    refresh_solves(problem.pk, [user.pk])
    assert _solve(user, problem) == practice_ac.pk  # a practice AC still counts

    part.disqualified = False
    part.save()
    refresh_solves(problem.pk, [user.pk])
    assert _solve(user, problem) == contest_ac.pk  # the earliest eligible AC again


def test_solve_follows_verdict_changes(problem, python, user):
    from apps.submissions.solves import refresh_solves
    first, second = [Submission.objects.create(user=user, problem=problem, language=python, source="x",
                                               verdict="AC") for _ in range(2)]
    refresh_solves(problem.pk, [user.pk])
    assert _solve(user, problem) == first.pk
    Submission.objects.filter(pk=first.pk).update(verdict="WA")  # e.g. a rejudge after a test fix
    refresh_solves(problem.pk, [user.pk])
    assert _solve(user, problem) == second.pk
    Submission.objects.filter(pk=second.pk).update(verdict="WA")
    refresh_solves(problem.pk)  # everyone: also clears rows with no eligible AC left
    user.refresh_from_db()
    assert _solve(user, problem) is None and user.practice_points == 0


def test_points_are_live_and_skip_own_problems(problem, python, user):
    from apps.submissions.solves import refresh_solves, sync_practice_points
    own = Problem.objects.create(slug="own", title="Own", statement_md="x", author=user, points=50)
    for p in (problem, own):
        Submission.objects.create(user=user, problem=p, language=python, source="x", verdict="AC")
        refresh_solves(p.pk, [user.pk])
    user.refresh_from_db()
    assert _solve(user, own) is not None and user.practice_points == 10  # solved, but no points for own
    Problem.objects.filter(pk=problem.pk).update(points=40)
    sync_practice_points()
    user.refresh_from_db()
    assert user.practice_points == 40
```

Append to `apps/contests/tests.py`:

```python
def test_backfill_published_at_marks_contests_the_old_publish_handled(author, python):
    import importlib

    from django.apps import apps

    from apps.submissions.models import UserProblemSolved

    migration = importlib.import_module("apps.contests.migrations.0006_contest_published_at")
    past = {"start": timezone.now() - timezone.timedelta(hours=3), "end": timezone.now() - timezone.timedelta(hours=2)}
    hidden = Problem.objects.create(slug="h", title="H", statement_md="x", author=author, is_public=False)
    public = Problem.objects.create(slug="o", title="O", statement_md="x", author=author, is_public=True)

    def contest(title, problems, **times):
        c = Contest.objects.create(title=title, **(times or past))
        for i, p in enumerate(problems):
            ContestProblem.objects.create(contest=c, problem=p, label="AB"[i])
        return c

    traced = contest("traced", [hidden])  # the old publish left a solve pointing at its AC
    ac = Submission.objects.create(user=author, problem=hidden, contest=traced, language=python, source="x",
                                   verdict="AC")
    UserProblemSolved.objects.create(user=author, problem=hidden, first_ac_submission=ac)
    opened = contest("opened", [public])  # every problem already public
    contest("closed", [hidden])
    contest("empty", [])
    contest("running", [public], start=timezone.now() - timezone.timedelta(hours=1),
            end=timezone.now() + timezone.timedelta(hours=1))

    migration.backfill_published_at(apps, None)

    got = dict(Contest.objects.values_list("title", "published_at"))
    assert got["traced"] == traced.end and got["opened"] == opened.end
    assert got["closed"] is None and got["empty"] is None and got["running"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest apps/submissions/tests.py -k "publish_unless or verdict_changes or live_and_skip" apps/contests/tests.py::test_backfill_published_at_marks_contests_the_old_publish_handled -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'apps.submissions.solves'` / `... 0006_contest_published_at`.

- [ ] **Step 3: Add the field and the migration**

`apps/contests/models.py`, in `Contest` after `rating_applied`:

```python
    rating_applied = models.BooleanField(default=False)
    # Set by staff publishing the ended contest; from then on participants' contest ACs
    # count as practice solves (apps.submissions.solves).
    published_at = models.DateTimeField(null=True, blank=True)
```

Create `apps/contests/migrations/0006_contest_published_at.py`:

```python
from django.db import migrations, models
from django.utils import timezone


def backfill_published_at(apps, schema_editor):
    """Contests the old publish button already processed are published at their end: it
    left solves pointing at their submissions, or opened all of their problems."""
    Contest = apps.get_model("contests", "Contest")
    UserProblemSolved = apps.get_model("submissions", "UserProblemSolved")
    traced = set(UserProblemSolved.objects.values_list("first_ac_submission__contest_id", flat=True))
    for contest in Contest.objects.filter(end__lte=timezone.now(), published_at__isnull=True):
        public = list(contest.contest_problems.values_list("problem__is_public", flat=True))
        if contest.pk in traced or (public and all(public)):
            contest.published_at = contest.end
            contest.save(update_fields=["published_at"])


class Migration(migrations.Migration):

    dependencies = [
        ("contests", "0005_drop_icpc_type"),
        ("submissions", "0003_testresult_mem_kb"),
    ]

    operations = [
        migrations.AddField(
            model_name="contest",
            name="published_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_published_at, migrations.RunPython.noop),
    ]
```

- [ ] **Step 4: Write the solves module**

Create `apps/submissions/solves.py`:

```python
"""Solves and practice points are derived data. A user has solved a problem iff they have
an eligible AC for it: a practice AC, or a contest AC once staff published the ended
contest and the user was not disqualified from it. practice_points is the live price of
the solved problems the user did not author. Everything that can change either goes
through here."""
from collections.abc import Iterable

from django.db import transaction
from django.db.models import Exists, IntegerField, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce

from apps.accounts.models import User
from apps.contests.models import Participation

from .models import Submission, UserProblemSolved


def _eligible_acs(problem_id: int):
    disqualified = Participation.objects.filter(user_id=OuterRef("user_id"), contest_id=OuterRef("contest_id"),
                                                disqualified=True)
    return (Submission.objects
            .filter(Q(contest__isnull=True) | Q(contest__published_at__isnull=False), ~Exists(disqualified),
                    problem_id=problem_id, verdict=Submission.Verdict.AC)
            .order_by("created", "id"))


def refresh_solves(problem_id: int, user_ids: Iterable[int] | None = None) -> None:
    """Make the UserProblemSolved rows of `problem_id` follow the rule for `user_ids`
    (None = everyone with a row or an eligible AC), then resync those users' points."""
    acs, rows = _eligible_acs(problem_id), UserProblemSolved.objects.filter(problem_id=problem_id)
    if user_ids is not None:
        user_ids = set(user_ids)
        acs, rows = acs.filter(user_id__in=user_ids), rows.filter(user_id__in=user_ids)
    wanted = {}  # user -> their earliest eligible AC
    for sub_id, user_id in acs.values_list("id", "user_id"):
        wanted.setdefault(user_id, sub_id)
    # ponytail: no per-user lock; a rejudge or disqualification racing a fresh AC of the
    # same user+problem can leave one stale row until that pair is refreshed again. Lock
    # the user row here if that is ever seen.
    with transaction.atomic():
        current = dict(rows.values_list("user_id", "first_ac_submission_id"))
        users = user_ids if user_ids is not None else current.keys() | wanted.keys()
        for user_id in users:
            want = wanted.get(user_id)
            if want == current.get(user_id):
                continue
            if want is None:
                UserProblemSolved.objects.filter(user_id=user_id, problem_id=problem_id).delete()
            else:
                UserProblemSolved.objects.update_or_create(
                    user_id=user_id, problem_id=problem_id, defaults={"first_ac_submission_id": want})
    sync_practice_points(users)


def sync_practice_points(user_ids: Iterable[int] | None = None) -> None:
    """practice_points = current price of each solved problem the user did not author.
    One UPDATE; None = every user."""
    total = (UserProblemSolved.objects.filter(user_id=OuterRef("pk"))
             .exclude(problem__author_id=OuterRef("pk"))
             .values("user_id").annotate(total=Sum("problem__points")).values("total"))
    users = User.objects.all() if user_ids is None else User.objects.filter(pk__in=list(user_ids))
    # ponytail: rewrites every row of `users`, changed or not; filter to changed rows if
    # the 5-minute sweep over all users ever shows up in DB load.
    users.update(practice_points=Coalesce(Subquery(total, output_field=IntegerField()), 0))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python manage.py makemigrations --check --dry-run`
Expected: `No changes detected`.

Run: `pytest apps/submissions/tests.py apps/contests/tests.py -q`
Expected: all pass.

- [ ] **Step 6: Commit (only if the user approved commits)**

```bash
git add apps/contests/models.py apps/contests/migrations/0006_contest_published_at.py \
  apps/submissions/solves.py apps/submissions/tests.py apps/contests/tests.py
git commit -m "feat: derived solves (eligible AC rule) and live practice points; Contest.published_at"
```

---

### Task 6: The runner finalizes every verdict through `refresh_solves`

**Files:**
- Replace: `judge/runner.py` (full content below)
- Modify: `apps/submissions/models.py` (`UserProblemSolved` docstring)
- Test: `apps/submissions/tests.py`

**Interfaces:**
- Consumes: `refresh_solves(problem_id, [user_id])` (Task 5), `sandbox.DEFAULT_OUTPUT_LIMIT` and `run_tests(..., output_limit=)` (Task 4).
- Produces: after any final verdict of `run_submission` (tests judged, CE, SQL judged, SQL error) the standings cache of the submission's contest is dropped and the user's solve and points are refreshed. `_award_points_if_first_ac` is gone.

- [ ] **Step 1: Write the failing test**

Append after `test_runner_retry_while_running_does_not_duplicate_results` in `apps/submissions/tests.py`:

```python
@pytest.mark.parametrize("compiled, run, verdict", [
    ((False, "error: expected ';'"), [], "CE"),
    ((True, ""), [("4\n", "OK", 10, 1024)], "WA"),
])
def test_rejudged_ac_that_now_fails_loses_its_solve(compiled, run, verdict, problem, python, user):
    """A rejudge resets an AC to PENDING. Whatever the new verdict, CE included, the runner
    must move the solve, the points and the contest standings."""
    from django.core.cache import cache

    from apps.submissions.solves import refresh_solves
    from judge.runner import run_submission

    contest = Contest.objects.create(title="Past", start=timezone.now() - timezone.timedelta(hours=3),
                                     end=timezone.now() - timezone.timedelta(hours=2), published_at=timezone.now())
    s = Submission.objects.create(user=user, problem=problem, contest=contest, language=python, source="x",
                                  verdict="AC")
    refresh_solves(problem.pk, [user.pk])
    user.refresh_from_db()
    assert user.practice_points == 10
    cache.set(f"contest-standings-{contest.pk}", "stale")
    Submission.objects.filter(pk=s.pk).update(verdict="PENDING")  # what the rejudge view does

    with (patch("judge.runner.sandbox.compile", return_value=compiled),
          patch("judge.runner.sandbox.run_tests", return_value=run)):
        run_submission(s.pk)

    s.refresh_from_db()
    user.refresh_from_db()
    assert s.verdict == verdict
    assert not UserProblemSolved.objects.filter(user=user).exists() and user.practice_points == 0
    assert cache.get(f"contest-standings-{contest.pk}") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest apps/submissions/tests.py -k rejudged_ac_that_now_fails -q`
Expected: both cases FAIL (the solve row is still there).

- [ ] **Step 3: Implement**

Replace `judge/runner.py` with:

```python
import os
import shutil
import tempfile

from django.conf import settings
from django.core.cache import cache

from apps.problems.models import Language, Problem
from apps.submissions.models import Submission, TestResult
from apps.submissions.solves import refresh_solves
from judge import sandbox, sql_judge
from judge.compare import outputs_match


TRIAL_OUTPUT_CHARS = 4000


def run_trial(lang_code: str, source: str, inputs: list[str], expected: list[str] | None,
              tl_ms: int, ml_mb: int) -> dict:
    """"Sinab ko'rish": run code on sample tests (expected given) or one custom input
    (expected None). Nothing touches the DB; the result lives only in the RQ job."""
    lang = Language.objects.get(code=lang_code)
    os.makedirs(settings.JUDGE_WORK_DIR, exist_ok=True)
    src_dir = tempfile.mkdtemp(prefix="trial-", dir=settings.JUDGE_WORK_DIR)
    os.chmod(src_dir, 0o777 if lang.compile_cmd else 0o755)
    try:
        source_path = os.path.join(src_dir, sandbox.SOURCE_FILENAME[lang.code])
        with open(source_path, "w") as f:
            f.write(source)
        os.chmod(source_path, 0o644)
        ok, log = sandbox.compile(lang, src_dir)
        if not ok:
            return {"verdict": "CE", "log": log, "cases": [], "total": len(inputs)}
        cases = []
        results = sandbox.run_tests(lang, src_dir, inputs, tl_ms, ml_mb)
        for i, (inp, (out, v, ms, kb)) in enumerate(zip(inputs, results)):
            want = expected[i] if expected is not None else None
            if v == "OK":
                v = "OK" if want is None else ("AC" if outputs_match(want, out) else "WA")
            cases.append({"input": inp[:TRIAL_OUTPUT_CHARS], "output": out[:TRIAL_OUTPUT_CHARS],
                          "expected": want, "verdict": v, "ms": ms, "kb": kb})
        bad = next((c["verdict"] for c in cases if c["verdict"] not in ("OK", "AC")), None)
        return {"verdict": bad or ("OK" if expected is None else "AC"), "log": "", "cases": cases,
                "total": len(inputs)}
    finally:
        shutil.rmtree(src_dir, ignore_errors=True)


def run_submission(submission_id: int) -> None:
    sub = Submission.objects.select_related("problem", "language", "user").get(pk=submission_id)
    if sub.is_terminal:
        return  # idempotent on RQ retry of terminal verdicts
    # Restartable: clear any partial TestResults from a prior RUNNING/PENDING attempt.
    TestResult.objects.filter(submission=sub).delete()
    sub.verdict = Submission.Verdict.RUNNING
    sub.save(update_fields=["verdict"])

    if sub.problem.kind == Problem.Kind.SQL:
        _run_sql_submission(sub)
    else:
        _run_code_submission(sub)
    # Every final verdict, CE included (a rejudge can turn an AC into one), moves the
    # contest standings and this user's solve and practice points.
    _drop_standings_cache(sub)
    refresh_solves(sub.problem_id, [sub.user_id])


def _run_code_submission(sub: Submission) -> None:
    lang = sub.language
    problem = sub.problem
    tests = list(problem.testcases.all())
    os.makedirs(settings.JUDGE_WORK_DIR, exist_ok=True)
    src_dir = tempfile.mkdtemp(prefix=f"sub{sub.pk}-", dir=settings.JUDGE_WORK_DIR)
    # Interpreted langs only need read+exec (0o755). Compiled langs write build
    # output into this dir as container-user `nobody`, so open write (0o777).
    os.chmod(src_dir, 0o777 if lang.compile_cmd else 0o755)
    try:
        source_path = os.path.join(src_dir, sandbox.SOURCE_FILENAME[lang.code])
        with open(source_path, "w") as f:
            f.write(sub.source)
        os.chmod(source_path, 0o644)

        ok, log = sandbox.compile(lang, src_dir)
        if not ok:
            sub.verdict, sub.compile_log, sub.total = Submission.Verdict.CE, log, len(tests)
            sub.save(update_fields=["verdict", "compile_log", "total"])
            return

        final, passed, max_ms, max_kb = Submission.Verdict.AC, 0, 0, 0
        # The cap covers all tests together; a problem with big answers gets room for them.
        output_limit = max(sandbox.DEFAULT_OUTPUT_LIMIT, 2 * sum(len(tc.expected.encode()) for tc in tests))
        results = sandbox.run_tests(lang, src_dir, [tc.input for tc in tests], problem.tl_ms, problem.ml_mb,
                                    output_limit=output_limit)
        rows = []
        for tc, (out, v, ms, kb) in zip(tests, results):
            max_ms, max_kb = max(max_ms, ms), max(max_kb, kb)
            if v == "OK":
                v = "AC" if outputs_match(tc.expected, out) else "WA"
            rows.append(TestResult(submission=sub, testcase=tc, verdict=v, exec_ms=ms, mem_kb=kb, stdout_excerpt=out[:1000]))
            if v != "AC":
                final = v
                break
            passed += 1
        TestResult.objects.bulk_create(rows)

        sub.verdict, sub.passed, sub.total, sub.exec_ms, sub.mem_kb = final, passed, len(tests), max_ms, max_kb
        sub.save(update_fields=["verdict", "passed", "total", "exec_ms", "mem_kb"])
    finally:
        shutil.rmtree(src_dir, ignore_errors=True)


def _run_sql_submission(sub: Submission) -> None:
    problem = sub.problem
    try:
        dataset = problem.sql_dataset
    except Problem.sql_dataset.RelatedObjectDoesNotExist:
        sub.verdict, sub.total = Submission.Verdict.RE, 1
        sub.save(update_fields=["verdict", "total"])
        return

    try:
        status, rows = sql_judge.run_query(dataset.schema_sql, dataset.seed_sql, sub.source, problem.tl_ms)
    except sql_judge.SQLJudgeError:
        sub.verdict, sub.total = Submission.Verdict.RE, 1
        sub.save(update_fields=["verdict", "total"])
        return

    if status == "TLE":
        final = Submission.Verdict.TLE
    elif status == "RE":
        final = Submission.Verdict.RE
    else:
        final = Submission.Verdict.AC if sql_judge.rows_match(rows, dataset.expected_result) else Submission.Verdict.WA

    sub.verdict = final
    sub.passed = 1 if final == Submission.Verdict.AC else 0
    sub.total = 1
    sub.save(update_fields=["verdict", "passed", "total"])


def _drop_standings_cache(sub: Submission) -> None:
    """Standings are cached 30s; a fresh verdict should show up right away."""
    if sub.contest_id is not None:
        cache.delete(f"contest-standings-{sub.contest_id}")
```

In `apps/submissions/models.py`, replace the `UserProblemSolved` docstring:

```python
class UserProblemSolved(models.Model):
    """Derived: the user's earliest eligible AC for the problem. Maintained by
    apps.submissions.solves.refresh_solves; practice points are computed from these rows."""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest apps/submissions/tests.py -q`
Expected: all pass, including the old runner tests (`test_runner_first_ac_awards_practice_points`, `test_runner_second_ac_does_not_award_points_again`, `test_runner_contest_ac_awards_no_practice_points`, `test_runner_sql_ac`).

- [ ] **Step 5: Commit (only if the user approved commits)**

```bash
git add judge/runner.py apps/submissions/models.py apps/submissions/tests.py
git commit -m "fix(judge): every final verdict, CE included, refreshes standings, solve and points"
```

---

### Task 7: Live points in the sweep, a full rebuild command, read-only points

**Files:**
- Modify: `apps/problems/management/commands/recalc_points.py`
- Replace: `apps/accounts/management/commands/recalc_practice_points.py`
- Modify: `apps/problems/management/commands/seed_demo.py`
- Modify: `apps/moderation/forms.py` (`UserForm`), `templates/moderation/user_form.html`
- Modify: `README.md`
- Test: `apps/problems/tests.py`, `apps/accounts/tests.py`, `apps/moderation/tests.py`

**Interfaces:**
- Consumes: `refresh_solves`, `sync_practice_points` (Task 5).
- Produces: `recalc_points` (scheduler, every 5 min) ends with `sync_practice_points()`; `recalc_practice_points` rebuilds every solve.

- [ ] **Step 1: Write the failing tests**

Append to `apps/problems/tests.py` after `test_recalc_points_command_updates_from_real_submissions`:

```python
@pytest.mark.django_db
def test_recalc_points_makes_practice_points_live():
    from django.core.management import call_command

    from apps.submissions.models import Submission
    from apps.submissions.solves import refresh_solves

    author = User.objects.create_user("teacher", password="x", role="teacher")
    ali = User.objects.create_user("ali", password="x")
    p = Problem.objects.create(slug="p", title="P", statement_md="x", author=author, points=999,
                               difficulty=Problem.Difficulty.EASY, status=Problem.Status.APPROVED)
    python = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    Submission.objects.create(user=ali, problem=p, language=python, source="x", verdict="AC")
    refresh_solves(p.pk)
    ali.refresh_from_db()
    assert ali.practice_points == 999

    call_command("recalc_points")

    p.refresh_from_db()
    ali.refresh_from_db()
    assert p.points != 999 and ali.practice_points == p.points
```

Append to `apps/accounts/tests.py` after `test_recalc_practice_points_sums_current_points_of_solved_problems`:

```python
@pytest.mark.django_db
def test_recalc_practice_points_drops_solves_the_rule_no_longer_allows():
    from django.core.management import call_command
    from django.utils import timezone

    from apps.contests.models import Contest, Participation

    author = User.objects.create_user("teacher", password="x")
    cheat = User.objects.create_user("cheat", password="x", practice_points=70)
    python = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    p = Problem.objects.create(slug="p", title="P", statement_md="x", author=author, points=70)
    c = Contest.objects.create(title="C", start=timezone.now() - timezone.timedelta(hours=3),
                               end=timezone.now() - timezone.timedelta(hours=2), published_at=timezone.now())
    Participation.objects.create(user=cheat, contest=c, disqualified=True)
    sub = Submission.objects.create(user=cheat, problem=p, contest=c, language=python, source="x", verdict="AC")
    UserProblemSolved.objects.create(user=cheat, problem=p, first_ac_submission=sub)  # left by the old publish

    call_command("recalc_practice_points")

    cheat.refresh_from_db()
    assert not UserProblemSolved.objects.filter(user=cheat).exists() and cheat.practice_points == 0
```

In `apps/moderation/tests.py`, `test_staff_can_edit_user_but_not_demote_self`: change `"practice_points": "0"` to `"practice_points": "999"` in `base`, and extend the first assertion so the posted value is ignored:

```python
    student.refresh_from_db()
    assert student.is_staff is True and student.rating == 1500 and student.practice_points == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest apps/problems/tests.py::test_recalc_points_makes_practice_points_live apps/accounts/tests.py::test_recalc_practice_points_drops_solves_the_rule_no_longer_allows apps/moderation/tests.py::test_staff_can_edit_user_but_not_demote_self -q`
Expected: 3 FAIL (points stay 999; the cheat keeps the row and 70 points; the form saves 999).

- [ ] **Step 3: Implement**

`apps/problems/management/commands/recalc_points.py`:

```python
from django.core.management.base import BaseCommand
from django.db.models import Count

from apps.problems.models import Problem
from apps.problems.scoring import compute_points
from apps.submissions.solves import sync_practice_points


class Command(BaseCommand):
    help = ("Recompute each approved problem's points from its difficulty band and solve "
            "rate (solvers / distinct attempters), then every user's practice_points from "
            "the new prices. Idempotent, cron-friendly.")

    def handle(self, *args, **opts):
        problems = Problem.objects.filter(status=Problem.Status.APPROVED).annotate(
            attempts=Count("submissions__user", distinct=True),
            solvers=Count("userproblemsolved", distinct=True),
        )
        updated = 0
        for p in problems:
            points = compute_points(p.difficulty, p.solvers, p.attempts)
            if points != p.points:
                p.points = points
                p.save(update_fields=["points"])
                updated += 1
        sync_practice_points()  # totals follow the new prices: practice points are live
        self.stdout.write(self.style.SUCCESS(f"{updated} problem(s) repointed"))
```

Replace `apps/accounts/management/commands/recalc_practice_points.py` with:

```python
from django.core.management.base import BaseCommand

from apps.submissions.models import Submission, UserProblemSolved
from apps.submissions.solves import refresh_solves, sync_practice_points


class Command(BaseCommand):
    help = ("Rebuild every solve from the eligibility rule (apps.submissions.solves), then "
            "every user's practice_points. Idempotent. Run once after deploying the honest-results "
            "change; the recalc_points sweep keeps points live after that.")

    def handle(self, *args, **opts):
        problem_ids = (set(Submission.objects.filter(verdict=Submission.Verdict.AC).values_list("problem_id", flat=True))
                       | set(UserProblemSolved.objects.values_list("problem_id", flat=True)))
        for problem_id in problem_ids:
            refresh_solves(problem_id)
        sync_practice_points()  # users with no solve left drop to 0
        self.stdout.write(self.style.SUCCESS(f"{len(problem_ids)} problem(s) resynced"))
```

`apps/problems/management/commands/seed_demo.py`: add the import next to the other app imports:

```python
from apps.submissions.solves import sync_practice_points
```

and call it after the `with transaction.atomic():` block, right before the final `self.stdout.write(...)`:

```python
        sync_practice_points()  # demo totals follow the demo solves, like real ones

        self.stdout.write(self.style.SUCCESS(
```

`apps/moderation/forms.py`, `UserForm`: remove `"practice_points"` from `fields` and its widget (points are derived; a manual value would be overwritten within 5 minutes):

```python
class UserForm(ModelForm):
    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name", "role", "is_staff", "is_active",
                  "rating", "school", "location"]
        widgets = {
            **{k: forms.TextInput(attrs=_CA_INPUT) for k in ["username", "first_name", "last_name", "school", "location"]},
            "email": forms.EmailInput(attrs=_CA_INPUT),
            "role": forms.Select(attrs={"class": "ca-select"}),
            "rating": forms.NumberInput(attrs=_CA_INPUT),
        }
```

`templates/moderation/user_form.html`, replace the `practice_points` field line:

```html
      <div><label class="ca-label" for="{{ form.practice_points.id_for_label }}">Amaliyot ball</label>{{ form.practice_points }}{{ form.practice_points.errors }}</div>
```

with a read-only value:

```html
      <div><p class="ca-label">Amaliyot ball</p><p class="tabular py-2 text-sm">{{ form.instance.practice_points }} <span class="text-mute">· yechilgan masalalardan hisoblanadi</span></p></div>
```

`README.md`, after the "Similarity is checked on demand ..." block (before "Publishing contest problems ..."), add:

```markdown
Solves and practice points are derived (`apps/submissions/solves.py`): a solve is
the user's earliest eligible AC (practice, or contest after the contest is
published and the user is not disqualified), and `practice_points` is the
current price of the solved problems, excluding problems the user authored.
The scheduler's `recalc_points` reprices problems and resyncs every total every
5 minutes. After deploying this change, rebuild every solve once:

    docker compose exec web python manage.py recalc_practice_points
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest apps/problems/tests.py apps/accounts/tests.py apps/moderation/tests.py -q`
Expected: all pass.

- [ ] **Step 5: Commit (only if the user approved commits)**

```bash
git add apps/problems/management/commands/recalc_points.py apps/accounts/management/commands/recalc_practice_points.py \
  apps/problems/management/commands/seed_demo.py apps/moderation/forms.py templates/moderation/user_form.html \
  README.md apps/problems/tests.py apps/accounts/tests.py apps/moderation/tests.py
git commit -m "feat: practice points follow live prices; recalc_practice_points rebuilds solves"
```

---

### Task 8: Publish and disqualify move solves through the rule

**Files:**
- Modify: `apps/moderation/views.py` (`contest_publish`, imports)
- Modify: `templates/moderation/contests.html` (publish button condition)
- Modify: `apps/contests/views.py` (`disqualify`, imports)
- Modify: `README.md`
- Test: `apps/moderation/tests.py`, `apps/contests/tests.py`

**Interfaces:**
- Consumes: `Contest.published_at`, `refresh_solves` (Task 5).
- Produces: publish sets `published_at` once and refreshes every contest problem; disqualify refreshes the user's solves on each contest problem when the contest is published.

- [ ] **Step 1: Write the failing tests**

In `apps/moderation/tests.py`, replace `test_contest_publish_opens_problems_and_grants_points` with:

```python
@pytest.mark.django_db
def test_contest_publish_opens_problems_and_grants_points(client):
    from django.utils import timezone

    from apps.contests.models import Contest, ContestProblem, Participation
    from apps.problems.models import Language
    from apps.submissions.models import Submission, UserProblemSolved

    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    ali = User.objects.create_user("ali", password="x")
    cheat = User.objects.create_user("cheat", password="x")
    p = Problem.objects.create(slug="p", title="P", statement_md="x", author=staff, is_public=False, points=70)
    c = Contest.objects.create(title="C", start=timezone.now() - timezone.timedelta(hours=3),
                               end=timezone.now() - timezone.timedelta(hours=1))
    ContestProblem.objects.create(contest=c, problem=p, label="A")
    Participation.objects.create(user=cheat, contest=c, disqualified=True)
    lang = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    for v in ("WA", "AC", "AC"):
        Submission.objects.create(user=ali, problem=p, contest=c, language=lang, source="x", verdict=v)
    Submission.objects.create(user=cheat, problem=p, contest=c, language=lang, source="x", verdict="AC")

    client.force_login(staff)
    assert client.post(reverse("moderation:contest_publish", args=[c.pk])).status_code == 302
    p.refresh_from_db(); ali.refresh_from_db(); cheat.refresh_from_db(); c.refresh_from_db()
    assert p.is_public is True and c.published_at is not None
    assert ali.practice_points == 70  # once, not per AC
    assert cheat.practice_points == 0 and not UserProblemSolved.objects.filter(user=cheat).exists()
    published_at = c.published_at
    client.post(reverse("moderation:contest_publish", args=[c.pk]))  # publishing again changes nothing
    ali.refresh_from_db(); c.refresh_from_db()
    assert ali.practice_points == 70 and c.published_at == published_at


@pytest.mark.django_db
def test_publish_button_shows_until_published(client):
    from django.utils import timezone

    from apps.contests.models import Contest, ContestProblem

    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    public = Problem.objects.create(slug="p", title="P", statement_md="x", author=staff, is_public=True)
    c = Contest.objects.create(title="C", start=timezone.now() - timezone.timedelta(hours=3),
                               end=timezone.now() - timezone.timedelta(hours=1))
    ContestProblem.objects.create(contest=c, problem=public, label="A")
    client.force_login(staff)
    publish_url = reverse("moderation:contest_publish", args=[c.pk]).encode()
    assert publish_url in client.get(reverse("moderation:contests")).content  # all problems public, still unpublished
    client.post(reverse("moderation:contest_publish", args=[c.pk]))
    assert publish_url not in client.get(reverse("moderation:contests")).content
```

Append to `apps/contests/tests.py`:

```python
@pytest.mark.django_db
def test_disqualifying_after_publish_takes_contest_solves_back(client, problem_a, python):
    staff = User.objects.create_user("boss", password="x", is_staff=True)
    ali = User.objects.create_user("ali", password="x")
    problem_a.points = 50
    problem_a.save()
    c = Contest.objects.create(title="Past", start=timezone.now() - timezone.timedelta(hours=3),
                               end=timezone.now() - timezone.timedelta(hours=2))
    ContestProblem.objects.create(contest=c, problem=problem_a, label="A")
    Participation.objects.create(user=ali, contest=c)
    Submission.objects.create(user=ali, problem=problem_a, contest=c, language=python, source="x", verdict="AC")
    client.force_login(staff)
    client.post(reverse("moderation:contest_publish", args=[c.pk]))
    ali.refresh_from_db()
    assert ali.practice_points == 50

    url = reverse("contests:disqualify", args=[c.pk, ali.pk])
    client.post(url, {"reason": "copy"})
    ali.refresh_from_db()
    assert ali.practice_points == 0 and not ali.userproblemsolved_set.exists()
    client.post(url)  # re-qualify
    ali.refresh_from_db()
    assert ali.practice_points == 50 and ali.userproblemsolved_set.count() == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest apps/moderation/tests.py -k "publish" apps/contests/tests.py::test_disqualifying_after_publish_takes_contest_solves_back -q`
Expected: 3 FAIL (the cheat gets 70 and `published_at` is None; the button is hidden; disqualifying keeps 50 points).

- [ ] **Step 3: Implement publish**

`apps/moderation/views.py` imports. Change only these lines: `F` is no longer used (`Count, F, Q` becomes `Count, Q`), and `timezone` and `refresh_solves` are new:

```python
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
```

```python
from apps.submissions.models import Submission, UserProblemSolved
from apps.submissions.solves import refresh_solves
```

Replace `contest_publish`:

```python
@staff_required
@require_POST
def contest_publish(request, pk):
    """After a contest: make its problems public and let participants' contest ACs count
    as practice solves. Disqualified participants get nothing (apps.submissions.solves).
    Publishing again keeps the first time and re-applies the rule."""
    contest = get_object_or_404(Contest, pk=pk)
    if not contest.has_ended:
        messages.error(request, "Musobaqa hali tugamagan.")
        return redirect("moderation:contests")
    with transaction.atomic():
        Problem.objects.filter(contests=contest).update(is_public=True)
        if contest.published_at is None:
            contest.published_at = timezone.now()
            contest.save(update_fields=["published_at"])
        for problem_id in contest.contest_problems.values_list("problem_id", flat=True):
            refresh_solves(problem_id)
    granted = UserProblemSolved.objects.filter(first_ac_submission__contest=contest).count()
    messages.success(request, f"Masalalar ochildi; {granted} ta yechim amaliyot balliga o'tkazildi.")
    return redirect("moderation:contests")
```

`templates/moderation/contests.html`, the publish form (lines 29-30): it shows until the contest is published, and its confirm no longer counts hidden problems, since that count can now be 0:

```html
      {% if c.has_ended and not c.published_at %}
      <form method="post" action="{% url 'moderation:contest_publish' c.pk %}" onsubmit="return confirm('Masalalar ochiladi va ishtirokchilarning AC yechimlari amaliyot balliga o‘tadi. Davom etasizmi?');">{% csrf_token %}
```

(was `{% if c.has_ended and c.n_hidden %}` and a confirm starting `{{ c.n_hidden }} ta yashirin masala ochiladi va ...`; the button and the `· N yashirin` count in the row meta stay.)

- [ ] **Step 4: Implement disqualify**

`apps/contests/views.py`, add the import:

```python
from apps.accounts.decorators import staff_required
from apps.submissions.solves import refresh_solves
```

Replace `disqualify`:

```python
@staff_required
@require_POST
def disqualify(request, pk, user_id):
    """Toggle a participant's disqualification; standings cache is dropped so the
    table reorders immediately. After publish the user's contest solves follow the
    toggle (a disqualified participant's contest ACs don't count)."""
    p = get_object_or_404(Participation.objects.select_related("contest"), contest_id=pk, user_id=user_id)
    p.disqualified = not p.disqualified
    p.disqualified_reason = request.POST.get("reason", "").strip()[:200] if p.disqualified else ""
    p.save(update_fields=["disqualified", "disqualified_reason"])
    if p.contest.published_at is not None:
        for problem_id in p.contest.contest_problems.values_list("problem_id", flat=True):
            refresh_solves(problem_id, [p.user_id])
    cache.delete(f"contest-standings-{pk}")
    if request.POST.get("back") == "report":
        return redirect("integrity:contest_report", pk)
    return redirect("contests:standings", pk=pk)
```

`README.md`, replace the paragraph starting "Publishing contest problems (making them public + awarding practice points)" (4 lines) with:

```markdown
Publishing a contest is a manual staff action after it ends: Boshqaruv →
Musobaqalar → Masalalarni ochish. It makes the problems public and lets
participants' contest ACs count as practice solves. Disqualified participants'
contest ACs never count, and disqualifying after publish takes those solves
back. The old `close_ended_contests` command still exists but is intentionally
not scheduled; it only opens problems and does not publish.
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest apps/moderation/tests.py apps/contests/tests.py -q`
Expected: all pass.

- [ ] **Step 6: Commit (only if the user approved commits)**

```bash
git add apps/moderation/views.py templates/moderation/contests.html apps/contests/views.py README.md \
  apps/moderation/tests.py apps/contests/tests.py
git commit -m "fix: publish and disqualification move solves by the rule; DQ'd users get no points"
```

---

### Task 9: Fresh problems for rated contests, a warning for unrated ones

**Files:**
- Modify: `apps/contests/services.py` (add `reuse_reason`)
- Modify: `apps/moderation/forms.py` (`BaseContestProblemFormSet`, `ContestProblemFormSet`)
- Modify: `apps/moderation/views.py` (`contest_edit`, import)
- Modify: `templates/base.html` (message level classes, `.ca-alert-warn`)
- Test: `apps/moderation/tests.py`

**Interfaces:**
- Produces: `apps.contests.services.reuse_reason(problem: Problem, contest: Contest) -> str` — the Uzbek reason participants may already know the problem, `""` when fresh. Messages render with `ca-alert-bad` (error) and `ca-alert-warn` (warning); Task 10 relies on `ca-alert-bad`.

- [ ] **Step 1: Write the failing tests**

Append to `apps/moderation/tests.py`:

```python
def _contest_data(problem, rated=True):
    """POST body for moderation:contest_new with one problem row."""
    data = {"title": "Round", "description_md": "", "start": "2030-01-01T10:00", "end": "2030-01-01T12:00",
            "allowed_ip_prefix": "", "require_group": "",
            "cp-TOTAL_FORMS": "1", "cp-INITIAL_FORMS": "0", "cp-MIN_NUM_FORMS": "0", "cp-MAX_NUM_FORMS": "1000",
            "cp-0-label": "A", "cp-0-problem": str(problem.pk), "cp-0-points": "100", "cp-0-order": "0"}
    if rated:
        data["is_rated"] = "on"
    return data


def _contest_edit_data(contest):
    """POST body that saves `contest` and its problem rows unchanged."""
    from django.utils import timezone

    fmt = "%Y-%m-%dT%H:%M"
    rows = list(contest.contest_problems.all())
    data = {"title": contest.title, "description_md": "", "allowed_ip_prefix": "", "require_group": "",
            "start": timezone.localtime(contest.start).strftime(fmt),
            "end": timezone.localtime(contest.end).strftime(fmt),
            "cp-TOTAL_FORMS": str(len(rows)), "cp-INITIAL_FORMS": str(len(rows)),
            "cp-MIN_NUM_FORMS": "0", "cp-MAX_NUM_FORMS": "1000"}
    if contest.is_rated:
        data["is_rated"] = "on"
    for i, cp in enumerate(rows):
        data |= {f"cp-{i}-id": str(cp.pk), f"cp-{i}-label": cp.label, f"cp-{i}-problem": str(cp.problem_id),
                 f"cp-{i}-points": str(cp.points), f"cp-{i}-order": str(cp.order)}
    return data


@pytest.mark.django_db
def test_rated_contest_takes_only_fresh_problems(client):
    from django.utils import timezone

    from apps.contests.models import Contest, ContestProblem

    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    client.force_login(staff)
    public = Problem.objects.create(slug="pub", title="Pub", statement_md="x", author=staff, is_public=True)
    r = client.post(reverse("moderation:contest_new"), _contest_data(public))
    assert r.status_code == 200 and "Ochiq masala" in r.content.decode()

    used = Problem.objects.create(slug="used", title="Used", statement_md="x", author=staff, is_public=False)
    old = Contest.objects.create(title="Old", start=timezone.now() + timezone.timedelta(days=1),
                                 end=timezone.now() + timezone.timedelta(days=2))
    ContestProblem.objects.create(contest=old, problem=used, label="A")
    r = client.post(reverse("moderation:contest_new"), _contest_data(used))
    assert r.status_code == 200 and "Bu masala boshqa musobaqada ishlatilgan" in r.content.decode()
    assert not Contest.objects.filter(title="Round").exists()


@pytest.mark.django_db
def test_unrated_contest_saves_reused_problem_with_warning(client):
    from apps.contests.models import Contest

    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    client.force_login(staff)
    public = Problem.objects.create(slug="pub", title="Pub", statement_md="x", author=staff, is_public=True)
    r = client.post(reverse("moderation:contest_new"), _contest_data(public, rated=False), follow=True)
    html = r.content.decode()
    assert Contest.objects.filter(title="Round").exists()
    assert 'class="ca-alert ca-alert-warn"' in html and "A: ochiq yoki boshqa musobaqada ishlatilgan" in html


@pytest.mark.django_db
def test_contest_edit_is_not_blocked_by_its_own_or_ended_problems(client):
    from django.utils import timezone

    from apps.contests.models import Contest, ContestProblem

    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    client.force_login(staff)
    now = timezone.now()
    running = Contest.objects.create(title="Live", is_rated=True, start=now - timezone.timedelta(hours=1),
                                     end=now + timezone.timedelta(hours=1))
    ContestProblem.objects.create(contest=running, label="A", problem=Problem.objects.create(
        slug="fresh", title="Fresh", statement_md="x", author=staff, is_public=False))
    ended = Contest.objects.create(title="Past", is_rated=True, start=now - timezone.timedelta(hours=3),
                                   end=now - timezone.timedelta(hours=2))
    ContestProblem.objects.create(contest=ended, label="A", problem=Problem.objects.create(
        slug="opened", title="Opened", statement_md="x", author=staff, is_public=True))
    for c in (running, ended):
        r = client.post(reverse("moderation:contest_edit", args=[c.pk]), _contest_edit_data(c))
        assert r.status_code == 302, r.content.decode()[:2000]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest apps/moderation/tests.py -k "fresh_problems or reused_problem or not_blocked" -q`
Expected: `test_rated_contest_takes_only_fresh_problems` and `test_unrated_contest_saves_reused_problem_with_warning` FAIL; `test_contest_edit_is_not_blocked_by_its_own_or_ended_problems` passes already (it guards the change).

- [ ] **Step 3: Implement**

`apps/contests/services.py`, append:

```python
def reuse_reason(problem, contest) -> str:
    """Why participants of `contest` may already know `problem`; "" when it is fresh."""
    if problem.is_public:
        return "Ochiq masala — reytingli musobaqaga faqat yashirin, yangi masala qo‘shiladi."
    if ContestProblem.objects.filter(problem=problem).exclude(contest_id=contest.pk).exists():
        return "Bu masala boshqa musobaqada ishlatilgan."
    return ""
```

`apps/moderation/forms.py`: add the import and a formset base above `ContestProblemFormSet`, then pass it in:

```python
from apps.contests.models import Contest, ContestProblem
from apps.contests.services import reuse_reason
```

```python
class BaseContestProblemFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        contest = self.instance  # contest_edit validates ContestForm first, which copies the POSTed values here
        if any(self.errors) or not contest.is_rated or contest.end is None or contest.end <= timezone.now():
            return  # an ended contest is skipped: publishing makes its problems public
        for form in self.forms:
            problem = form.cleaned_data.get("problem")
            if problem is None or form.cleaned_data.get("DELETE"):
                continue
            reason = reuse_reason(problem, contest)
            if reason:
                form.add_error("problem", reason)


ContestProblemFormSet = inlineformset_factory(
    Contest, ContestProblem, formset=BaseContestProblemFormSet,
    fields=["label", "problem", "points", "order"], extra=1, can_delete=True,
    widgets={
        "label": forms.TextInput(attrs={"class": "ca-input w-16 text-center", "maxlength": 2}),
        "problem": forms.Select(attrs={"class": "ca-select"}),
        "points": forms.NumberInput(attrs={"class": "ca-input w-24"}),
        "order": forms.NumberInput(attrs={"class": "ca-input w-20"}),
    },
)
```

`apps/moderation/views.py`: add the import

```python
from apps.contests.models import Contest
from apps.contests.services import reuse_reason
```

and in `contest_edit`, after `messages.success(request, "Musobaqa saqlandi.")`:

```python
        messages.success(request, "Musobaqa saqlandi.")
        if not contest.is_rated and not contest.has_ended:
            known = [cp.label for cp in contest.contest_problems.select_related("problem")
                     if reuse_reason(cp.problem, contest)]
            if known:
                messages.warning(request, f"{', '.join(known)}: ochiq yoki boshqa musobaqada ishlatilgan — "
                                          "ishtirokchilar bu masalalarni oldindan bilishi mumkin.")
        return redirect("moderation:contests")
```

`templates/base.html`: after the `.ca-alert-bad { ... }` rule add

```css
    .ca-alert-warn { box-shadow: inset 4px 0 0 rgb(var(--ca-warn-rgb)), var(--ca-shadow); }
```

and give each message its level class (the `{% for m in messages %}` loop):

```html
      <div class="ca-alert{% if m.level_tag == 'error' %} ca-alert-bad{% elif m.level_tag == 'warning' %} ca-alert-warn{% endif %}">{{ m }}</div>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest apps/moderation/tests.py -q`
Expected: all pass (including the existing `test_staff_can_create_contest_with_problems`, whose problem is hidden and unused).

- [ ] **Step 5: Commit (only if the user approved commits)**

```bash
git add apps/contests/services.py apps/moderation/forms.py apps/moderation/views.py templates/base.html apps/moderation/tests.py
git commit -m "feat: rated contests accept only fresh problems; unrated ones warn; styled message levels"
```

---

### Task 10: Delete guards and `CASCADE` on the solve's submission

**Files:**
- Modify: `apps/submissions/models.py` (`UserProblemSolved.first_ac_submission`)
- Create: `apps/submissions/migrations/0005_userproblemsolved_cascade.py` (generated)
- Modify: `apps/moderation/views.py` (`problem_delete`, `contest_delete`)
- Test: `apps/moderation/tests.py`

**Interfaces:**
- Consumes: `ca-alert-bad` message class (Task 9).
- Produces: deleting a problem is refused when it is in any contest or has submissions from anyone but its author; deleting a contest is refused when it has submissions.

- [ ] **Step 1: Write the failing tests**

Append to `apps/moderation/tests.py`:

```python
@pytest.mark.django_db
def test_problem_delete_refuses_when_others_depend_on_it(client):
    from django.utils import timezone

    from apps.contests.models import Contest, ContestProblem
    from apps.problems.models import Language
    from apps.submissions.models import Submission, UserProblemSolved

    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    ali = User.objects.create_user("ali", password="x")
    lang = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    in_contest = Problem.objects.create(slug="c", title="C", statement_md="x", author=staff)
    c = Contest.objects.create(title="R", start=timezone.now() + timezone.timedelta(days=1),
                               end=timezone.now() + timezone.timedelta(days=2))
    ContestProblem.objects.create(contest=c, problem=in_contest, label="A")
    tried = Problem.objects.create(slug="t", title="T", statement_md="x", author=staff)
    Submission.objects.create(user=ali, problem=tried, language=lang, source="x", verdict="WA")
    own = Problem.objects.create(slug="m", title="M", statement_md="x", author=staff)
    own_ac = Submission.objects.create(user=staff, problem=own, language=lang, source="x", verdict="AC")
    UserProblemSolved.objects.create(user=staff, problem=own, first_ac_submission=own_ac)

    client.force_login(staff)
    for p in (in_contest, tried):
        r = client.post(reverse("moderation:problem_delete", args=[p.pk]), follow=True)
        assert 'class="ca-alert ca-alert-bad"' in r.content.decode()
    assert Problem.objects.filter(pk__in=[in_contest.pk, tried.pk]).count() == 2
    client.post(reverse("moderation:problem_delete", args=[own.pk]))  # only the author's solve: no ProtectedError
    assert not Problem.objects.filter(pk=own.pk).exists()


@pytest.mark.django_db
def test_contest_delete_refuses_when_it_has_submissions(client):
    from django.utils import timezone

    from apps.contests.models import Contest
    from apps.problems.models import Language
    from apps.submissions.models import Submission

    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    p = Problem.objects.create(slug="p", title="P", statement_md="x", author=staff)
    lang = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    times = {"start": timezone.now() - timezone.timedelta(hours=3), "end": timezone.now() - timezone.timedelta(hours=2)}
    used = Contest.objects.create(title="Used", **times)
    Submission.objects.create(user=staff, problem=p, contest=used, language=lang, source="x", verdict="AC")
    empty = Contest.objects.create(title="Empty", **times)
    client.force_login(staff)
    client.post(reverse("moderation:contest_delete", args=[used.pk]))
    client.post(reverse("moderation:contest_delete", args=[empty.pk]))
    assert list(Contest.objects.values_list("title", flat=True)) == ["Used"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest apps/moderation/tests.py -k "delete_refuses" -q`
Expected: 2 FAIL (the problems are deleted, then `ProtectedError`; the used contest is deleted).

- [ ] **Step 3: Implement**

`apps/submissions/models.py`:

```python
    first_ac_submission = models.ForeignKey(Submission, on_delete=models.CASCADE)
```

Run: `python manage.py makemigrations submissions -n userproblemsolved_cascade`
Expected: creates `apps/submissions/migrations/0005_userproblemsolved_cascade.py` with one `AlterField` on `userproblemsolved.first_ac_submission`.

`apps/moderation/views.py`, replace `problem_delete`:

```python
@staff_required
@require_POST
def problem_delete(request, pk):
    problem = get_object_or_404(Problem, pk=pk)
    # A contest's record or other people's work hangs on it; hiding keeps both.
    if problem.contests.exists() or problem.submissions.exclude(user_id=problem.author_id).exists():
        messages.error(request, f"«{problem.title}» musobaqada ishlatilgan yoki unga boshqalar urinish yuborgan — "
                                "o‘chirib bo‘lmaydi, yashirib qo‘ying.")
        return redirect("moderation:problems")
    problem.delete()
    messages.success(request, f"«{problem.title}» o'chirildi.")
    return redirect("moderation:problems")
```

Replace `contest_delete`:

```python
@staff_required
@require_POST
def contest_delete(request, pk):
    contest = get_object_or_404(Contest, pk=pk)
    # Submission.contest is SET_NULL: deleting would turn its ACs, unpublished and
    # disqualified ones included, into practice ACs that count as solves.
    if contest.submissions.exists():
        messages.error(request, f"«{contest.title}» musobaqasida urinishlar bor — o‘chirib bo‘lmaydi.")
        return redirect("moderation:contests")
    contest.delete()
    messages.success(request, f"«{contest.title}» o'chirildi.")
    return redirect("moderation:contests")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest apps/moderation/tests.py apps/submissions/tests.py -q`
Expected: all pass.

- [ ] **Step 5: Commit (only if the user approved commits)**

```bash
git add apps/submissions/models.py apps/submissions/migrations/0005_userproblemsolved_cascade.py \
  apps/moderation/views.py apps/moderation/tests.py
git commit -m "fix: guard problem and contest deletes; a deleted solve's AC no longer crashes delete"
```

---

### Task 11: Rejudge a problem

**Files:**
- Modify: `apps/moderation/views.py` (`problems` list, new `problem_rejudge`, imports)
- Modify: `apps/moderation/urls.py`
- Modify: `templates/moderation/problems.html`
- Modify: `config/settings/base.py` (`RQ_QUEUES`), `docker-compose.yml`, `docker-compose.prod.yml`, `README.md`
- Test: `apps/moderation/tests.py`

**Interfaces:**
- Consumes: `judge.runner.run_submission` (Task 6 finalizes solves, points, standings), `Submission.TERMINAL` (Task 3).
- Produces: URL `moderation:problem_rejudge` → `POST /moderation/problems/<pk>/rejudge/`, staff only; problems list items carry `n_subs` (finished submissions).

- [ ] **Step 1: Write the failing tests**

Append to `apps/moderation/tests.py`:

```python
@pytest.mark.django_db
def test_rejudge_requeues_finished_submissions_once(client, django_capture_on_commit_callbacks):
    from apps.problems.models import Language
    from apps.submissions.models import Submission, TestResult

    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    ali = User.objects.create_user("ali", password="x")
    p = Problem.objects.create(slug="p", title="P", statement_md="x", author=staff)
    tc = p.testcases.create(input="1\n", expected="1\n")
    lang = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    ac, wa, running = [Submission.objects.create(user=ali, problem=p, language=lang, source="x", verdict=v,
                                                 passed=1, total=1) for v in ("AC", "WA", "RUNNING")]
    TestResult.objects.create(submission=ac, testcase=tc, verdict="AC")
    client.force_login(staff)
    assert "2 ta urinish qayta tekshiriladi" in client.get(reverse("moderation:problems")).content.decode()

    with patch("apps.moderation.views.django_rq.get_queue") as get_queue:
        for _ in range(2):  # a double click: the second finds nothing left to reset
            with django_capture_on_commit_callbacks(execute=True):
                assert client.post(reverse("moderation:problem_rejudge", args=[p.pk])).status_code == 302
    get_queue.assert_called_with("rejudge")
    assert [c.args[1] for c in get_queue.return_value.enqueue.call_args_list] == [ac.pk, wa.pk]
    ac.refresh_from_db()
    running.refresh_from_db()
    assert (ac.verdict, ac.passed, ac.total) == ("PENDING", 0, 0) and not ac.results.exists()
    assert running.verdict == "RUNNING"  # in flight: left alone


@pytest.mark.django_db
def test_rejudge_warns_about_applied_rating_and_needs_staff(client):
    from django.utils import timezone

    from apps.contests.models import Contest, ContestProblem
    from apps.problems.models import Language
    from apps.submissions.models import Submission

    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    ali = User.objects.create_user("ali", password="x")
    p = Problem.objects.create(slug="p", title="P", statement_md="x", author=staff)
    c = Contest.objects.create(title="Final", is_rated=True, rating_applied=True,
                               start=timezone.now() - timezone.timedelta(hours=3),
                               end=timezone.now() - timezone.timedelta(hours=2))
    ContestProblem.objects.create(contest=c, problem=p, label="A")
    lang = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    s = Submission.objects.create(user=ali, problem=p, contest=c, language=lang, source="x", verdict="AC")

    client.force_login(ali)
    assert client.post(reverse("moderation:problem_rejudge", args=[p.pk])).status_code == 302
    s.refresh_from_db()
    assert s.verdict == "AC"  # not staff: nothing happened

    client.force_login(staff)
    with patch("apps.moderation.views.django_rq.get_queue"):
        r = client.post(reverse("moderation:problem_rejudge", args=[p.pk]), follow=True)
    assert "Final: reyting allaqachon hisoblangan" in r.content.decode()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest apps/moderation/tests.py -k rejudge -q`
Expected: 2 FAIL (`NoReverseMatch: 'problem_rejudge'`).

- [ ] **Step 3: Implement the view and the list count**

`apps/moderation/views.py` imports. Change only these lines; every other import stays, including `from django.utils import timezone` from Task 8. Add `import django_rq` as the first line, and:

```python
from django.db.models import Count, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
```

(was `from django.db.models import Count, Q` after Task 8)

```python
from apps.submissions.models import Submission, TestResult, UserProblemSolved
from apps.submissions.solves import refresh_solves
from judge.runner import run_submission
```

(`TestResult` and the `judge.runner` line are new)

Replace the queryset line of `problems`:

```python
    # A subquery, not a second Count join: two joins would multiply tests by submissions.
    finished = (Submission.objects.filter(problem=OuterRef("pk"), verdict__in=Submission.TERMINAL)
                .order_by().values("problem").annotate(n=Count("pk")).values("n"))
    qs = (Problem.objects.select_related("author")
          .annotate(n_tests=Count("testcases"), n_subs=Coalesce(Subquery(finished), 0)).order_by("-pk"))
```

Add after `problem_delete`:

```python
@staff_required
@require_POST
def problem_rejudge(request, pk):
    """Judge every finished submission of the problem again, e.g. after its tests were
    fixed. In-flight ones are left alone. The runner then moves verdicts, solves, points
    and standings like for a fresh submission."""
    problem = get_object_or_404(Problem, pk=pk)
    with transaction.atomic():
        # The row locks make a concurrent double click find nothing left to reset.
        ids = list(Submission.objects.filter(problem=problem, verdict__in=Submission.TERMINAL)
                   .select_for_update().order_by("created", "id").values_list("pk", flat=True))
        # Reset by id, not by verdict again: a submission that finished after the SELECT is
        # not locked, and resetting it without queueing it would leave it PENDING for good.
        # ponytail: one IN list; chunk it past ~65k submissions of one problem (Postgres
        # takes at most 65535 parameters per statement).
        TestResult.objects.filter(submission_id__in=ids).delete()
        Submission.objects.filter(pk__in=ids).update(verdict=Submission.Verdict.PENDING, passed=0, total=0,
                                                     exec_ms=0, mem_kb=0, compile_log="")

        def enqueue():
            queue = django_rq.get_queue("rejudge")
            for submission_id in ids:
                queue.enqueue(run_submission, submission_id)
        transaction.on_commit(enqueue)
    messages.success(request, f"{len(ids)} ta urinish qayta tekshirishga yuborildi.")
    applied = list(problem.contests.filter(rating_applied=True).values_list("title", flat=True))
    if applied:
        messages.warning(request, f"{', '.join(applied)}: reyting allaqachon hisoblangan — "
                                  "qayta tekshiruvdan keyin ham o‘zgarmaydi.")
    return redirect("moderation:problems")
```

`apps/moderation/urls.py`, after the `problem_delete` path:

```python
    path("problems/<int:pk>/rejudge/", views.problem_rejudge, name="problem_rejudge"),
```

`templates/moderation/problems.html`, after the "Urinishlar" (`history`) link:

```html
      <form method="post" action="{% url 'moderation:problem_rejudge' p.pk %}" onsubmit="return confirm('«{{ p.title|escapejs }}»: {{ p.n_subs }} ta urinish qayta tekshiriladi. Davom etasizmi?');">{% csrf_token %}
        <button class="ca-btn ca-btn-ghost !px-2 !py-1.5" title="Qayta tekshirish" aria-label="Qayta tekshirish: {{ p.title }}"{% if not p.n_subs %} disabled{% endif %}><i data-lucide="refresh-cw" class="lu" aria-hidden="true"></i></button>
      </form>
```

- [ ] **Step 4: Add the queue and the workers**

`config/settings/base.py`, the comment above `RQ_QUEUES` and the dict:

```python
# "run" = "Sinab ko'rish" trial runs, "rejudge" = staff rejudges; workers listen
# `default run rejudge`, so real submissions go first and a rejudge never delays them.
RQ_QUEUES = {"default": {"URL": REDIS_URL, "DEFAULT_TIMEOUT": 600},
             "run": {"URL": REDIS_URL, "DEFAULT_TIMEOUT": 120},
             "rejudge": {"URL": REDIS_URL, "DEFAULT_TIMEOUT": 600}}
```

`docker-compose.yml`, worker:

```yaml
    command: python manage.py rqworker default run rejudge
```

`docker-compose.prod.yml`, worker:

```yaml
    command: python manage.py rqworker-pool default run rejudge --num-workers ${JUDGE_WORKERS:-4}
```

`README.md`: in "Dev (host)" change `python manage.py rqworker default run` to `python manage.py rqworker default run rejudge`, and after the publishing paragraph (Task 8) add:

```markdown
After fixing a problem's tests, staff rejudge it from Boshqaruv → Masalalar
(the ↻ button): its finished submissions go back to the low-priority `rejudge`
RQ queue, and verdicts, solves, points and standings follow the new results.
Ratings already applied do not change.
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest apps/moderation/tests.py -q && python manage.py check`
Expected: all pass; `System check identified no issues (0 silenced).`

- [ ] **Step 6: Commit (only if the user approved commits)**

```bash
git add apps/moderation/views.py apps/moderation/urls.py templates/moderation/problems.html \
  config/settings/base.py docker-compose.yml docker-compose.prod.yml README.md apps/moderation/tests.py
git commit -m "feat: staff rejudge of a problem on a low-priority rejudge queue"
```

---

### Task 12: Rating board lists rated users only

**Files:**
- Modify: `apps/accounts/views.py` (`rating`, `profile`)
- Modify: `templates/accounts/profile.html` (rating stat block, rating rank block)
- Test: `apps/accounts/tests.py`

**Interfaces:**
- Produces: profile context gains `total_rated: int`; `rating_rank` is `None` for users without a rated contest.

- [ ] **Step 1: Write the failing tests**

In `apps/accounts/tests.py`, add a helper after the imports:

```python
def _rated(*users):
    """A finished rated contest the given users took part in (rating_after set)."""
    from django.utils import timezone

    from apps.contests.models import Contest, Participation

    c = Contest.objects.create(title="R", is_rated=True, rating_applied=True,
                               start=timezone.now() - timezone.timedelta(hours=3),
                               end=timezone.now() - timezone.timedelta(hours=2))
    for u in users:
        Participation.objects.create(user=u, contest=c, rating_before=1200, rating_after=u.rating)
```

Replace `test_rating_lists_users_by_rating_desc`:

```python
@pytest.mark.django_db
def test_rating_lists_users_by_rating_desc(client):
    low = User.objects.create_user("low", password="x", rating=1400)
    high = User.objects.create_user("high", password="x", rating=1800)
    User.objects.create_user("fresh", password="x", rating=2000)  # never rated: not on the board
    _rated(low, high)
    r = client.get(reverse("rating"))
    assert r.status_code == 200
    assert [u.username for u in r.context["users"]] == ["high", "low"] and r.context["total"] == 2
```

Replace `test_blocked_users_get_no_place_on_boards`:

```python
@pytest.mark.django_db
def test_blocked_users_get_no_place_on_boards(client):
    ok = User.objects.create_user("ok", password="x", rating=1400, practice_points=5)
    banned = User.objects.create_user("banned", password="x", rating=1800, practice_points=50, is_active=False)
    _rated(ok, banned)
    for name in ("top", "rating"):
        r = client.get(reverse(name))
        assert [u.username for u in r.context["users"]] == ["ok"] and r.context["total"] == 1

    r = client.get(reverse("profile", args=["ok"]))
    assert r.context["rating_rank"] == 1 and r.context["points_rank"] == 1
    assert r.context["total_users"] == 1 and r.context["total_rated"] == 1
    r = client.get(reverse("profile", args=["banned"]))
    assert r.context["rating_rank"] is None and r.context["points_rank"] is None
```

Append:

```python
@pytest.mark.django_db
def test_unrated_profile_says_reytingsiz(client):
    vet = User.objects.create_user("vet", password="x", rating=1500)
    _rated(vet)
    User.objects.create_user("new", password="x", rating=1700)  # staff-set rating, no rated contest
    r = client.get(reverse("profile", args=["new"]))
    assert r.context["rating_rank"] is None and r.context["total_rated"] == 1
    assert "Reytingsiz" in r.content.decode()
    r = client.get(reverse("profile", args=["vet"]))
    assert r.context["rating_rank"] == 1 and "Reytingsiz" not in r.content.decode()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest apps/accounts/tests.py -k "rating_lists or blocked_users or reytingsiz" -q`
Expected: 3 FAIL ("fresh" is listed; no `total_rated` in context).

- [ ] **Step 3: Implement**

`apps/accounts/views.py`, `rating`:

```python
def rating(request):
    # Only users who finished a rated contest; a default 1200 says nothing about anyone.
    qs = (User.objects.filter(is_active=True)
          .annotate(contest_count=Count("participations", filter=Q(participations__rating_after__isnull=False)))
          .filter(contest_count__gt=0).order_by("-rating", "username"))
```

(the rest of the function is unchanged).

In `profile`, replace the rank block:

```python
    # blocked (inactive) users hold no place on the boards and push nobody down
    ranked = User.objects.filter(is_active=True)
    total_users = ranked.count()
    rating_rank = points_rank = None
    if profile_user.is_active:
        rating_rank = ranked.filter(rating__gt=profile_user.rating).count() + 1
        points_rank = ranked.filter(practice_points__gt=profile_user.practice_points).count() + 1
```

with:

```python
    # blocked (inactive) users hold no place on the boards and push nobody down; the
    # rating rank only counts users who finished a rated contest, like /rating
    ranked = User.objects.filter(is_active=True)
    rated = ranked.filter(participations__rating_after__isnull=False).distinct()
    total_users, total_rated = ranked.count(), rated.count()
    rating_rank = points_rank = None
    if profile_user.is_active:
        points_rank = ranked.filter(practice_points__gt=profile_user.practice_points).count() + 1
        if rating_history:
            rating_rank = rated.filter(rating__gt=profile_user.rating).count() + 1
```

and add `"total_rated": total_rated,` to the render context next to `"total_users": total_users,`.

`templates/accounts/profile.html`, replace the "Reyting" and "Reyting o‘rni" stat blocks:

```html
    <div class="px-6 py-4">
      <p class="ca-stat-label">Reyting</p>
      {% if rating_history %}
      <p class="ca-stat-value mt-1">{{ profile_user.rating }}</p>
      <p class="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1"><span class="ca-tier" style="--tier: {{ tier_color }}">{{ tier }}</span><span class="text-xs text-mute">{{ rating_history|length }} ta musobaqa</span></p>
      {% else %}
      <p class="ca-stat-value mt-1">—</p>
      <p class="mt-1.5"><span class="ca-tier" style="--tier: #6B7280">Reytingsiz</span></p>
      {% endif %}
    </div>
    <div class="px-6 py-4">
      <p class="ca-stat-label">Reyting o‘rni</p>
      <p class="ca-stat-value mt-1">{% if rating_rank %}#{{ rating_rank }}{% else %}—{% endif %}</p>
      <p class="mt-1 text-xs text-mute">{{ total_rated }} ishtirokchidan</p>
    </div>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest apps/accounts/tests.py -q`
Expected: all pass.

- [ ] **Step 5: Commit (only if the user approved commits)**

```bash
git add apps/accounts/views.py templates/accounts/profile.html apps/accounts/tests.py
git commit -m "fix: rating board and rating rank count only users with a rated contest"
```

---

### Task 13: Rate limits on the integrity endpoints

**Files:**
- Create: `apps/submissions/ratelimit.py`
- Modify: `apps/submissions/views.py` (drop `_rate_limited`, use the shared one)
- Modify: `apps/integrity/views.py` (`event`, `snapshot`, constants, import)
- Test: `apps/integrity/tests.py`

**Interfaces:**
- Produces: `apps.submissions.ratelimit.rate_limited(user_id: int, kind: str, limit: int) -> bool` (fixed 60-second window, cache key `f"{kind}-rl:{user_id}"`, same keys as before for `submit` and `trial`); `apps.integrity.views.EVENT_RATE_MAX = 60`, `SNAPSHOT_RATE_MAX = 20`.

- [ ] **Step 1: Write the failing test**

Append to `apps/integrity/tests.py`:

```python
def test_event_and_snapshot_are_rate_limited(client, flag_contest, flag_problem, flag_python):
    from django.core.cache import cache

    from .models import CodeSnapshot
    from .views import EVENT_RATE_MAX, SNAPSHOT_RATE_MAX

    cache.clear()  # counters live in the cache, and user pks repeat across tests
    ali = User.objects.create_user("rl", password="x")
    Participation.objects.create(user=ali, contest=flag_contest)
    client.force_login(ali)
    event = {"contest_id": flag_contest.pk, "kind": "blur"}
    for _ in range(EVENT_RATE_MAX):
        assert client.post(reverse("integrity:event"), event).status_code == 200
    assert client.post(reverse("integrity:event"), event).status_code == 429
    assert FocusEvent.objects.count() == EVENT_RATE_MAX

    snap = {"contest_id": flag_contest.pk, "problem_id": flag_problem.pk, "language": "python"}
    for i in range(SNAPSHOT_RATE_MAX):
        assert client.post(reverse("integrity:snapshot"), snap | {"source": f"v{i}"}).status_code == 200
    assert client.post(reverse("integrity:snapshot"), snap | {"source": "late"}).status_code == 429
    assert not CodeSnapshot.objects.filter(source="late").exists()
    cache.clear()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest apps/integrity/tests.py::test_event_and_snapshot_are_rate_limited -q`
Expected: FAIL (`ImportError: cannot import name 'EVENT_RATE_MAX'`).

- [ ] **Step 3: Implement**

Create `apps/submissions/ratelimit.py`:

```python
"""Per-user request counters in the Django cache."""
from django.core.cache import cache

WINDOW_S = 60


def rate_limited(user_id: int, kind: str, limit: int) -> bool:
    """True once `user_id` has made `limit` requests of `kind` in the current window."""
    # ponytail: fixed window, not sliding — a burst can land 2x limit across a window
    # boundary. Good enough to stop a spam script; swap for a sliding/token-bucket
    # counter if that boundary burst becomes a problem.
    key = f"{kind}-rl:{user_id}"
    count = cache.get(key)
    if count is None:
        cache.set(key, 1, timeout=WINDOW_S)
        return False
    if count >= limit:
        return True
    cache.incr(key)
    return False
```

`apps/submissions/views.py`: delete the `from django.core.cache import cache` import, the `RATE_LIMIT_WINDOW_S` constant and the whole `_rate_limited` function; import the shared one and keep `RATE_LIMIT_MAX`/`TRIAL_RATE_MAX` (a test imports `RATE_LIMIT_MAX` from here):

```python
from .models import Submission, UserProblemSolved
from .ratelimit import rate_limited

MAX_SOURCE = 64 * 1024
RATE_LIMIT_MAX = 10       # submissions per minute
TRIAL_RATE_MAX = 20       # "Sinab ko'rish" runs per minute: cheaper than a submit, but still a container
MAX_TRIAL_INPUT = 64 * 1024
```

In `submit`:

```python
    if rate_limited(request.user.id, "submit", RATE_LIMIT_MAX):
        return HttpResponse("too many submissions, slow down", status=429)
```

In `trial`:

```python
    if rate_limited(request.user.id, "trial", TRIAL_RATE_MAX):
        return JsonResponse({"error": "Juda tez-tez — bir daqiqadan keyin urinib ko‘ring"}, status=429)
```

`apps/integrity/views.py`: add the import

```python
from apps.submissions.models import Submission
from apps.submissions.ratelimit import rate_limited
```

and the limits next to `_MAX_SNAPSHOT_CHARS`:

```python
_MAX_AWAY_MS = 6 * 3600 * 1000
_MAX_SNAPSHOT_CHARS = 64_000
# Per user per minute. The client sends a snapshot every 10 s plus one per submit or page
# exit; a flood of events leaves a visible trail before it hits the limit.
EVENT_RATE_MAX = 60
SNAPSHOT_RATE_MAX = 20
```

First lines of `event` and `snapshot` (before any validation or DB work):

```python
def event(request):
    if rate_limited(request.user.id, "event", EVENT_RATE_MAX):
        return JsonResponse({"error": "too many requests"}, status=429)
    kind = request.POST.get("kind")
```

```python
def snapshot(request):
    if rate_limited(request.user.id, "snapshot", SNAPSHOT_RATE_MAX):
        return JsonResponse({"error": "too many requests"}, status=429)
    contest, problem, error = _participant_contest(request)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest apps/integrity/tests.py apps/submissions/tests.py -q`
Expected: all pass.

- [ ] **Step 5: Commit (only if the user approved commits)**

```bash
git add apps/submissions/ratelimit.py apps/submissions/views.py apps/integrity/views.py apps/integrity/tests.py
git commit -m "fix: rate-limit integrity event and snapshot endpoints (60 and 20 per minute)"
```

---

### Task 14: Final verification

**Files:** none new; review only.

- [ ] **Step 1: Full unit suite**

Run: `pytest -q`
Expected: all pass (baseline before this plan: 173 passed, 10 skipped; now about 199 passed, 18 skipped, the skips being the Docker tests). pytest builds its test database by applying every migration, so this also checks that the four new migrations apply.

- [ ] **Step 2: Docker judge suite**

Run: `JUDGE_TESTS=1 JUDGE_WORK_DIR=$PWD/work pytest judge -q`
Expected: all pass.

- [ ] **Step 3: Project checks**

Run: `python manage.py makemigrations --check --dry-run && python manage.py check`
Expected: `No changes detected` and `System check identified no issues (0 silenced).`

Run: `uvx ruff check apps judge config`
Expected: no findings on lines this plan added or changed. The project has no ruff config; list older findings for the user instead of fixing them here.

- [ ] **Step 4: Review the diff**

Run: `git status && git diff --stat`
Expected: only the files in the File map, the four migrations, `apps/submissions/solves.py`, `apps/submissions/ratelimit.py`, `judge/tests/test_sandbox_results.py`, the test files named in the tasks, and the plan/spec docs. Read `git diff` once end to end for leftovers (debug prints, unrelated edits).

- [ ] **Step 5: Deploy notes for the user**

Tell the user, after deploy (`migrate` runs on `web` start):
1. Run once: `docker compose -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py recalc_practice_points`.
2. Every total moves to the live value, and authors lose the points for their own problems.
3. The worker must be recreated so it listens on `rejudge` (`up -d --build` does it).

- [ ] **Step 6: Commit (only if the user approved commits)**

Nothing new to commit if the per-task commits were made; otherwise leave the working tree for the user.
