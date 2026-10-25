"""Contest submissions against the AI baselines of their problem (models.AiMatch)."""
from .models import AiBaseline, AiMatch
from .similarity import MIN_LINES, code_lines, similarity

AI_THRESHOLD = 0.85
# A short, forced solution is the same for everybody, an AI's included. When this share of a
# problem's candidates match a baseline, the match says nothing and none are kept.
COMMON_SHARE = 0.4
COMMON_MIN = 6


def match(contest, problem_id, candidates) -> int:
    """Rebuild the AI matches of one problem's candidate submissions (flag_similarity's picks:
    each ACs and last tries). Returns how many were kept."""
    AiMatch.objects.filter(submission__contest=contest, submission__problem_id=problem_id).delete()
    baselines = [b for b in AiBaseline.objects.filter(problem_id=problem_id) if code_lines(b.source) >= MIN_LINES]
    if not baselines:
        return 0
    found = []
    for sub in candidates:
        best = max(((similarity(sub.source, b.source), b) for b in baselines if b.language_id == sub.language_id),
                   key=lambda t: t[0], default=None)
        if best and best[0] >= AI_THRESHOLD:
            found.append((sub, best[1], best[0]))
    if len(candidates) >= COMMON_MIN and len(found) / len(candidates) >= COMMON_SHARE:
        return 0
    AiMatch.objects.bulk_create(AiMatch(submission=s, baseline=b, score=score) for s, b, score in found)
    return len(found)
