import pytest

from judge.sql_judge import SQLJudgeError, rows_match, run_query

SCHEMA = "CREATE TABLE users(id INTEGER, name TEXT, age INTEGER);"
SEED = "INSERT INTO users VALUES (1,'ali',20),(2,'vali',25),(3,'guli',22);"


def test_run_query_returns_rows():
    verdict, rows = run_query(SCHEMA, SEED, "SELECT name FROM users WHERE age > 21 ORDER BY name", 1000)
    assert verdict == "OK"
    assert rows == [("guli",), ("vali",)]


def test_run_query_denies_write():
    verdict, rows = run_query(SCHEMA, SEED, "DELETE FROM users", 1000)
    assert verdict == "RE"
    assert rows == []


def test_run_query_denies_attach():
    verdict, rows = run_query(SCHEMA, SEED, "ATTACH DATABASE '/etc/passwd' AS x", 1000)
    assert verdict == "RE"


def test_run_query_denies_multiple_statements():
    verdict, rows = run_query(SCHEMA, SEED, "SELECT 1; DROP TABLE users;", 1000)
    assert verdict == "RE"


def test_run_query_times_out_on_runaway_query():
    # COUNT(*) can't return its one row until the whole cross join is scanned,
    # so this forces the progress handler to fire before any row is produced
    # (unlike a bare SELECT, which fetchmany() can cut short at MAX_ROWS).
    big_schema = SCHEMA + "\nCREATE TABLE t(id INTEGER);"
    seed = SEED + "\n" + "\n".join(f"INSERT INTO t VALUES ({i});" for i in range(300))
    verdict, rows = run_query(big_schema, seed, "SELECT COUNT(*) FROM t a, t b, t c, t d", 50)
    assert verdict == "TLE"
    assert rows == []


def test_run_query_bad_syntax_is_runtime_error():
    verdict, rows = run_query(SCHEMA, SEED, "SELEKT * FROM users", 1000)
    assert verdict == "RE"


def test_run_query_raises_on_broken_schema():
    with pytest.raises(SQLJudgeError):
        run_query("NOT VALID SQL(", "", "SELECT 1", 1000)


def test_rows_match_ignores_row_order():
    assert rows_match([("b",), ("a",)], "a\nb\n")


def test_rows_match_respects_column_order():
    assert not rows_match([(1, 2)], "2\t1")


def test_rows_match_normalizes_none_to_empty_string():
    assert rows_match([(None, "x")], "\tx")


def test_rows_match_fails_on_extra_row():
    assert not rows_match([("a",), ("b",)], "a\n")
