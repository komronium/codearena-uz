def _norm(s: str) -> list[str]:
    lines = [line.rstrip() for line in s.replace("\r\n", "\n").split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def outputs_match(expected: str, actual: str) -> bool:
    return _norm(expected) == _norm(actual)
