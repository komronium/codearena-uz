"""Variants of bank questions, so no question can be learned by heart: the same program with other numbers,
the answer worked out by running it. Only "what does it print?" questions are varied (a fill question's blank
depends on the code around it), and only by the whole numbers outside strings; a variant that crashes, prints
nothing or prints what the original printed is dropped. Wrong options are made from the new answer (a number
a little off; True/False stay as they were); an answer of any other kind is typed.

    python manage.py generate_duel_variants [--per-question N] [--language python] [--dry-run]

It runs the sandbox, so it belongs in the worker container, like load_duel_questions --verify."""
import hashlib
import random
import re

from .quiz_bank import XATO, entries, friendly
from .quiz_check import _out, program

_STRING = re.compile(r"""("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')""")
_INT = re.compile(r"(?<![\w.])\d+(?![\w.])")
_MAX_ANSWER = 60
_ZERO = re.compile(r"(?<![\w.])0(?![\w.])")


def acceptable(code: str, answer: str, origin_code: str) -> bool:
    """A variant worth asking: not a long decimal tail (1.7142857142857142), and no 0 the original didn't have
    (`x * 0`, `+ 0` make a question trivial)."""
    if re.search(r"\d\.\d{5,}", answer):
        return False
    return len(_ZERO.findall(code)) <= len(_ZERO.findall(origin_code))


def mutate(code: str, rng: random.Random) -> str:
    """`code` with some whole numbers (outside strings) nudged; the code itself when none could be."""
    def bump(match):
        n = int(match.group())
        return str(max(n + rng.choice((-3, -2, -1, 1, 2, 3, 4)), 0)) if rng.random() < 0.7 else match.group()

    for _ in range(5):
        parts = _STRING.split(code)  # odd parts are the strings
        new = "".join(p if i % 2 else _INT.sub(bump, p) for i, p in enumerate(parts))
        if new != code:
            return new
    return code


def options_for(answer: str, original: list[str], rng: random.Random) -> list[str]:
    """Picks for a variant whose original was multiple choice; [] means typed."""
    if not original:
        return []
    if re.fullmatch(r"-?\d+", answer):
        n = int(answer)
        near = [n + d for d in (-2, -1, 1, 2, 3) if n + d != n]
        wrong = [str(v) for v in rng.sample(near, 3)]
    elif re.fullmatch(r"-?\d+\.\d+", answer):
        places, f = len(answer.split(".")[1]), float(answer)
        near = [round(f + d, places) for d in (-1, -0.5, 0.5, 1, 2)]
        wrong = [f"{v:.{places}f}" for v in rng.sample(near, 3)]
    elif answer in ("True", "False") and {"True", "False"} <= set(original):
        return list(original)
    else:
        return []
    return [answer, *wrong]


def variants_of(entry: dict, run, count: int, rng: random.Random):
    """Up to `count` new questions from one bank entry; `run(language, source)` returns (ok, stdout)."""
    if entry["kind"] != "output" or entry["answer"] == XATO:
        return
    seen = {entry["code"]}
    for _ in range(count * 4):
        if len(seen) > count:
            break
        code = mutate(entry["code"], rng)
        if code in seen:
            continue
        seen.add(code)
        ok, got = run(entry["language"], program(entry["language"], code, entry["full"]))
        answer = _out(got) if ok else ""
        if not answer or len(answer) > _MAX_ANSWER or answer == entry["answer"]:
            continue
        options = options_for(answer, entry["options"], rng)
        if entry["options"] and not options:  # a pick question never turns into a typed one
            continue
        if not friendly(entry["language"], code, answer, options) or not acceptable(code, answer, entry["code"]):
            continue
        digest = hashlib.sha1(f"variant\n{entry['language']}\n{code}".encode()).hexdigest()[:10]
        yield {**entry, "code": code, "answer": answer, "accept": [], "explain": "",
               "options": options, "origin": entry["key"],
               "key": f"{entry['language']}-v{digest}"}


def generate(run, per_question: int = 6, languages=None, seed=None):
    """Variants of every bank question (of `languages`, if given)."""
    rng = random.Random(seed)
    for entry in entries():
        if languages and entry["language"] not in languages:
            continue
        yield from variants_of(entry, run, per_question, rng)
