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
    out, verdict, ms, _ = run_tests(Lang, d, ["1 2\n"], 1000, 64)[0]
    assert verdict == "OK" and out == "3\n" and ms < 1000


def test_re():
    d = _src("print(1/0)")
    _, verdict, _, _ = run_tests(Lang, d, [""], 1000, 64)[0]
    assert verdict == "RE"


def test_tle():
    d = _src("while True: pass")
    _, verdict, ms, _ = run_tests(Lang, d, [""], 500, 64)[0]
    assert verdict == "TLE" and ms >= 500


def test_mle():
    d = _src("x=[0]*(10**8)")
    _, verdict, _, _ = run_tests(Lang, d, [""], 3000, 32)[0]
    assert verdict == "MLE"


def test_no_network():
    d = _src("import socket; socket.create_connection(('1.1.1.1',53),timeout=1)")
    _, verdict, _, _ = run_tests(Lang, d, [""], 3000, 64)[0]
    assert verdict == "RE"


def test_many_tests_one_container_stops_at_first_failure():
    d = _src("n=int(input())\nprint(n*2) if n < 3 else 1/0")
    res = run_tests(Lang, d, ["1\n", "2\n", "3\n", "4\n"], 1000, 64)
    assert [(o, v) for o, v, _, _ in res] == [("2\n", "OK"), ("4\n", "OK"), ("", "RE")]


def test_reports_peak_memory_per_test():
    d = _src("n=int(input())\nx=bytearray(n*1024*1024)\nprint(len(x))")
    (_, v1, _, small), (_, v2, _, big) = run_tests(Lang, d, ["1\n", "40\n"], 2000, 128)
    assert v1 == v2 == "OK" and small < 20_000 and big >= 40 * 1024


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
