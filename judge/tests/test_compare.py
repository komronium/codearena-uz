from judge.compare import outputs_match


def test_exact():
    assert outputs_match("3\n", "3\n")


def test_trailing_spaces_and_newlines_ignored():
    assert outputs_match("3\n", "3  \n\n")
    assert outputs_match("1 2\n3\n", "1 2 \n3")


def test_missing_line_is_mismatch():
    assert not outputs_match("1\n2\n", "1\n")


def test_leading_space_is_mismatch():
    assert not outputs_match("3", " 3")
