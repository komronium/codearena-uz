import difflib
import re

THRESHOLD = 0.85

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
})


def _canonicalize(source: str) -> str:
    """Token stream with identifiers renamed to positional placeholders (V1, V2, ...
    in first-appearance order) so renaming variables/functions no longer dodges the
    similarity check — only literal restructuring does.
    ponytail: regex tokenizer, not a real per-language parser, so it can't see through
    statement reordering or helper-function extraction. Upgrade path: swap in an
    actual AST diff (e.g. tree-sitter) per language if renaming-evasion stops being
    the common case."""
    seen: dict[str, str] = {}
    out = []
    for tok in _TOKEN_RE.findall(source):
        if tok[0].isalpha() or tok[0] == "_":
            if tok in _KEYWORDS:
                out.append(tok)
            else:
                out.append(seen.setdefault(tok, f"V{len(seen) + 1}"))
        else:
            out.append(tok)
    return " ".join(out)


def similarity(source_a: str, source_b: str) -> float:
    return difflib.SequenceMatcher(a=_canonicalize(source_a), b=_canonicalize(source_b)).ratio()
