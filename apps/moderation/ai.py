import json
from concurrent.futures import ThreadPoolExecutor

import anthropic

from apps.problems.models import Problem
from django.utils.translation import gettext as _t, gettext_lazy as _tl

MODEL_CHOICES = [
    ("claude-sonnet-5", _tl("Sonnet 5 (tavsiya etiladi)")),
    ("claude-opus-5", "Opus 5"),
    ("claude-haiku-4-5", "Haiku 4.5"),
]
DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_LEVELS = {"easy": 2, "medium": 1}
MAX_COUNT = 10
MIN_TESTCASES = 20
# What each level means, so "medium" is the same size of problem every time.
LEVEL_BRIEFS = {
    "beginner": _tl("kiritish-chiqarish, arifmetika, bitta-ikkita shart; yechim bir necha qator"),
    "easy": _tl("sikl, shartlar, massiv yoki satr ustida oddiy ishlov; to‘g‘ridan-to‘g‘ri yechim o‘tadi"),
    "medium": _tl("saralash, prefiks yig‘indi, ikki ko‘rsatkich, ochko‘z usul yoki oddiy DP; "
              "cheklovlar sodda (O(n²)) yechimni o‘tkazmaydi"),
    "hard": _tl("murakkab DP, graflar, sonlar nazariyasi yoki ma’lumotlar tuzilmalari; "
            "katta cheklovlar, samarali algoritm shart"),
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
    """[("easy_1", "easy"), ("easy_2", "easy"), ...]: one entry per problem, in level order."""
    return [(f"{level}_{i}", level) for level in Problem.Difficulty.values
            for i in range(1, levels.get(level, 0) + 1)]


def _request(slots, index: int, topics, focus: str) -> str:
    """The prompt for problem `index` of `slots`. Each problem is its own request (one small
    schema each — a single schema holding every problem compiles to a grammar the API rejects
    as too large), so the prompt names the whole batch and this problem's place in it to keep
    the problems from repeating each other."""
    labels = dict(Problem.Difficulty.choices)
    key, level = slots[index]
    same = [k for k, lv in slots if lv == level]
    lines = [_t("Bitta masala tuz: {labels_level} — {level_briefs_level}.").format(labels_level=labels[level], level_briefs_level=LEVEL_BRIEFS[level])]
    if len(slots) > 1:
        lines.append(_t("Bu {len_slots} ta masaladan iborat to'plamning {index_1}-masalasi").format(len_slots=len(slots), index_1=index + 1)
                     + (_t(" ({labels_level} darajasida {same_index_key_1}-si, jami {len_same} ta)").format(labels_level=labels[level], same_index_key_1=same.index(key) + 1, len_same=len(same))
                        if len(same) > 1 else "")
                     + _t(". To'plamdagi boshqa masalalar bilan takrorlanmaydigan g'oya tanla."))
    if topics:
        # rotate the topic list so parallel requests don't all start from the same one
        shift = index % len(topics)
        ordered = list(topics[shift:]) + list(topics[:shift])
        lines.append(f"Mavzular: {', '.join(ordered)} (birinchisini asos qilib ol). Masala shulardan "
                     "kamida bittasiga tegishli bo'lsin; tags ga faqat shu ro'yxatdan yoz.")
    if focus:
        lines.append(_t("Aniq mavzu va talablar: {focus}").format(focus=focus))
    return "\n".join(lines)


def _generate_one(client, model: str, schema: dict, prompt: str) -> dict:
    try:
        with client.messages.stream(
            model=model,
            max_tokens=64000,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        ) as stream:
            response = stream.get_final_message()
    except anthropic.APIError as e:
        raise AIGenerationError(str(e)) from e

    if getattr(response, "stop_reason", None) == "max_tokens":
        raise AIGenerationError(_t("Javob uzilib qoldi — qayta urinib ko'ring."))
    if getattr(response, "stop_reason", None) == "refusal":
        raise AIGenerationError(_t("AI bu so'rovni bajarmadi — mavzu yoki talabni o'zgartirib ko'ring."))
    text = next((b.text for b in response.content if b.type == "text"), None)
    if text is None:
        raise AIGenerationError(_t("AI javobida matn topilmadi."))
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise AIGenerationError(_t("AI javobi JSON emas: {e}").format(e=e)) from e


def generate_problems(levels: dict[str, int], topics: list[str] = (), focus: str = "",
                      model: str = DEFAULT_MODEL, client=None, allowed_tags: list[str] = ()) -> list[dict]:
    """Draft `levels[level]` problems per level, each with `difficulty` set. `topics`: what
    they must be about (none: the model picks). Tags come only from `topics`, else from
    `allowed_tags` (the site's topic list), so the model can't invent variants in other
    languages. One request per problem, run in parallel."""
    slots = _slots(levels)
    if not 1 <= len(slots) <= MAX_COUNT:
        raise AIGenerationError(_t("1 dan {max_count} tagacha masala so'rang.").format(max_count=MAX_COUNT))
    schema = _PROBLEM_SCHEMA
    if topics or allowed_tags:
        tags = {"type": "array", "items": {"type": "string", "enum": list(topics or allowed_tags)}}
        schema = {**_PROBLEM_SCHEMA, "properties": {**_PROBLEM_SCHEMA["properties"], "tags": tags}}
    client = client or anthropic.Anthropic()

    with ThreadPoolExecutor(max_workers=min(4, len(slots))) as pool:
        futures = [pool.submit(_generate_one, client, model, schema, _request(slots, i, list(topics), focus))
                   for i in range(len(slots))]
        results = [f.result() for f in futures]  # the first failure is raised as-is

    problems = []
    for (key, level), p in zip(slots, results):
        if not isinstance(p, dict):
            raise AIGenerationError(_t("AI javobida {key} masalasi yo'q. Qayta urinib ko'ring.").format(key=key))
        if len(p.get("testcases", [])) < MIN_TESTCASES:
            raise AIGenerationError(
                _t("«{title}» uchun {n} ta test bor, kamida {min} ta kerak. Qayta urinib ko‘ring.").format(
                    title=p.get("title", "?"), n=len(p.get("testcases", [])), min=MIN_TESTCASES)
            )
        problems.append({**p, "difficulty": level})
    return problems
