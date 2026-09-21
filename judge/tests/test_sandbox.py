import os
import tempfile

import pytest

from judge.sandbox import SOURCE_FILENAME, compile, run_tests

pytestmark = pytest.mark.skipif(os.environ.get("JUDGE_TESTS") != "1", reason="needs docker; set JUDGE_TESTS=1")


class Lang:  # duck-typed stand-in for problems.Language
    code = "python"
    docker_image = "codearena-judge-python"
    compile_cmd = ""
    run_cmd = "python3 main.py"
    tl_multiplier = 1.0


def _src(code: str) -> str:
    # mkdtemp defaults to 0700; the container runs as `nobody`, so the dir and
    # file need to be world-readable/executable or every run fails with "not
    # found" before it ever gets to running the code. judge.runner (Task 5)
    # must do the same when it writes a submission's source file.
    d = tempfile.mkdtemp(dir=os.environ.get("JUDGE_WORK_DIR"))
    os.chmod(d, 0o755)
    path = os.path.join(d, SOURCE_FILENAME["python"])
    with open(path, "w") as f:
        f.write(code)
    os.chmod(path, 0o644)
    return d


def test_ok():
    d = _src("a,b=map(int,input().split());print(a+b)")
    ok, log = compile(Lang, d)
    assert ok and log == ""
    out, verdict, ms = run_tests(Lang, d, ["1 2\n"], 1000, 64)[0]
    assert verdict == "OK" and out == "3\n" and ms < 1000


def test_re():
    d = _src("print(1/0)")
    _, verdict, _ = run_tests(Lang, d, [""], 1000, 64)[0]
    assert verdict == "RE"


def test_tle():
    d = _src("while True: pass")
    _, verdict, ms = run_tests(Lang, d, [""], 500, 64)[0]
    assert verdict == "TLE" and ms >= 500


def test_mle():
    d = _src("x=[0]*(10**8)")
    _, verdict, _ = run_tests(Lang, d, [""], 3000, 32)[0]
    assert verdict == "MLE"


def test_no_network():
    d = _src("import socket; socket.create_connection(('1.1.1.1',53),timeout=1)")
    _, verdict, _ = run_tests(Lang, d, [""], 3000, 64)[0]
    assert verdict == "RE"


def test_many_tests_one_container_stops_at_first_failure():
    d = _src("n=int(input())\nprint(n*2) if n < 3 else 1/0")
    res = run_tests(Lang, d, ["1\n", "2\n", "3\n", "4\n"], 1000, 64)
    assert [(o, v) for o, v, _ in res] == [("2\n", "OK"), ("4\n", "OK"), ("", "RE")]
