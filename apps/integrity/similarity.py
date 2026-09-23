import difflib
import re

THRESHOLD = 0.90
# Short solutions (a+b, one-liners) converge naturally; only real code is worth a flag.
MIN_LINES = 4

# Comments are free text: stripping them stops "add a comment" from dodging the score
# and stops identical boilerplate comments from inflating it.
_COMMENT_RE = re.compile(r"/\*.*?\*/|//[^\n]*|#(?!include)[^\n]*", re.S)

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[0-9]+\.?[0-9]*|[^\w\s]")

# Union of python/cpp/java/js keywords + common builtins. Kept as one flat set —
# a token being a keyword in a language the submission isn't written in is
# harmless (it just also stays literal, which never hurts the diff).
_KEYWORDS = frozenset({
    "if", "else", "elif", "for", "while", "do", "switch", "case", "break", "continue",
    "return", "def", "function", "class", "struct", "enum", "interface", "public",
    "private", "protected", "static", "final", "const", "let", "var", "void", "int",
    "long", "short", "float", "double", "char", "bool", "boolean", "string", "String",
    "true", "false", "null", "None", "nil", "undefined", "new", "delete", "this", "self",
    "super", "import", "from", "include", "using", "namespace", "try", "catch", "except",
    "finally", "throw", "throws", "raise", "with", "as", "in", "is", "not", "and", "or",
    "xor", "lambda", "yield", "async", "await", "print", "printf", "cout", "cin", "scanf",
    "System", "console", "main", "sizeof", "typedef", "template", "virtual", "override",
    "extends", "implements", "package", "export", "default",
    # library names people don't rename: keeping them literal keeps unrelated code apart
    "input", "map", "list", "dict", "set", "tuple", "range", "len", "sum", "min", "max",
    "sorted", "sort", "split", "append", "join", "abs", "str", "open", "sys", "stdin",
    "readline", "strip", "std", "vector", "push_back", "size", "endl", "Scanner",
    "nextInt", "Math", "parseInt", "require", "readFileSync", "log", "length", "push",
})


def _canonical_lines(source: str) -> list[str]:
    """One canonical token string per original line: every user identifier becomes
    "V" so renaming variables/functions doesn't dodge the check, and — unlike
    first-appearance numbering — one extra variable or import doesn't shift every
    later name and hide the copy.
    ponytail: regex tokenizer, not a real per-language parser, so it can't see through
    statement reordering or helper-function extraction. Upgrade path: an AST diff
    (e.g. tree-sitter) per language if that becomes the common evasion."""
    out = []
    for line in _strip_comments(source).splitlines():
        toks = ("V" if (t[0].isalpha() or t[0] == "_") and t not in _KEYWORDS else t
                for t in _TOKEN_RE.findall(line))
        out.append(" ".join(toks))
    return out


def _strip_comments(source: str) -> str:
    # keep newlines inside block comments so line numbers still match the original
    return _COMMENT_RE.sub(lambda m: "\n" * m.group().count("\n"), source)


def code_lines(source: str) -> int:
    """Non-blank lines once comments are gone."""
    return sum(1 for line in _strip_comments(source).splitlines() if line.strip())


def similarity(source_a: str, source_b: str) -> float:
    return difflib.SequenceMatcher(
        a=" ".join(_canonical_lines(source_a)), b=" ".join(_canonical_lines(source_b)), autojunk=False).ratio()


def matched_lines(source_a: str, source_b: str) -> tuple[set[int], set[int]]:
    """0-based line numbers in each source that belong to a shared block (after renaming),
    blank lines excluded — what the reviewer should look at side by side."""
    ca, cb = _canonical_lines(source_a), _canonical_lines(source_b)
    ia = [i for i, x in enumerate(ca) if x]
    ib = [i for i, x in enumerate(cb) if x]
    sm = difflib.SequenceMatcher(a=[ca[i] for i in ia], b=[cb[i] for i in ib], autojunk=False)
    hit_a, hit_b = set(), set()
    for blk in sm.get_matching_blocks():
        hit_a.update(ia[blk.a + k] for k in range(blk.size))
        hit_b.update(ib[blk.b + k] for k in range(blk.size))
    return hit_a, hit_b
