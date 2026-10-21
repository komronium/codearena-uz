"""What a public handle may look like: it is shown on standings and put in profile URLs, so it is plain: a latin
letter first, then latin letters, digits and underscores."""
import re

USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,19}$")
USERNAME_RULE = ("Foydalanuvchi nomi lotin harfi bilan boshlansin va faqat lotin harflari, raqamlar va _ dan iborat "
                 "bo‘lsin (3–20 belgi).")


def valid_username(name: str) -> bool:
    return bool(USERNAME_RE.fullmatch(name or ""))
