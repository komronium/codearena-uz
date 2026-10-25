# PyPy has no Alpine package and its official image is Debian, so busybox (which the test runner
# uses for `time -f %M` and `timeout`) is added and put first on nobody's PATH.
FROM pypy:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends busybox \
    && ln -s /bin/busybox /usr/local/bin/timeout \
    && rm -rf /var/lib/apt/lists/*
# The sandbox is read-only and runs as nobody, so .pyc files cannot be written at run time and every
# test would recompile the standard library (~80 ms and ~50 MB extra per start): compile it here.
RUN pypy3 -m compileall -q /opt/pypy/lib
WORKDIR /work
