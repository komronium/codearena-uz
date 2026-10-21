"""Which texts a piece of content has, what is translated, and the AI draft. A "unit" is (a model row, a field): a problem
has its own fields and one per hint, a course its own and one per section, a contest its own."""
import json

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from .models import ContentTranslation

LANG_NAMES = {"uz": "Uzbek (Latin script)", "en": "English"}
KINDS = {"problems": "problems.Problem", "courses": "learn.StudyPlan", "contests": "contests.Contest"}
MODEL_ID = "claude-sonnet-5"
_SYSTEM = (
    "You translate text for CodeArena, a programming-practice site (problems, courses, contests). Translate faithfully and "
    "naturally for students. Keep Markdown structure, LaTeX ($...$), code blocks and inline code, identifiers, numbers, "
    "sample inputs and outputs, URLs and HTML exactly as they are; translate only the human language. For problem "
    "statements use the usual competitive-programming phrasing. Do not add or drop sentences."
)


def other(lang: str) -> str:
    return "en" if lang == "uz" else "uz"


def model_of(kind: str):
    from django.apps import apps
    return apps.get_model(KINDS[kind])


def units(obj) -> list[tuple]:
    """[(row, field, raw text)] of everything on `obj` (and its children) that has text, read raw (never translated)."""
    out = []
    for f in type(obj).TRANSLATABLE:
        text = getattr(obj, f)
        if text and str(text).strip():
            out.append((obj, f, str(text)))
    children = []
    if hasattr(obj, "hints"):
        children = list(obj.hints.all())
    elif hasattr(obj, "sections"):
        children = list(obj.sections.all())
    for child in children:
        for f in type(child).TRANSLATABLE:
            text = getattr(child, f)
            if text and str(text).strip():
                out.append((child, f, str(text)))
    return out


def key(row, field: str) -> str:
    return f"{type(row).__name__.lower()}.{row.pk}.{field}"


def existing(obj, lang: str) -> dict:
    """{(content type id, object id, field): ContentTranslation} for all the units of obj in `lang`."""
    rows = {}
    for row, field, _ in units(obj):
        ct = ContentType.objects.get_for_model(row)
        t = ContentTranslation.objects.filter(content_type=ct, object_id=row.pk, lang=lang, field=field).first()
        if t:
            rows[(ct.pk, row.pk, field)] = t
    return rows


def status(obj, lang: str | None = None) -> str:
    """"none" (nothing yet), "draft" (some text, not all confirmed) or "confirmed" (every text confirmed)."""
    lang = lang or other(obj.source_lang)
    us = units(obj)
    have = existing(obj, lang)
    if not have:
        return "none"
    cts = {}
    ok = True
    for row, field, _ in us:
        ct = cts.setdefault(type(row), ContentType.objects.get_for_model(row))
        t = have.get((ct.pk, row.pk, field))
        if t is None or not t.confirmed:
            ok = False
    return "confirmed" if ok else "draft"


def save_draft(row, field: str, lang: str, text: str, by_ai: bool = False, user=None, confirm: bool = False):
    ct = ContentType.objects.get_for_model(row)
    t, _ = ContentTranslation.objects.get_or_create(content_type=ct, object_id=row.pk, lang=lang, field=field)
    t.text, t.by_ai = text, by_ai
    t.confirmed = confirm
    if confirm:
        t.reviewed_by, t.reviewed_at = user, timezone.now()
    t.save()
    return t


def stale(obj):
    """The author's text changed: every translation of it waits for an admin again."""
    for row, field, _ in units(obj):
        ct = ContentType.objects.get_for_model(row)
        for t in ContentTranslation.objects.filter(content_type=ct, object_id=row.pk, confirmed=True):
            t.confirmed = False
            t.save(update_fields=["confirmed", "updated"])


def ai_translate(obj, client=None) -> int:
    """Ask the AI for the other language of every text on `obj`; stored as unconfirmed drafts. Returns how many."""
    import anthropic

    src, dst = obj.source_lang, other(obj.source_lang)
    us = units(obj)
    if not us:
        return 0
    keys = {key(row, field): (row, field, text) for row, field, text in us}
    schema = {"type": "object", "properties": {k: {"type": "string"} for k in keys}, "required": list(keys),
              "additionalProperties": False}
    prompt = (f"Translate from {LANG_NAMES[src]} into {LANG_NAMES[dst]}. Return a JSON object with the same keys, "
              "each value the translation of that text.\n\n" + json.dumps({k: v[2] for k, v in keys.items()}, ensure_ascii=False))
    client = client or anthropic.Anthropic()
    try:
        with client.messages.stream(model=MODEL_ID, max_tokens=64000, system=_SYSTEM,
                                    messages=[{"role": "user", "content": prompt}],
                                    output_config={"format": {"type": "json_schema", "schema": schema}}) as stream:
            response = stream.get_final_message()
    except anthropic.APIError as e:
        raise RuntimeError(str(e)) from e
    if getattr(response, "stop_reason", None) in ("max_tokens", "refusal"):
        raise RuntimeError(f"the AI stopped: {response.stop_reason}")
    text = next((b.text for b in response.content if b.type == "text"), "")
    data = json.loads(text)
    n = 0
    for k, (row, field, _) in keys.items():
        value = str(data.get(k, "")).strip()
        if value:
            save_draft(row, field, dst, value, by_ai=True)
            n += 1
    return n


def confirm_all(obj, user) -> int:
    lang = other(obj.source_lang)
    n = 0
    for row, field, _ in units(obj):
        ct = ContentType.objects.get_for_model(row)
        for t in ContentTranslation.objects.filter(content_type=ct, object_id=row.pk, lang=lang, confirmed=False).exclude(text=""):
            t.confirm(user)
            n += 1
    return n
