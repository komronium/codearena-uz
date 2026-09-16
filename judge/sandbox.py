"""Docker-per-test sandbox. Interface stable so it can be swapped for `isolate` later."""
import subprocess
import time
import uuid

SOURCE_FILENAME = {"python": "main.py", "cpp": "main.cpp", "java": "Main.java", "node": "main.js"}

_BASE = ["docker", "run", "--rm", "--network", "none", "--cpus", "1", "--pids-limit", "64",
         "--read-only", "--tmpfs", "/tmp", "-i", "--user", "nobody", "-w", "/work"]


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


def run_test(lang, src_dir: str, input: str, tl_ms: int, ml_mb: int) -> tuple[str, str, int]:
    name = f"ca-r-{uuid.uuid4().hex[:12]}"
    tl_s = tl_ms * lang.tl_multiplier / 1000
    cmd = _BASE + ["--name", name, "--memory", f"{ml_mb}m", "--memory-swap", f"{ml_mb}m",
                   "-v", f"{src_dir}:/work:ro", lang.docker_image, "sh", "-c", lang.run_cmd]
    # ponytail: wall-clock timeout includes ~100-300ms docker startup; subtract nothing, add 0.5s grace.
    p, ms, timed_out = _run(cmd, input, tl_s + 0.5, name)
    if timed_out or ms > tl_ms * lang.tl_multiplier + 300:
        return "", "TLE", ms
    if p.returncode == 137:
        return "", "MLE", ms
    if p.returncode != 0:
        return p.stdout, "RE", ms
    return p.stdout, "OK", ms
