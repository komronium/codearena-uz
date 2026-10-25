"""AI baselines (models.AiBaseline): ask an AI to solve each contest problem from its statement, as a
cheater would, and keep the answers to compare submissions with (ai_match). The statement goes in as a
participant would copy it, without the hidden AI notes."""
import re
from concurrent.futures import ThreadPoolExecutor

import anthropic

from apps.moderation.ai import DEFAULT_MODEL
from apps.problems.ai_marks import strip
from apps.problems.models import Language, Problem

from .models import AiBaseline

# Each sample is asked for in a different style: an AI's answers to one prompt differ in
# naming and structure, and the real cheater's prompt differs from ours.
STYLES = (
    "Write the shortest correct solution.",
    "Write a clear solution with helper functions and descriptive names.",
    "Write a solution the way a competitive programmer would, with fast input reading.",
    "Write a careful solution that handles edge cases explicitly.",
)
_SYSTEM = ("You solve programming problems. Reply with exactly one fenced code block holding the complete "
           "program (it reads standard input and writes standard output), and nothing else.")
_FENCE = re.compile(r"```[A-Za-z0-9+#_-]*\n(.*?)```", re.S)


def _prompt(problem: Problem, language: Language, style: str) -> str:
    parts = [f"# {problem.title}", strip(problem.statement_md or "")]
    if problem.input_md:
        parts += ["## Input", strip(problem.input_md)]
    if problem.output_md:
        parts += ["## Output", strip(problem.output_md)]
    samples = problem.testcases.filter(is_sample=True)[:2]
    for i, t in enumerate(samples, 1):
        parts += [f"## Example {i}", f"Input:\n{t.input.strip()}\n\nOutput:\n{t.expected.strip()}"]
    parts.append(f"Language: {language.name}. {style}")
    return "\n\n".join(parts)


def extract_code(text: str) -> str:
    m = _FENCE.search(text)
    return (m.group(1) if m else "").strip("\n")


def _one(client, model, problem, language, style) -> str:
    response = client.messages.create(
        model=model, max_tokens=4000, system=_SYSTEM,
        messages=[{"role": "user", "content": _prompt(problem, language, style)}])
    return extract_code(next((b.text for b in response.content if b.type == "text"), ""))


def generate(problem: Problem, language: Language, count: int, model: str = DEFAULT_MODEL, client=None) -> int:
    """Add up to `count` baselines for (problem, language); returns how many were kept (empty or
    failed answers are skipped). Needs ANTHROPIC_API_KEY unless a client is passed."""
    client = client or anthropic.Anthropic()
    styles = [STYLES[i % len(STYLES)] for i in range(count)]

    def run(style):
        try:
            return _one(client, model, problem, language, style)
        except anthropic.APIError:
            return ""

    with ThreadPoolExecutor(max_workers=min(4, count)) as pool:
        sources = list(pool.map(run, styles))
    made = 0
    for source in sources:
        if source.strip():
            AiBaseline.objects.create(problem=problem, language=language, source=source, model=model)
            made += 1
    return made
