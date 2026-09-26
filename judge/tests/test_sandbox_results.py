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
