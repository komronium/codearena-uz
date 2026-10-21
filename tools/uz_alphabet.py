"""The new Uzbek Latin spelling (2026 law): O‘ -> Ö, G‘ -> Ğ, Sh -> Ş, Ch -> Ç. `convert` rewrites the Uzbek words of a
UI string and leaves tags, placeholders, URLs and the words listed in KEEP (English and brand names) alone. The site's
source strings stay in the old spelling; locale/uz carries this conversion of each of them (tools/i18n_build.py), so it can
be switched off by deleting that folder."""
import re

KEEP = ("ChatGPT", "English", "Marshall", "Cheaterlarni", "Chrome", "Shift", "Github", "GitHub", "Sublime", "Anthropic")
_PROTECT = re.compile(r"(<[^>]*>|%\([^)]*\)s|\$\{[^}]*\}|\{[a-z_0-9]*\}|&[a-zA-Z]+;|&#\d+;|https?://\S+|[\w.+-]+@[\w-]+\.[\w.-]+)")
_KEEP = re.compile(r"\b(" + "|".join(map(re.escape, KEEP)) + r")\w*")
_APOS = "‘ʻ’'"


def _word(text: str) -> str:
    text = re.sub(rf"([OoGg])[{_APOS}](?=[A-Za-z])", lambda m: {"O": "Ö", "o": "ö", "G": "Ğ", "g": "ğ"}[m.group(1)], text)
    text = re.sub(r"(?i)sh", lambda m: "Ş" if m.group(0)[0].isupper() else "ş", text)
    text = re.sub(r"(?i)ch", lambda m: "Ç" if m.group(0)[0].isupper() else "ç", text)
    return text


def convert(text: str) -> str:
    out = []
    for i, part in enumerate(_PROTECT.split(text)):
        if i % 2:  # a tag, a placeholder, a link: kept
            out.append(part)
            continue
        pieces, last = [], 0
        for m in _KEEP.finditer(part):  # the words kept as they are
            pieces.append(_word(part[last:m.start()]))
            pieces.append(m.group(0))
            last = m.end()
        pieces.append(_word(part[last:]))
        out.append("".join(pieces))
    return "".join(out)
