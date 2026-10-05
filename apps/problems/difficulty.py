"""A problem's difficulty rating, the Codeforces way: the rating at which half of the people who
try the problem solve it. It sits on the contest rating's scale and uses its Elo curve
(apps.contests.rating), so a problem rated d is solved by about 76% of people rated d + 200 and
by 24% of those rated d - 200; it is found from who tried the problem and who solved it.

A problem few people have tried has little to go on, so the setter's guess (or its level's)
counts as GUESS_WEIGHT people of that rating, half of whom solved it: the rating starts at the
guess and moves to what the attempts say as they add up."""
from django.db.models import F

from apps.accounts.models import User
from apps.contests.rating import _beats, _rated_counts, hidden
from apps.submissions.models import Submission, UserProblemSolved

# Where each level (scoring.py) starts: the median rating its problems' attempts gave on
# production (October 2026: beginner 500, easy 600-700, medium ~1000; hard had too few). In
# practice people retry until they pass, so a newcomer, at the contest rating's start (1000),
# solves a beginner problem ~95% of the time and a hard one ~15%.
LEVEL_RATING = {"beginner": 500, "easy": 700, "medium": 1000, "hard": 1300}
GUESS_WEIGHT = 5
STEP = 100  # shown in hundreds, as on Codeforces
LOWEST, HIGHEST = 100, 3500


def guess(problem) -> int:
    return problem.rating_guess or LEVEL_RATING[problem.difficulty]


def estimate(results: list[tuple[int, bool]], prior: int) -> int:
    """The rating d at which the people in `results` (rating, solved) plus the guess's virtual
    ones would be expected to solve the problem as many times as they did."""
    target = sum(solved for _, solved in results) + GUESS_WEIGHT / 2
    low, high = float(LOWEST), float(HIGHEST)
    for _ in range(40):  # the expected solves fall as d rises: bisect
        d = (low + high) / 2
        expected = GUESS_WEIGHT * _beats(prior, d) + sum(_beats(rating, d) for rating, _ in results)
        low, high = (d, high) if expected > target else (low, d)
    return round(low / STEP) * STEP


def results(problems) -> dict[int, list[tuple[int, bool]]]:
    """Per problem id: everyone who submitted to it, its author and staff aside, with their rating
    as the contest maths sees it (a newcomer counts at the start) and whether they solved it."""
    # ponytail: only those who submitted count; Codeforces also counts a round's participants
    # who never tried the problem, which would lift hard contest problems a little.
    # order_by(): the default -id ordering would join DISTINCT and make each submission its own pair
    pairs = list(Submission.objects.filter(problem__in=problems, user__is_staff=False)
                 .exclude(user=F("problem__author")).order_by().values_list("problem_id", "user_id").distinct())
    shown = dict(User.objects.filter(pk__in={user for _, user in pairs}).values_list("pk", "rating"))
    rated = _rated_counts(list(shown))
    maths = {user: hidden(rating, rated.get(user, 0)) for user, rating in shown.items()}
    solved = set(UserProblemSolved.objects.filter(problem__in=problems).values_list("problem_id", "user_id"))
    out: dict[int, list[tuple[int, bool]]] = {}
    for problem, user in pairs:
        out.setdefault(problem, []).append((maths[user], (problem, user) in solved))
    return out


def rate(problem) -> int:
    """The problem's rating now; a new problem's is its guess."""
    if problem.pk is None:
        return guess(problem)
    return estimate(results([problem.pk]).get(problem.pk, []), guess(problem))
