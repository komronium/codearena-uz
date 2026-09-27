import json

import anthropic

from apps.problems.models import Problem

MODEL_CHOICES = [
    ("claude-sonnet-5", "Sonnet 5 (tavsiya etiladi)"),
    ("claude-opus-5", "Opus 5"),
    ("claude-haiku-4-5", "Haiku 4.5"),
]
DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_LEVELS = {"easy": 2, "medium": 1}
MAX_COUNT = 10
MIN_TESTCASES = 20
# What each level means, so "medium" is the same size of problem every time.
LEVEL_BRIEFS = {
    "beginner": "kiritish-chiqarish, arifmetika, bitta-ikkita shart; yechim bir necha qator",
    "easy": "sikl, shartlar, massiv yoki satr ustida oddiy ishlov; to‘g‘ridan-to‘g‘ri yechim o‘tadi",
    "medium": "saralash, prefiks yig‘indi, ikki ko‘rsatkich, ochko‘z usul yoki oddiy DP; "
              "cheklovlar sodda (O(n²)) yechimni o‘tkazmaydi",
    "hard": "murakkab DP, graflar, sonlar nazariyasi yoki ma’lumotlar tuzilmalari; "
            "katta cheklovlar, samarali algoritm shart",
}

_PROBLEM_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "statement_md": {"type": "string"},
        "input_md": {"type": "string"},
        "output_md": {"type": "string"},
        "tl_ms": {"type": "integer"},
        "ml_mb": {"type": "integer"},
        "points": {"type": "integer"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "testcases": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "input": {"type": "string"},
                    "expected": {"type": "string"},
                    "is_sample": {"type": "boolean"},
                },
                "required": ["input", "expected", "is_sample"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "statement_md", "input_md", "output_md",
                 "tl_ms", "ml_mb", "points", "tags", "testcases"],
    "additionalProperties": False,
}

_SYSTEM = (
    "Sen dasturlash musobaqasi uchun masala tuzuvchi ekspertsan. So'rovdagi har bir masalani "
    "to'liq tuz: markdown shart matni, kirish/chiqish tavsifi va cheklovlar, hamda kamida "
    f"{MIN_TESTCASES} ta xilma-xil test (oddiy, chegaraviy va eng katta holatlar; kamida "
    "bittasi is_sample=true — shart ichida namunaviy misol sifatida ko'rsatiladigan test). "
    "Har bir testning expected qiymatini yechimni o'zing bajarib, aniq hisobla: bitta "
    "noto'g'ri test butun masalani buzadi. Qiyinlik va mavzu so'rovdagiga aniq mos bo'lsin, "
    "masalalar bir-birini takrorlamasin."
)


class AIGenerationError(Exception):
    pass


def _slots(levels: dict[str, int]) -> list[tuple[str, str]]:
    """[("easy_1", "easy"), ("easy_2", "easy"), ...]: one schema key per problem. Structured
    outputs can't bound an array's length, but a required key is always there, so the
    reply has exactly this many problems at exactly these levels."""
    return [(f"{level}_{i}", level) for level in Problem.Difficulty.values
            for i in range(1, levels.get(level, 0) + 1)]


def _request(slots, topics, focus: str) -> str:
    lines = [f"{len(slots)} ta masala tuz. Har bir kalit — bitta masala, qiyinligi kalit nomida:"]
    labels = dict(Problem.Difficulty.choices)
    for level in dict.fromkeys(level for _, level in slots):
        keys = ", ".join(key for key, lv in slots if lv == level)
        lines.append(f"- {keys}: {labels[level]} — {LEVEL_BRIEFS[level]}.")
    if topics:
        lines.append(f"Mavzular: {', '.join(topics)}. Har bir masala shulardan kamida bittasiga "
                     "tegishli bo'lsin; tags ga faqat shu ro'yxatdan yoz.")
    if focus:
        lines.append(f"Aniq mavzu va talablar: {focus}")
    return "\n".join(lines)


def generate_problems(levels: dict[str, int], topics: list[str] = (), focus: str = "",
                      model: str = DEFAULT_MODEL, client=None, allowed_tags: list[str] = ()) -> list[dict]:
    """Draft `levels[level]` problems per level, each with `difficulty` set. `topics`: what
    they must be about (none: the model picks). Tags come only from `topics`, else from
    `allowed_tags` (the site's topic list), so the model can't invent variants in other
    languages."""
    slots = _slots(levels)
    if not 1 <= len(slots) <= MAX_COUNT:
        raise AIGenerationError(f"1 dan {MAX_COUNT} tagacha masala so'rang.")
    problem = _PROBLEM_SCHEMA
    if topics or allowed_tags:
        tags = {"type": "array", "items": {"type": "string", "enum": list(topics or allowed_tags)}}
        problem = {**_PROBLEM_SCHEMA, "properties": {**_PROBLEM_SCHEMA["properties"], "tags": tags}}
    schema = {
        "type": "object",
        "properties": {key: problem for key, _ in slots},
        "required": [key for key, _ in slots],
        "additionalProperties": False,
    }
    client = client or anthropic.Anthropic()
    try:
        with client.messages.stream(
            model=model,
            max_tokens=64000,
            system=_SYSTEM,
            messages=[{"role": "user", "content": _request(slots, topics, focus)}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        ) as stream:
            response = stream.get_final_message()
    except Exception as e:
        raise AIGenerationError(str(e)) from e

    if getattr(response, "stop_reason", None) == "max_tokens":
        raise AIGenerationError("Javob uzilib qoldi — bir so'rovda kamroq masala so'rang.")
    text = next((b.text for b in response.content if b.type == "text"), None)
    if text is None:
        raise AIGenerationError("AI javobida matn topilmadi.")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise AIGenerationError(f"AI javobi JSON emas: {e}") from e

    problems = []
    for key, level in slots:
        p = data.get(key)
        if not isinstance(p, dict):
            raise AIGenerationError(f"AI javobida {key} masalasi yo'q. Qayta urinib ko'ring.")
        if len(p.get("testcases", [])) < MIN_TESTCASES:
            raise AIGenerationError(
                f"«{p.get('title', '?')}» uchun {len(p.get('testcases', []))} ta test bor, "
                f"kamida {MIN_TESTCASES} ta kerak. Qayta urinib ko'ring."
            )
        problems.append({**p, "difficulty": level})
    return problems
