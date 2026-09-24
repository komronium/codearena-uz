import os
import shutil
import tempfile

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import F

from apps.accounts.models import User
from apps.problems.models import Language, Problem
from apps.submissions.models import Submission, TestResult, UserProblemSolved
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
        return

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
        results = sandbox.run_tests(lang, src_dir, [tc.input for tc in tests], problem.tl_ms, problem.ml_mb)
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
        _drop_standings_cache(sub)

        if final == Submission.Verdict.AC and sub.contest_id is None:
            _award_points_if_first_ac(sub)
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
    _drop_standings_cache(sub)

    if final == Submission.Verdict.AC and sub.contest_id is None:
        _award_points_if_first_ac(sub)


def _drop_standings_cache(sub: Submission) -> None:
    """Standings are cached 30s; a fresh verdict should show up right away."""
    if sub.contest_id is not None:
        cache.delete(f"contest-standings-{sub.contest_id}")


def _award_points_if_first_ac(submission: Submission) -> None:
    """First AC per (user, problem) awards problem.points once — spec §2 step 5."""
    with transaction.atomic():
        _, created = UserProblemSolved.objects.get_or_create(
            user=submission.user, problem=submission.problem,
            defaults={"first_ac_submission": submission},
        )
        if created:
            User.objects.filter(pk=submission.user_id).update(
                practice_points=F("practice_points") + submission.problem.points,
            )
