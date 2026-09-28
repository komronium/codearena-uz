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
    verdict, _, rows = run_query_table(schema_sql, seed_sql, query, tl_ms)
    return verdict, rows


def run_query_table(schema_sql: str, seed_sql: str, query: str, tl_ms: int):
    """Like run_query, plus the result's column names: (verdict, columns, rows)."""
    conn = _load(schema_sql, seed_sql)
    try:
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
                return "TLE", [], []
            return "RE", [], []
        except sqlite3.Error:
            return "RE", [], []

        if len(rows) > MAX_ROWS:
            return "RE", [], []
        return "OK", [d[0] for d in cur.description or ()], rows
    finally:
        conn.close()


def _load(schema_sql: str, seed_sql: str) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(schema_sql)
        conn.executescript(seed_sql)
        conn.commit()
    except sqlite3.Error as exc:
        conn.close()
        raise SQLJudgeError(str(exc)) from exc
    return conn


def tables(schema_sql: str, seed_sql: str) -> list[dict]:
    """Each table of the dataset in creation order: its name, (column, type) pairs and rows,
    for the problem page to draw the data students query."""
    conn = _load(schema_sql, seed_sql)
    try:
        names = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY rowid")]
        out = []
        for name in names:
            quoted = '"' + name.replace('"', '""') + '"'
            columns = [(c[1], c[2]) for c in conn.execute(f"PRAGMA table_info({quoted})")]
            rows = conn.execute(f"SELECT * FROM {quoted}").fetchmany(MAX_ROWS)
            out.append({"name": name, "columns": columns, "rows": rows})
        return out
    finally:
        conn.close()


def _cells(row) -> str:
    return "\t".join("" if v is None else str(v) for v in row)


def format_rows(rows) -> str:
    """Rows as an expected_result text: what rows_match compares against."""
    return "".join(_cells(row) + "\n" for row in rows)


def parse_rows(expected_result: str) -> list[list[str]]:
    return [line.split("\t") for line in expected_result.strip("\n").split("\n") if line]


def rows_match(rows, expected_result: str, ordered: bool = False) -> bool:
    got = [_cells(row) for row in rows]
    want = [line for line in expected_result.strip("\n").split("\n") if line]
    return got == want if ordered else sorted(got) == sorted(want)
