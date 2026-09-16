import os
import shutil
import tempfile

from django.conf import settings
from django.db import transaction

from apps.submissions.models import Submission, TestResult, UserProblemSolved
from judge import sandbox
from judge.compare import outputs_match


def run_submission(submission_id: int) -> None:
    sub = Submission.objects.select_related("problem", "language", "user").get(pk=submission_id)
    if sub.is_terminal:
        return  # idempotent on RQ retry
    sub.verdict = Submission.Verdict.RUNNING
    sub.save(update_fields=["verdict"])

    lang = sub.language
    problem = sub.problem
    tests = list(problem.testcases.all())
    os.makedirs(settings.JUDGE_WORK_DIR, exist_ok=True)
    src_dir = tempfile.mkdtemp(prefix=f"sub{sub.pk}-", dir=settings.JUDGE_WORK_DIR)
    # 0o777: compiled languages (C++/Java) write their build output into this
    # dir as container-user `nobody`, who needs write, not just read+exec.
    os.chmod(src_dir, 0o777)
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

        final, passed, max_ms = Submission.Verdict.AC, 0, 0
        for tc in tests:
            out, v, ms = sandbox.run_test(lang, src_dir, tc.input, problem.tl_ms, problem.ml_mb)
            max_ms = max(max_ms, ms)
            if v == "OK":
                v = "AC" if outputs_match(tc.expected, out) else "WA"
            TestResult.objects.create(submission=sub, testcase=tc, verdict=v, exec_ms=ms,
                                      stdout_excerpt=out[:1000])
            if v != "AC":
                final = v
                break
            passed += 1

        sub.verdict, sub.passed, sub.total, sub.exec_ms = final, passed, len(tests), max_ms
        sub.save(update_fields=["verdict", "passed", "total", "exec_ms"])

        if final == Submission.Verdict.AC:
            _award_points_if_first_ac(sub)
    finally:
        shutil.rmtree(src_dir, ignore_errors=True)


def _award_points_if_first_ac(submission: Submission) -> None:
    """First AC per (user, problem) awards problem.points once — spec §2 step 5."""
    with transaction.atomic():
        _, created = UserProblemSolved.objects.get_or_create(
            user=submission.user, problem=submission.problem,
            defaults={"first_ac_submission": submission},
        )
        if created:
            user = submission.user
            user.practice_points += submission.problem.points
            user.save(update_fields=["practice_points"])
