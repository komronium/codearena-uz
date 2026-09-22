import json

import anthropic

from apps.problems.models import Problem

MODEL_CHOICES = [
    ("claude-sonnet-5", "Sonnet 5 (tavsiya etiladi)"),
    ("claude-opus-5", "Opus 5"),
    ("claude-haiku-4-5", "Haiku 4.5"),
]
DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_COUNT = 3
MIN_COUNT, MAX_COUNT = 1, 10
MIN_TESTCASES = 20

_PROBLEM_SCHEMA = {
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
            "minItems": MIN_TESTCASES,
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
    "asosida bir nechta to'liq, aniq, sinovdan o'tkazilishi mumkin bo'lgan masala tuz: "
    "har biri uchun markdown shart matni, kirish/chiqish tavsifi, va kamida "
    f"{MIN_TESTCASES} ta xilma-xil test (oddiy holatlar + chegaraviy holatlar; kamida "
    "bittasi is_sample=true — shart ichida namunaviy misol sifatida ko'rsatiladigan test)."
)


class AIGenerationError(Exception):
    pass


def generate_problems(prompt: str, model: str = DEFAULT_MODEL, count: int = DEFAULT_COUNT, client=None) -> list[dict]:
    count = max(MIN_COUNT, min(MAX_COUNT, count))
    schema = {
        "type": "object",
        "properties": {"problems": {"type": "array", "minItems": count, "maxItems": count, "items": _PROBLEM_SCHEMA}},
        "required": ["problems"],
        "additionalProperties": False,
    }
    client = client or anthropic.Anthropic()
    try:
        with client.messages.stream(
            model=model,
            max_tokens=64000,
            system=_SYSTEM,
            messages=[{"role": "user", "content": f"{count} ta masala tuz. Mavzu/talab: {prompt}"}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        ) as stream:
            response = stream.get_final_message()
    except Exception as e:
        raise AIGenerationError(str(e)) from e

    text = next((b.text for b in response.content if b.type == "text"), None)
    if text is None:
        raise AIGenerationError("AI javobida matn topilmadi.")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise AIGenerationError(f"AI javobi JSON emas: {e}") from e
    return data["problems"]
