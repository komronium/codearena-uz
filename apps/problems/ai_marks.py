"""AI markers in a statement: `[[ai: …]]` in the Markdown is a note for an AI assistant that a person
does not see (visually hidden, skipped by screen readers) but that copying the statement keeps. It asks
for a name in backticks (`javob_qz`); code that carries that name was very likely written by an AI from
the copied text, and the contest report shows it as evidence. Staff see the marker in the editor as is."""
import re

MARK = re.compile(r"\[\[ai:(.*?)\]\]", re.S)
TOKEN = re.compile(r"`([A-Za-z_][A-Za-z0-9_]{4,})`")
# rendered: Markdown has turned the backticks into <code>
_TOKEN_HTML = re.compile(r"<code>([A-Za-z_][A-Za-z0-9_]{4,})</code>")


def render(html: str) -> str:
    """The sanitized statement HTML with each marker turned into its hidden span."""
    return MARK.sub(lambda m: f'<span class="ca-ai-mark" aria-hidden="true"> {m.group(1).strip()}</span>', html)


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
