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
