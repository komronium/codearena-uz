"""Docker sandbox. One container per compile, one container per submission for
the tests (a runner script loops over them inside), since `docker run` costs
~0.5-1s and a problem has dozens of tests. Interface stable so it can be
swapped for `isolate` later."""
import os
import subprocess
import time
import uuid

SOURCE_FILENAME = {"python": "main.py", "cpp": "main.cpp", "java": "Main.java", "node": "main.js"}

_BASE = ["docker", "run", "--rm", "--network", "none", "--cpus", "1", "--pids-limit", "64",
         "--read-only", "--tmpfs", "/tmp", "-i", "--user", "nobody", "-w", "/work"]

# Runs inside the (alpine/busybox) image. Stops at the first non-zero exit so a
# TLE solution doesn't burn TL x tests; WA is decided on the host and keeps going.
# /proc/uptime gives 10ms resolution without needing `date +%N`.
_RUNNER = """#!/bin/sh
for f in /work/tests/*.in; do
  n=$(basename "$f" .in)
  s=$(cut -d' ' -f1 /proc/uptime)
  timeout -s KILL {tl} {run} < "$f" > "/out/$n.out" 2>/dev/null
  rc=$?
  e=$(cut -d' ' -f1 /proc/uptime)
  echo "$n $rc $s $e" >> /out/result
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
    cmd = _BASE + ["--name", name, "--memory", "512m", "--memory-swap", "512m",
                   "-v", f"{src_dir}:/work", lang.docker_image, "sh", "-c", lang.compile_cmd]
    p, _, timed_out = _run(cmd, "", 30, name)
    if timed_out:
        return False, "compile timeout"
    return p.returncode == 0, (p.stderr or "")[:4000]


def run_tests(lang, src_dir: str, inputs: list[str], tl_ms: int, ml_mb: int) -> list[tuple[str, str, int]]:
    """Run every input in one container. Returns (stdout, verdict, ms) per test in
    order, verdict in {OK, TLE, MLE, RE}; stops after the first non-OK test, so
    the list may be shorter than `inputs`."""
    tests_dir, out_dir = os.path.join(src_dir, "tests"), os.path.join(src_dir, "out")
    os.makedirs(tests_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    os.chmod(out_dir, 0o777)  # container user `nobody` writes here
    for i, inp in enumerate(inputs):
        with open(os.path.join(tests_dir, f"{i:04d}.in"), "w") as f:
            f.write(inp)
    tl_s = tl_ms * lang.tl_multiplier / 1000
    runner = os.path.join(src_dir, "run.sh")
    with open(runner, "w") as f:
        f.write(_RUNNER.format(tl=f"{tl_s + 0.3:.2f}", run=lang.run_cmd))
    for path in (tests_dir, runner, *(os.path.join(tests_dir, p) for p in os.listdir(tests_dir))):
        os.chmod(path, 0o755)

    name = f"ca-r-{uuid.uuid4().hex[:12]}"
    cmd = _BASE + ["--name", name, "--memory", f"{ml_mb}m", "--memory-swap", f"{ml_mb}m",
                   "-v", f"{src_dir}:/work:ro", "-v", f"{out_dir}:/out", lang.docker_image, "sh", "/work/run.sh"]
    # Outer guard only: per-test TL is enforced by `timeout` inside the container.
    _run(cmd, "", len(inputs) * (tl_s + 0.5) + 10, name)

    results = []
    try:
        with open(os.path.join(out_dir, "result")) as f:
            lines = f.read().split("\n")
    except FileNotFoundError:
        return [("", "RE", 0)]  # container never got going: treat as runtime error
    for line in lines:
        if not line.strip():
            continue
        n, rc, s, e = line.split()
        ms = int((float(e) - float(s)) * 1000)
        try:
            with open(os.path.join(out_dir, f"{n}.out"), errors="replace") as f:
                out = f.read()
        except FileNotFoundError:
            out = ""
        rc = int(rc)
        if rc == 0:
            results.append((out, "OK", ms))
        elif rc == 137 and ms >= tl_ms * lang.tl_multiplier:
            results.append(("", "TLE", ms))
        elif rc == 137:
            results.append(("", "MLE", ms))
        else:
            results.append((out, "RE", ms))
    return results
