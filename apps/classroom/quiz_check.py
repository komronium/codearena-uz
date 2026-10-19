"""Checks a duel question by running it: `problems(entry)` says what to run and what must come out, and
`run` (the judge sandbox's run_trial in production) does the running."""
from .quiz_bank import XATO

BLANK = "___"
_CPP = "#include <bits/stdc++.h>\nusing namespace std;\n\nint main() {\n%s\n}\n"
_JAVA = "import java.util.*;\n\npublic class Main {\n    public static void main(String[] args) {\n%s\n    }\n}\n"
SANDBOX_LANG = {"python": "python", "cpp": "cpp", "java": "java", "js": "node"}


def sandbox_run(language, source):
    """`run` for check() in production: the judge sandbox (the worker container has it)."""
    from judge.runner import run_trial
    r = run_trial(SANDBOX_LANG[language], source, [""], None, 2000, 256)
    if r["verdict"] != "OK":
        return False, r["log"] or r["verdict"]
    return True, r["cases"][0]["output"]


def program(language: str, code: str, full: bool) -> str:
    """The runnable program around what the player sees."""
    if language == "cpp" and not full:
        return _CPP % code
    if language == "java" and not full:
        return _JAVA % code
    return code + "\n"


def norm(s: str) -> str:
    """Answers compare without any spacing: "[1,4]" is "[1, 4]"."""
    return "".join(s.split())


def _out(s: str) -> str:
    return "\n".join(line.rstrip() for line in s.replace("\r\n", "\n").strip("\n").split("\n"))


def check(entry: dict, run) -> list[str]:
    """What is wrong with the question; [] when every claim it makes holds. `run(language, source)`
    returns (ok, stdout): ok False for a compile error, a crash or a timeout."""
    errors = []
    lang, full, code = entry["language"], entry["full"], entry["code"]
    options = entry["options"]
    if options:
        if entry["answer"] not in options:
            errors.append("javob variantlar orasida yo‘q")
        if len(set(options)) != len(options):
            errors.append("variantlar takrorlangan")
    if entry["kind"] == "output":
        if BLANK in code:
            errors.append("output savolida ___ bor")
        ok, got = run(lang, program(lang, code, full))
        if entry["answer"] == XATO:
            if ok:
                errors.append(f"xato kutilgan, lekin chiqdi: {got!r}")
        elif not ok:
            errors.append(f"ishlamadi: {got[:200]!r}")
        else:
            got = _out(got)
            if got != entry["answer"]:
                errors.append(f"javob {entry['answer']!r}, chiqdi {got!r}")
            for wrong in options:  # a pick matches exactly; spacing is forgiven only when typed
                if wrong != entry["answer"] and wrong == got:
                    errors.append(f"noto‘g‘ri variant {wrong!r} ham to‘g‘ri chiqadi")
            for alt in entry["accept"]:
                if norm(alt) != norm(got):
                    errors.append(f"qabul qilinadigan {alt!r} chiqqanga mos emas")
    else:
        if code.count(BLANK) != 1:
            errors.append("fill savolida bitta ___ bo‘lishi kerak")
            return errors
        for right in [entry["answer"], *entry["accept"]]:
            ok, got = run(lang, program(lang, code.replace(BLANK, right), full))
            if not ok or _out(got) != entry["expect"]:
                errors.append(f"{right!r} bilan {entry['expect']!r} chiqmadi: {got[:200]!r}")
        for wrong in options:
            if wrong == entry["answer"]:
                continue
            ok, got = run(lang, program(lang, code.replace(BLANK, wrong), full))
            if ok and _out(got) == entry["expect"]:
                errors.append(f"noto‘g‘ri variant {wrong!r} ham {entry['expect']!r} chiqaradi")
    return errors
