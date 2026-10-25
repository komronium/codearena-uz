"""AI markers in a statement: `[[ai: …]]` in the Markdown is a note for an AI assistant that a person
does not see (visually hidden, skipped by screen readers) but that copying the statement keeps. It asks
for a name in backticks (`javob_qz`); code that carries that name was very likely written by an AI from
the copied text, and the contest report shows it as evidence. Staff see the marker in the editor as is.

A signed-in reader gets their own copy of the name (`javob_qz_k3`, the suffix is their id): code that
carries someone else's copy shows who handed the statement or the answer on."""
import re

MARK = re.compile(r"\[\[ai:(.*?)\]\]", re.S)
TOKEN = re.compile(r"`([A-Za-z_][A-Za-z0-9_]{4,})`")
# rendered: Markdown has turned the backticks into <code>
_TOKEN_HTML = re.compile(r"<code>([A-Za-z_][A-Za-z0-9_]{4,})</code>")

_DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"


def _b36(n: int) -> str:
    out = ""
    while n:
        n, r = divmod(n, 36)
        out = _DIGITS[r] + out
    return out or "0"


def _check(user_id: int) -> str:
    return _DIGITS[(user_id * 7 + 3) % 36]


def personal(token: str, user_id: int) -> str:
    """The reader's own copy of a marker's name: `javob_qz` -> `javob_qz_k3` (id in base 36 + a check digit)."""
    return f"{token}_{_b36(user_id)}{_check(user_id)}"


def pattern(token: str) -> re.Pattern:
    """Finds a marker's name in code, bare or as someone's copy; group 1 is the copy's suffix."""
    return re.compile(rf"(?<![A-Za-z0-9_]){re.escape(token)}(?:_([0-9a-z]{{2,}}))?(?![A-Za-z0-9_])")


def owner(suffix: str | None) -> int | None:
    """Whose copy a suffix is (their user id), or None for a bare name or a suffix that is not one."""
    if not suffix or len(suffix) < 2:
        return None
    body, check = suffix[:-1], suffix[-1]
    user_id = int(body, 36)
    return user_id if user_id and _check(user_id) == check else None


def render(html: str, user_id: int | None = None) -> str:
    """The sanitized statement HTML with each marker turned into its hidden span, naming the
    reader's own copy when there is a reader."""
    def span(m):
        text = m.group(1).strip()
        if user_id:
            text = _TOKEN_HTML.sub(lambda t: f"<code>{personal(t.group(1), user_id)}</code>", text)
        return f'<span class="ca-ai-mark" aria-hidden="true"> {text}</span>'
    return MARK.sub(span, html)


def strip(text: str) -> str:
    """Markdown or HTML without its markers (and their spans): for descriptions, previews, search."""
    text = re.sub(r'<span class="ca-ai-mark"[^>]*>.*?</span>', "", text, flags=re.S)
    return MARK.sub("", text)


def tokens(*texts: str) -> set[str]:
    """The names the markers ask for, from a problem's Markdown (statement, input, output)."""
    found = set()
    for text in texts:
        for m in MARK.finditer(text or ""):
            found |= set(TOKEN.findall(m.group(1))) | set(_TOKEN_HTML.findall(m.group(1)))
    return found
