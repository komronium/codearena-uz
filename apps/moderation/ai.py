import json

import anthropic

from apps.problems.models import Problem

MODEL_CHOICES = [
    ("claude-sonnet-5", "Sonnet 5 (tavsiya etiladi)"),
    ("claude-opus-5", "Opus 5"),
    ("claude-haiku-4-5", "Haiku 4.5"),
]
DEFAULT_MODEL = "claude-sonnet-5"

_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "statement_md": {"type": "string"},
        "input_md": {"type": "string"},
        "output_md": {"type": "string"},
        "difficulty": {"type": "string", "enum": list(Problem.Difficulty.values)},
        "tl_ms": {"type": "integer"},
        "ml_mb": {"type": "integer"},
        "points": {"type": "integer"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "testcases": {
            "type": "array",
            "minItems": 1,
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
    "required": ["title", "statement_md", "input_md", "output_md", "difficulty",
                 "tl_ms", "ml_mb", "points", "tags", "testcases"],
    "additionalProperties": False,
}

_SYSTEM = (
    "Sen dasturlash musobaqasi uchun masala tuzuvchi ekspertsan. Foydalanuvchi so'rovi "
    "asosida to'liq, aniq, sinovdan o'tkazilishi mumkin bo'lgan masala tuz: markdown "
    "shart matni, kirish/chiqish tavsifi, va kamida 3 ta test (kamida bittasi "
    "is_sample=true — shart ichida namunaviy misol sifatida ko'rsatilishi kerak bo'lgan test)."
)


class AIGenerationError(Exception):
    pass


def generate_problem(prompt: str, model: str = DEFAULT_MODEL, client=None) -> dict:
    client = client or anthropic.Anthropic()
    try:
        response = client.messages.create(
            model=model,
            max_tokens=8000,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
        )
    except Exception as e:
        raise AIGenerationError(str(e)) from e

    text = next((b.text for b in response.content if b.type == "text"), None)
    if text is None:
        raise AIGenerationError("AI javobida matn topilmadi.")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise AIGenerationError(f"AI javobi JSON emas: {e}") from e
