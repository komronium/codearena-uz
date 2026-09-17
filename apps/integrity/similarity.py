import difflib
import re

THRESHOLD = 0.85


def normalize(source: str) -> str:
    """Token stream: identifiers/numbers/operators, whitespace-insensitive
    (spec §4.2), so reformatting alone doesn't dodge the similarity check."""
    return " ".join(re.findall(r"\w+|[^\w\s]", source))


def similarity(source_a: str, source_b: str) -> float:
    return difflib.SequenceMatcher(a=normalize(source_a), b=normalize(source_b)).ratio()
