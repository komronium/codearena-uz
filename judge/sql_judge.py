"""Judge path for Problem.Kind.SQL. Runs the student's query with Python's
stdlib sqlite3 directly in the worker process — no Docker image needed, since
sqlite3.Connection.set_authorizer() gives us the same read-only sandboxing a
container would, without the per-submission container startup cost.

Security: the authorizer denies everything except SELECT/read/function calls
(no INSERT/UPDATE/DELETE/DROP/ATTACH/PRAGMA/...), and sqlite3.Cursor.execute()
already refuses to run more than one statement per call. set_progress_handler
enforces the wall-clock time limit by aborting the VM mid-query.
"""
import sqlite3
import time

MAX_ROWS = 5000

_ALLOWED_ACTIONS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}


class SQLJudgeError(Exception):
    """Problem's own schema/seed SQL failed to load — an authoring bug, not the student's fault."""


def _authorizer(action, *_):
    return sqlite3.SQLITE_OK if action in _ALLOWED_ACTIONS else sqlite3.SQLITE_DENY


def run_query(schema_sql: str, seed_sql: str, query: str, tl_ms: int):
    """Returns (verdict, rows) where verdict is one of "OK", "TLE", "RE"."""
    conn = sqlite3.connect(":memory:")
    try:
        try:
            conn.executescript(schema_sql)
            conn.executescript(seed_sql)
            conn.commit()
        except sqlite3.Error as exc:
            raise SQLJudgeError(str(exc)) from exc

        start = time.monotonic()
        deadline_s = tl_ms / 1000

        def _progress():
            return 1 if time.monotonic() - start > deadline_s else 0

        conn.set_progress_handler(_progress, 1000)
        conn.set_authorizer(_authorizer)
        try:
            cur = conn.execute(query)
            rows = cur.fetchmany(MAX_ROWS + 1)
        except sqlite3.OperationalError as exc:
            if "interrupted" in str(exc):
                return "TLE", []
            return "RE", []
        except sqlite3.Error:
            return "RE", []

        if len(rows) > MAX_ROWS:
            return "RE", []
        return "OK", rows
    finally:
        conn.close()


def _normalize(rows) -> list[str]:
    return sorted("\t".join("" if v is None else str(v) for v in row) for row in rows)


def rows_match(rows, expected_result: str) -> bool:
    expected_rows = [line for line in expected_result.strip("\n").split("\n") if line]
    return _normalize(rows) == sorted(expected_rows)
