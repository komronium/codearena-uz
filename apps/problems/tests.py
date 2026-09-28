import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.contests.models import Contest, ContestProblem, Participation
from .models import Language, Problem, Tag, TestCase
from .scoring import BANDS, MIN_ATTEMPTS, compute_points


@pytest.fixture
def problem(db):
    author = User.objects.create_user("teacher", password="x", role="teacher")
    p = Problem.objects.create(slug="a-plus-b", title="A + B", statement_md="Ikki son **yig'indisi**.",
                               author=author)
    TestCase.objects.create(problem=p, input="1 2\n", expected="3\n", is_sample=True, order=0)
    TestCase.objects.create(problem=p, input="99 1\n", expected="100\n", is_sample=False, order=1)
    return p


def test_list_shows_public_problem(client, problem):
    r = client.get(reverse("problems:list"))
    assert r.status_code == 200
    assert b"A + B" in r.content


def test_list_hides_private_problem(client, problem):
    problem.is_public = False
    problem.save()
    r = client.get(reverse("problems:list"))
    assert b"A + B" not in r.content


def test_list_marks_solved_problem_for_logged_in_user(client, problem):
    from apps.problems.models import Language
    from apps.submissions.models import Submission, UserProblemSolved

    user = User.objects.create_user("ali", password="x")
    python = Language.objects.create(code="python", name="Python 3", docker_image="codearena-judge-python",
                                      run_cmd="python3 main.py")
    sub = Submission.objects.create(user=user, problem=problem, language=python, source="x", verdict="AC")
    UserProblemSolved.objects.create(user=user, problem=problem, first_ac_submission=sub)

    client.force_login(user)
    r = client.get(reverse("problems:list"))
    assert b'title="Yechilgan"' in r.content


def test_list_does_not_mark_unsolved_problem(client, problem):
    user = User.objects.create_user("ali", password="x")
    client.force_login(user)
    r = client.get(reverse("problems:list"))
    assert b'title="Yechilgan"' not in r.content


def test_detail_renders_markdown_and_samples_only(client, problem):
    r = client.get(reverse("problems:detail", kwargs={"slug": "a-plus-b"}))
    assert r.status_code == 200
    assert b"<strong>yig&#x27;indisi</strong>" in r.content or b"<strong>yig'indisi</strong>" in r.content
    assert b"1 2" in r.content
    assert b"99 1" not in r.content


def test_private_detail_404(client, problem):
    problem.is_public = False
    problem.save()
    assert client.get(reverse("problems:detail", kwargs={"slug": "a-plus-b"})).status_code == 404


def test_detail_strips_script_tags_from_statement(client, problem):
    problem.statement_md = "hi <script>alert(1)</script> there"
    problem.save()
    r = client.get(reverse("problems:detail", kwargs={"slug": "a-plus-b"}))
    assert b"<script>alert(1)</script>" not in r.content
    assert b"&lt;script&gt;alert(1)&lt;/script&gt;" in r.content


def test_detail_renders_ordered_list_immediately_after_a_paragraph(client, problem):
    # No blank line before "1." — the editor's own preview renders this as a list
    # (CommonMark allows a list to interrupt a paragraph); the server must match.
    problem.input_md = "3 ta son beriladi:\n1. Birinchi\n2. Ikkinchi\n3. Uchinchi"
    problem.save()
    r = client.get(reverse("problems:detail", kwargs={"slug": "a-plus-b"}))
    body = r.content.decode()
    assert "<ol>" in body and "<li>Birinchi</li>" in body and "<li>Uchinchi</li>" in body


def test_detail_still_renders_tables(client, problem):
    problem.statement_md = "|a|b|\n|-|-|\n|1|2|"
    problem.save()
    r = client.get(reverse("problems:detail", kwargs={"slug": "a-plus-b"}))
    body = r.content.decode()
    assert "<table>" in body and "<td>1</td>" in body


@pytest.fixture
def running_contest(db, problem):
    contest = Contest.objects.create(
        title="Sprint", start=timezone.now() - timezone.timedelta(minutes=5),
        end=timezone.now() + timezone.timedelta(minutes=55))
    ContestProblem.objects.create(contest=contest, problem=problem, label="A", points=100)
    return contest


def test_private_contest_problem_visible_to_registered_participant(client, problem, running_contest):
    problem.is_public = False
    problem.save()
    user = User.objects.create_user("ali", password="x")
    Participation.objects.create(user=user, contest=running_contest)
    client.force_login(user)
    r = client.get(reverse("problems:detail", kwargs={"slug": "a-plus-b"}))
    assert r.status_code == 200
    assert b"Musobaqa rejimi" in r.content
    # contest mode: statement + editor watermarked with who is viewing, printing blanked
    body = r.content.decode()
    assert body.count('class="ca-watermark" data-wm="ali ·') == 2
    assert '<style media="print">' in body
    assert 'id="ca-away"' in body  # leave tracker + warning dialog


def test_private_contest_problem_404_for_non_participant(client, problem, running_contest):
    problem.is_public = False
    problem.save()
    user = User.objects.create_user("bob", password="x")
    client.force_login(user)
    assert client.get(reverse("problems:detail", kwargs={"slug": "a-plus-b"})).status_code == 404


def test_upcoming_contest_problem_secret_even_if_public(client, problem):
    """Problems of a not-yet-started contest are hidden from list, detail, contest page
    and submit — is_public is irrelevant until the contest starts."""
    contest = Contest.objects.create(
        title="Soon", start=timezone.now() + timezone.timedelta(hours=1),
        end=timezone.now() + timezone.timedelta(hours=3))
    ContestProblem.objects.create(contest=contest, problem=problem, label="A", points=100)
    user = User.objects.create_user("ali", password="x")
    Participation.objects.create(user=user, contest=contest)
    client.force_login(user)

    assert problem not in client.get(reverse("problems:list")).context["problems"].object_list
    assert client.get(reverse("problems:detail", kwargs={"slug": "a-plus-b"})).status_code == 404
    assert b"a-plus-b" not in client.get(reverse("contests:detail", kwargs={"pk": contest.pk})).content
    lang = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    r = client.post(reverse("submissions:submit", kwargs={"slug": "a-plus-b"}),
                    {"language": lang.code, "source": "print(1)"})
    assert r.status_code == 404

    contest.start = timezone.now() - timezone.timedelta(minutes=1)
    contest.save()
    assert client.get(reverse("problems:detail", kwargs={"slug": "a-plus-b"})).status_code == 200


def test_list_sorts_by_column_and_direction(client, problem):
    author = problem.author
    hard = Problem.objects.create(slug="z", title="Zzz", statement_md="x", author=author, difficulty="hard")
    easy = Problem.objects.create(slug="b", title="Bbb", statement_md="x", author=author, difficulty="beginner")

    def ids(**params):
        return [p.id for p in client.get(reverse("problems:list"), params).context["problems"].object_list]

    assert ids(sort="title") == [problem.id, easy.id, hard.id]  # "A + B" < "Bbb" < "Zzz"
    assert ids(sort="title", dir="desc") == [hard.id, easy.id, problem.id]
    assert ids(sort="difficulty")[0] == easy.id and ids(sort="difficulty", dir="desc")[0] == hard.id
    assert ids(sort="bogus") == ids()  # unknown column falls back to id


def test_list_pagination_keeps_filters_and_shows_page_numbers(client, problem):
    author = problem.author
    for i in range(65):
        Problem.objects.create(slug=f"p{i}", title=f"P{i}", statement_md="x", author=author)
    r = client.get(reverse("problems:list"), {"q": "P", "sort": "title", "page": 2})
    html = r.content.decode()
    assert 'aria-current="page">2<' in html
    assert "?q=P&amp;sort=title&amp;page=3" in html
    assert "31–60 / 65" in html


def test_list_paginates_at_30(client, problem):
    author = problem.author
    for i in range(35):
        Problem.objects.create(slug=f"p{i}", title=f"P{i}", statement_md="x", author=author)
    r = client.get(reverse("problems:list"))
    assert r.status_code == 200
    assert len(r.context["problems"]) == 30
    assert r.context["problems"].paginator.num_pages == 2


def test_list_search_by_title(client, problem):
    Problem.objects.create(slug="other", title="Binary Search", statement_md="x", author=problem.author)
    r = client.get(reverse("problems:list"), {"q": "Binary"})
    assert b"Binary Search" in r.content
    assert b"A + B" not in r.content


def test_list_filter_by_tag(client, problem):
    dp = Tag.objects.create(name="dp")
    tagged = Problem.objects.create(slug="tagged", title="DP Problem", statement_md="x", author=problem.author)
    tagged.tags.add(dp)
    r = client.get(reverse("problems:list"), {"tag": "dp"})
    assert b"DP Problem" in r.content
    assert b"A + B" not in r.content


def _sql_problem(author, **dataset):
    from .models import SQLDataset

    p = Problem.objects.create(slug="sql-older", title="Kattalar", statement_md="x", author=author,
                               kind=Problem.Kind.SQL, output_md="Bitta ustun: `name`.")
    SQLDataset.objects.create(problem=p, schema_sql="CREATE TABLE users(id INTEGER, name TEXT, age INTEGER);",
                              seed_sql="INSERT INTO users VALUES (1,'ali',20),(2,'vali',25);",
                              expected_result="vali\n", **dataset)
    return p


def test_list_filters_by_kind_and_marks_sql_problems(client, problem):
    sql = _sql_problem(problem.author)
    sql.tags.add(Tag.objects.create(name="where", kind=Tag.Kind.SQL))
    problem.tags.add(Tag.objects.get_or_create(name="math")[0])
    everything = client.get(reverse("problems:list")).content.decode()
    assert "A + B" in everything and "Kattalar" in everything and everything.count('class="ca-kind-sql"') == 1
    assert 'class="is-sql"' in everything and '<optgroup label="SQL">' in everything
    only_sql = client.get(reverse("problems:list"), {"kind": "sql"})
    assert [p.slug for p in only_sql.context["problems"]] == ["sql-older"]
    assert [(label, [t.name for t in tags]) for label, tags in only_sql.context["tag_groups"]] == [("SQL", ["where"])]
    only_code = client.get(reverse("problems:list"), {"kind": "code"})
    assert [p.slug for p in only_code.context["problems"]] == ["a-plus-b"]


def test_sql_problem_page_draws_the_tables_and_the_expected_result(client, problem):
    sql = _sql_problem(problem.author, check_seed_sql="INSERT INTO users VALUES (3,'guli',30);",
                       check_expected_result="guli\n", ordered=True)
    client.force_login(User.objects.create_user("student", password="x"))
    page = client.get(reverse("problems:detail", args=[sql.slug])).content.decode()
    assert '<span translate="no">users</span>' in page
    assert '<th translate="no">age <span class="ca-sql-type">integer</span></th>' in page
    assert '<td class="font-mono">vali</td>' in page  # sample row and expected result
    assert "guli" not in page  # the hidden check data stays hidden
    assert "aynan shu tartibda" in page and "yashirin, kattaroq" in page
    assert 'id="trial-btn"' in page and 'id="trial-stdin"' not in page
    assert "MB</span>" not in page  # no memory limit on a query


@pytest.mark.django_db
def test_problem_page_offers_to_join_running_contest(client):
    from django.utils import timezone

    from apps.contests.models import Contest, ContestProblem, Participation

    staff = User.objects.create_user("teacher", password="x", is_staff=True)
    ali = User.objects.create_user("ali", password="x")
    p = Problem.objects.create(slug="p", title="P", statement_md="x", author=staff)
    c = Contest.objects.create(title="Live", start=timezone.now() - timezone.timedelta(minutes=5),
                               end=timezone.now() + timezone.timedelta(hours=1))
    ContestProblem.objects.create(contest=c, problem=p, label="A")
    client.force_login(ali)
    assert "Musobaqaga qo‘shilish" in client.get(reverse("problems:detail", args=["p"])).content.decode()
    Participation.objects.create(user=ali, contest=c)
    assert "Musobaqaga qo‘shilish" not in client.get(reverse("problems:detail", args=["p"])).content.decode()


# ---- dynamic points (difficulty band + solve rate) -----------------------------

def test_compute_points_keeps_band_max_below_min_attempts():
    assert compute_points("easy", solvers=1, attempts=MIN_ATTEMPTS - 1) == BANDS["easy"][1]


def test_compute_points_drops_toward_band_min_for_high_success_rate():
    band_min, band_max = BANDS["easy"]
    points = compute_points("easy", solvers=12, attempts=12)  # 100% success, MIN_ATTEMPTS met
    assert points == band_min


def test_compute_points_stays_near_band_max_for_low_success_rate():
    band_min, band_max = BANDS["easy"]
    points = compute_points("easy", solvers=1, attempts=20)  # 5% success
    assert points > (band_min + band_max) / 2


def test_compute_points_matches_user_example_96_percent_on_easy():
    band_min, band_max = BANDS["easy"]
    points = compute_points("easy", solvers=int(round(12 * 0.96)), attempts=12)
    assert band_min <= points < band_max // 2


def test_compute_points_rounds_to_nearest_5():
    assert compute_points("medium", solvers=7, attempts=13) % 5 == 0


def test_compute_points_never_leaves_its_band():
    band_min, band_max = BANDS["hard"]
    for solvers, attempts in [(0, 0), (0, 100), (100, 100), (50, 100)]:
        points = compute_points("hard", solvers, attempts)
        assert band_min <= points <= band_max


@pytest.mark.django_db
def test_recalc_points_command_updates_from_real_submissions():
    from django.core.management import call_command

    from apps.submissions.models import Submission, UserProblemSolved

    author = User.objects.create_user("teacher", password="x", role="teacher")
    p = Problem.objects.create(slug="easy-one", title="Easy One", statement_md="x", author=author,
                               difficulty=Problem.Difficulty.EASY, status=Problem.Status.APPROVED)
    python = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    band_min, band_max = BANDS["easy"]
    assert p.points == 100  # model default, pre-recalc

    for i in range(12):
        u = User.objects.create_user(f"u{i}", password="x")
        verdict = "AC" if i < 11 else "WA"  # ~92% success, comfortably below MIN_ATTEMPTS-gate and above midpoint
        sub = Submission.objects.create(user=u, problem=p, language=python, source="x", verdict=verdict)
        if verdict == "AC":
            UserProblemSolved.objects.create(user=u, problem=p, first_ac_submission=sub)

    call_command("recalc_points")
    p.refresh_from_db()
    assert band_min <= p.points < band_max
    assert p.points % 5 == 0

    points_after_first_run = p.points
    call_command("recalc_points")  # idempotent: same inputs, same output
    p.refresh_from_db()
    assert p.points == points_after_first_run


@pytest.mark.django_db
def test_recalc_points_makes_practice_points_live():
    from django.core.management import call_command

    from apps.submissions.models import Submission
    from apps.submissions.solves import refresh_solves

    author = User.objects.create_user("teacher", password="x", role="teacher")
    ali = User.objects.create_user("ali", password="x")
    p = Problem.objects.create(slug="p", title="P", statement_md="x", author=author, points=999,
                               difficulty=Problem.Difficulty.EASY, status=Problem.Status.APPROVED)
    python = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    Submission.objects.create(user=ali, problem=p, language=python, source="x", verdict="AC")
    refresh_solves(p.pk)
    ali.refresh_from_db()
    assert ali.practice_points == 999

    call_command("recalc_points")

    p.refresh_from_db()
    ali.refresh_from_db()
    assert p.points != 999 and ali.practice_points == p.points


# ---- problem rating + solution leaderboards ---------------------------------------------------

def _ac(user, problem, lang, exec_ms, source):
    from apps.submissions.models import Submission, UserProblemSolved
    s = Submission.objects.create(user=user, problem=problem, language=lang, source=source,
                                  verdict="AC", exec_ms=exec_ms)
    UserProblemSolved.objects.get_or_create(user=user, problem=problem, defaults={"first_ac_submission": s})
    return s


@pytest.fixture
def py(db):
    return Language.objects.create(code="python", name="Python 3", docker_image="i", run_cmd="r")


def test_only_solver_can_rate_and_stars_are_clamped(client, problem, py):
    from .models import ProblemRating
    ali = User.objects.create_user("ali", password="x")
    client.force_login(ali)
    url = reverse("problems:rate", args=[problem.slug])
    assert client.post(url, {"stars": 5}).status_code == 404
    _ac(ali, problem, py, 10, "print(1)")
    client.post(url, {"stars": 4})
    client.post(url, {"stars": 9})  # ignored
    assert ProblemRating.objects.get(user=ali, problem=problem).stars == 4
    assert "4.0" in client.get(reverse("problems:detail", args=[problem.slug])).content.decode()


def test_leaders_best_per_user_by_time_and_length(client, problem, py):
    from apps.problems.views import leaders
    ali, vali = User.objects.create_user("ali", password="x"), User.objects.create_user("vali", password="x")
    _ac(ali, problem, py, 50, "x" * 10)
    _ac(ali, problem, py, 20, "x" * 99)   # ali's fastest
    _ac(vali, problem, py, 30, "x" * 5)
    assert [(s.user.username, s.exec_ms) for s in leaders(problem, "time")] == [("ali", 20), ("vali", 30)]
    assert [(s.user.username, s.code_len) for s in leaders(problem, "length")] == [("vali", 5), ("ali", 10)]
    r = client.get(reverse("problems:leaders", args=[problem.slug]) + "?by=length")
    assert r.status_code == 200 and r.content.decode().index("vali") < r.content.decode().index(">ali<")


def test_solutions_hidden_during_running_contest(client, problem, py):
    ali, vali = User.objects.create_user("ali", password="x"), User.objects.create_user("vali", password="x")
    theirs = _ac(vali, problem, py, 10, "secret")
    _ac(ali, problem, py, 10, "mine")
    client.force_login(ali)
    code_url = reverse("submissions:detail", args=[theirs.pk])
    assert client.get(code_url).status_code == 200  # solver may read others' AC code
    now = timezone.now()
    c = Contest.objects.create(title="C", start=now - timezone.timedelta(hours=1), end=now + timezone.timedelta(hours=1))
    ContestProblem.objects.create(contest=c, problem=problem, label="A", points=100, order=0)
    assert client.get(code_url).status_code == 404
    assert client.get(reverse("problems:leaders", args=[problem.slug])).status_code == 404


def test_non_solver_cannot_read_others_code(client, problem, py):
    theirs = _ac(User.objects.create_user("vali", password="x"), problem, py, 10, "secret")
    client.force_login(User.objects.create_user("ali", password="x"))
    assert client.get(reverse("submissions:detail", args=[theirs.pk])).status_code == 404


# ---- hints and editorials ---------------------------------------------------------------------

def _hints(problem, *costs):
    from .models import ProblemHint

    return [ProblemHint.objects.create(problem=problem, order=i, body_md=f"Maslahat {i + 1}", cost_pct=c)
            for i, c in enumerate(costs)]


@pytest.mark.django_db
def test_hints_open_in_order_and_cost_points_only_before_the_solve(client, problem):
    from apps.submissions.models import Submission, UserProblemSolved
    from apps.submissions.solves import refresh_solves

    from .models import HintUnlock

    problem.points = 100
    problem.save()
    h1, h2, h3 = _hints(problem, 20, 30, 50)
    ali = User.objects.create_user("ali", password="x")
    client.force_login(ali)
    url = lambda h: reverse("problems:hint", args=[problem.slug, h.pk])  # noqa: E731

    assert client.post(url(h2)).status_code == 400  # hint 1 first
    page = client.get(reverse("problems:detail", args=[problem.slug])).content.decode()
    assert "Maslahat 1" not in page and "20%" in page  # locked, cost shown up front
    assert client.post(url(h1)).status_code == 302
    assert "Maslahat 1" in client.get(reverse("problems:detail", args=[problem.slug])).content.decode()
    client.post(url(h1))  # opening twice costs once
    assert HintUnlock.objects.filter(user=ali).count() == 1

    lang = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    Submission.objects.create(user=ali, problem=problem, language=lang, source="x", verdict="AC")
    refresh_solves(problem.pk, [ali.pk])
    ali.refresh_from_db()
    assert UserProblemSolved.objects.get(user=ali).hint_pct == 20 and ali.practice_points == 80

    client.post(url(h2))  # after the solve: free
    client.post(url(h3))
    refresh_solves(problem.pk, [ali.pk])
    ali.refresh_from_db()
    assert ali.practice_points == 80


@pytest.mark.django_db
def test_hint_costs_are_capped(client, problem):
    from apps.submissions.models import Submission
    from apps.submissions.solves import refresh_solves

    problem.points = 100
    problem.save()
    ali = User.objects.create_user("ali", password="x")
    client.force_login(ali)
    for h in _hints(problem, 50, 50):
        client.post(reverse("problems:hint", args=[problem.slug, h.pk]))
    lang = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    Submission.objects.create(user=ali, problem=problem, language=lang, source="x", verdict="AC")
    refresh_solves(problem.pk, [ali.pk])
    ali.refresh_from_db()
    assert ali.practice_points == 10


@pytest.mark.django_db
def test_hints_are_locked_while_the_problem_is_in_a_contest(client, problem):
    (h1,) = _hints(problem, 10)
    c = Contest.objects.create(title="Soon", start=timezone.now() + timezone.timedelta(days=1),
                               end=timezone.now() + timezone.timedelta(days=2))
    ContestProblem.objects.create(contest=c, problem=problem, label="A")
    ali = User.objects.create_user("ali", password="x")
    client.force_login(ali)
    assert client.post(reverse("problems:hint", args=[problem.slug, h1.pk])).status_code in (400, 404)
    Contest.objects.filter(pk=c.pk).update(start=timezone.now() - timezone.timedelta(hours=1),
                                           end=timezone.now() + timezone.timedelta(hours=1))
    Participation.objects.create(user=ali, contest=c)
    assert client.post(reverse("problems:hint", args=[problem.slug, h1.pk])).status_code == 400


@pytest.mark.django_db
def test_editorial_opens_after_the_solve(client, problem):
    from apps.submissions.models import Submission
    from apps.submissions.solves import refresh_solves

    problem.editorial_md = "Javob: **a + b**"
    problem.save()
    ali = User.objects.create_user("ali", password="x")
    client.force_login(ali)
    page = client.get(reverse("problems:detail", args=[problem.slug])).content.decode()
    assert "<strong>a + b</strong>" not in page and "Yechim tahlili" in page
    lang = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    Submission.objects.create(user=ali, problem=problem, language=lang, source="x", verdict="AC")
    refresh_solves(problem.pk, [ali.pk])
    assert "<strong>a + b</strong>" in client.get(reverse("problems:detail", args=[problem.slug])).content.decode()
    client.force_login(problem.author)
    assert "<strong>a + b</strong>" in client.get(reverse("problems:detail", args=[problem.slug])).content.decode()


@pytest.mark.django_db
def test_staff_edit_hints_and_editorial_on_the_problem_form(client, problem):
    staff = User.objects.create_user("boss", password="x", is_staff=True)
    client.force_login(staff)
    data = {"title": problem.title, "statement_md": "x", "difficulty": "easy", "kind": "code",
            "tl_ms": "1000", "ml_mb": "256", "points": "100", "is_public": "on", "editorial_md": "Tahlil",
            "testcases-TOTAL_FORMS": "2", "testcases-INITIAL_FORMS": "2",
            "testcases-MIN_NUM_FORMS": "0", "testcases-MAX_NUM_FORMS": "1000",
            "hints-TOTAL_FORMS": "2", "hints-INITIAL_FORMS": "0", "hints-MIN_NUM_FORMS": "0",
            "hints-MAX_NUM_FORMS": "1000",
            "hints-0-order": "0", "hints-0-body_md": "Birinchi", "hints-0-cost_pct": "10",
            "hints-1-order": "1", "hints-1-body_md": "Ikkinchi", "hints-1-cost_pct": "150"}
    for i, tc in enumerate(problem.testcases.all()):
        data |= {f"testcases-{i}-id": str(tc.pk), f"testcases-{i}-input": tc.input,
                 f"testcases-{i}-expected": tc.expected, f"testcases-{i}-order": str(tc.order)}
    r = client.post(reverse("moderation:problem_edit", args=[problem.pk]), data)
    assert r.status_code == 200 and not problem.hints.exists()  # 150% is refused
    data["hints-1-cost_pct"] = "25"
    r = client.post(reverse("moderation:problem_edit", args=[problem.pk]), data)
    problem.refresh_from_db()
    assert r.status_code == 302 and problem.editorial_md == "Tahlil"
    assert list(problem.hints.values_list("body_md", "cost_pct")) == [("Birinchi", 10), ("Ikkinchi", 25)]


# ---- skill map and next problem -----------------------------------------------------------------

@pytest.fixture
def catalog(db):
    """Tags dp (4 problems) and math (3); one hidden and one contest-locked extra."""
    author = User.objects.create_user("author", password="x")
    dp, math = Tag.objects.create(name="dp"), Tag.objects.get(name="math")
    made = {}
    for slug, tag, diff in [("dp1", dp, "easy"), ("dp2", dp, "easy"), ("dp3", dp, "medium"), ("dp4", dp, "hard"),
                            ("m1", math, "easy"), ("m2", math, "easy"), ("m3", math, "easy")]:
        p = Problem.objects.create(slug=slug, title=slug, statement_md="x", author=author, difficulty=diff)
        p.tags.add(tag)
        made[slug] = p
    hidden = Problem.objects.create(slug="h", title="h", statement_md="x", author=author, is_public=False)
    hidden.tags.add(dp)
    soon = Problem.objects.create(slug="soon", title="soon", statement_md="x", author=author)
    soon.tags.add(dp)
    c = Contest.objects.create(title="C", start=timezone.now() + timezone.timedelta(days=1),
                               end=timezone.now() + timezone.timedelta(days=2))
    ContestProblem.objects.create(contest=c, problem=soon, label="A")
    return made


def _solve(user, *problems):
    from apps.submissions.models import Submission, UserProblemSolved

    lang, _ = Language.objects.get_or_create(code="python", defaults={"name": "Python 3", "docker_image": "x",
                                                                       "run_cmd": "x"})
    for p in problems:
        s = Submission.objects.create(user=user, problem=p, language=lang, source="x", verdict="AC")
        UserProblemSolved.objects.create(user=user, problem=p, first_ac_submission=s)


@pytest.mark.django_db
def test_skill_map_counts_open_problems_per_tag(catalog):
    from .skills import skill_map

    ali = User.objects.create_user("ali", password="x")
    _solve(ali, catalog["m1"], catalog["m2"], catalog["dp1"])
    got = {row["tag"].name: (row["solved"], row["total"]) for row in skill_map(ali)}
    assert got == {"dp": (1, 4), "math": (2, 3)}  # hidden and contest-locked don't count


@pytest.mark.django_db
def test_next_problems_come_from_the_weakest_tag_at_the_users_level(catalog):
    from .skills import next_problems

    ali = User.objects.create_user("ali", password="x")
    _solve(ali, catalog["m1"], catalog["m2"], catalog["dp1"])  # weakest: dp (1/4); level: easy
    picks = next_problems(ali)
    assert [p.slug for p, _ in picks][:2] == ["dp2", "dp3"]  # easy first, then one step up; never dp4 (hard)
    assert all(reason == "dp" for _, reason in picks[:2])
    assert {p.slug for p, _ in picks} <= {"dp2", "dp3", "m3"}
    assert "dp4" not in {p.slug for p, _ in picks}


@pytest.mark.django_db
def test_problem_list_and_profile_show_them(client, catalog):
    ali = User.objects.create_user("ali", password="x")
    _solve(ali, catalog["m1"])
    client.force_login(ali)
    page = client.get(reverse("problems:list")).content.decode()
    assert "Keyingi masala" in page
    assert "Mavzular" in client.get(reverse("profile", args=["ali"])).content.decode()


# ---- daily problem and streak -------------------------------------------------------------------

@pytest.mark.django_db
def test_daily_problem_is_picked_once_a_day_from_fresh_open_problems(catalog):
    import datetime

    from .daily import daily_for
    from .models import DailyProblem

    day = datetime.date(2030, 1, 7)  # a Monday: easy
    first = daily_for(day)
    assert first is not None and daily_for(day).pk == first.pk and DailyProblem.objects.count() == 1
    assert first.problem.difficulty == "easy" and first.problem.slug not in ("h", "soon")
    # the next 60 days never repeat a problem while fresh ones of the day's level remain
    easy = {p.pk for p in catalog.values() if p.difficulty == "easy"}
    used = [daily_for(day + datetime.timedelta(days=7 * i)).problem.pk for i in range(len(easy))]
    assert sorted(used) == sorted(easy)


@pytest.mark.django_db
def test_daily_solves_give_bonus_and_streaks(catalog):
    import datetime

    from apps.submissions.models import Submission
    from apps.submissions.solves import refresh_solves

    from .daily import DAILY_BONUS, daily_for, streaks
    from .models import DailySolve

    ali = User.objects.create_user("ali", password="x")
    lang = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    today = timezone.localdate()
    for back in (0, 1, 2, 5):  # a 3-day run up to today, and an older single day
        day = today - datetime.timedelta(days=back)
        d = daily_for(day)
        at = timezone.make_aware(datetime.datetime.combine(day, datetime.time(12, 0)))
        s = Submission.objects.create(user=ali, problem=d.problem, language=lang, source="x", verdict="AC")
        Submission.objects.filter(pk=s.pk).update(created=at)
        refresh_solves(d.problem_id, [ali.pk])
    assert DailySolve.objects.filter(user=ali).count() == 4
    assert streaks(ali) == (3, 3)
    ali.refresh_from_db()
    solved_points = sum(p.points for p in Problem.objects.filter(userproblemsolved__user=ali))
    assert ali.practice_points == solved_points + 4 * DAILY_BONUS

    # an AC on another day than the problem's day is not a daily solve; a rejudge that
    # takes the AC away takes the daily solve and its bonus away too
    Submission.objects.filter(user=ali, problem=daily_for(today).problem).update(verdict="WA")
    refresh_solves(daily_for(today).problem_id, [ali.pk])
    assert DailySolve.objects.filter(user=ali).count() == 3
    assert streaks(ali) == (2, 2)  # yesterday's run is still alive today


@pytest.mark.django_db
def test_problem_list_shows_the_daily_problem(client, catalog):
    ali = User.objects.create_user("ali", password="x")
    client.force_login(ali)
    r = client.get(reverse("problems:list"))
    assert "Kun masalasi" in r.content.decode()
    daily = r.context["daily"]
    assert daily.problem.pk not in [p.pk for p, _ in r.context["next_picks"]]


@pytest.mark.django_db
def test_next_problems_reach_down_a_level_for_the_strongest(catalog):
    from .skills import next_problems

    ali = User.objects.create_user("ali", password="x")
    _solve(ali, catalog["dp4"])  # only a hard one solved: nothing is above hard
    picks = [p.slug for p, _ in next_problems(ali)]
    assert picks and picks[0] == "dp3" and len(picks) == 1  # dp3 is the only unsolved medium; easy is two down


# ---- redesign: week strip, list filters, profile honesty ---------------------------------------

@pytest.mark.django_db
def test_week_strip_marks_this_weeks_daily_solves(catalog):
    from apps.submissions.models import Submission
    from apps.submissions.solves import refresh_solves

    from .daily import daily_for, week_strip

    ali = User.objects.create_user("ali", password="x")
    lang = Language.objects.create(code="python", name="Python 3", docker_image="x", run_cmd="x")
    d = daily_for()
    Submission.objects.create(user=ali, problem=d.problem, language=lang, source="x", verdict="AC")
    refresh_solves(d.problem_id, [ali.pk])
    week, today = week_strip(ali), timezone.localdate().weekday()
    assert [w["label"] for w in week] == ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]
    assert week[today]["today"] and week[today]["done"] and sum(w["done"] for w in week) == 1
    assert all(w["future"] for w in week[today + 1:]) and not any(w["future"] for w in week[:today + 1])


@pytest.mark.django_db
def test_difficulty_chips_count_what_a_click_would_show(client, catalog):
    from .models import ProblemRating

    r = client.get(reverse("problems:list"), {"tag": "dp", "difficulty": "easy"})
    chips = {c["value"]: c["n"] for c in r.context["level_chips"]}
    # the hidden and the contest-locked dp problems are not counted; other levels still are
    assert chips == {"beginner": 0, "easy": 2, "medium": 1, "hard": 1} and r.context["level_total"] == 4
    assert len(r.context["problems"].object_list) == 2
    # nobody rated anything yet: no column of dashes
    assert r.context["any_rated"] is False and ">Baho<" not in r.content.decode()
    ProblemRating.objects.create(user=User.objects.get(username="author"), problem=catalog["dp1"], stars=4)
    assert ">Baho<" in client.get(reverse("problems:list")).content.decode()


@pytest.mark.django_db
def test_profile_explains_solves_an_upcoming_contest_hides(client, catalog):
    ali = User.objects.create_user("ali", password="x")
    _solve(ali, catalog["m1"], Problem.objects.get(slug="soon"))
    r = client.get(reverse("profile", args=["ali"]))
    assert r.context["solved_shown"] == 1 and r.context["solved_hidden"] == 1
    assert "yechilgan 2 ta masala" in r.content.decode() and "kelgusi musobaqada" in r.content.decode()


def test_standard_topics_migration_merges_variants_and_drops_the_rest(db):
    import importlib

    from django.apps import apps as django_apps

    migration = importlib.import_module("apps.problems.migrations.0013_standard_topics")
    author = User.objects.create_user("author", password="x")
    p1 = Problem.objects.create(slug="p1", title="p1", statement_md="x", author=author)
    p2 = Problem.objects.create(slug="p2", title="p2", statement_md="x", author=author)
    p1.tags.add(*(Tag.objects.create(name=n) for n in ["sikl", "beginner", "Yig‘indi"]))
    p2.tags.add(Tag.objects.get(name="loops"), *(Tag.objects.create(name=n) for n in ["For", "Binary Search"]))

    migration.standardize(django_apps, None)

    assert set(Tag.objects.values_list("name", flat=True)) == set(migration.TOPICS)
    assert set(p1.tags.values_list("name", flat=True)) == {"loops", "math"}  # "beginner" is a level, not a topic
    assert set(p2.tags.values_list("name", flat=True)) == {"loops", "binary-search"}


@pytest.mark.django_db
def test_header_streak_pill_shows_the_run_and_whether_today_is_solved(client, catalog):
    import datetime

    from .daily import daily_for
    from .models import DailySolve

    assert b"ca-streak" not in client.get(reverse("problems:list")).content  # guests get no pill
    ali = User.objects.create_user("ali", password="x")
    client.force_login(ali)
    today = timezone.localdate()
    DailySolve.objects.create(user=ali, daily=daily_for(today - datetime.timedelta(days=1)))
    daily = daily_for(today)
    page = client.get(reverse("submissions:mine")).content.decode()  # any page with the header
    assert 'class="ca-streak is-risk"' in page and '<span class="tabular">1</span>' in page
    assert reverse("problems:detail", args=[daily.problem.slug]) in page
    DailySolve.objects.create(user=ali, daily=daily)
    page = client.get(reverse("submissions:mine")).content.decode()
    assert 'class="ca-streak is-done"' in page and '<span class="tabular">2</span>' in page


@pytest.mark.django_db
def test_suggest_finds_what_the_list_shows_and_nothing_hidden(client):
    from django.contrib.auth import get_user_model
    from django.urls import reverse

    from apps.problems.models import Problem
    author = get_user_model().objects.create_user("sugg", password="x")
    Problem.objects.create(slug="ikki-son", title="Ikki son", statement_md="x", author=author)
    Problem.objects.create(slug="yashirin", title="Ikki yashirin", statement_md="x", author=author, is_public=False)
    Problem.objects.create(slug="sonlar-ikki", title="Sonlar ikki marta", statement_md="x", author=author)
    r = client.get(reverse("problems:suggest"), {"q": "ikki"}).json()["results"]
    assert [x["title"] for x in r] == ["Ikki son", "Sonlar ikki marta"]  # title-prefix first, hidden never
    assert client.get(reverse("problems:suggest"), {"q": ""}).json() == {"results": []}


@pytest.mark.django_db
def test_practice_pack_adds_25_open_problems_once_and_repeats_nothing_on_the_portal():
    from io import StringIO

    from django.core.management import call_command

    from apps.accounts.models import User
    from apps.problems.management.commands import add_practice_pack_1, seed_problems, seed_story_problems
    from apps.problems.models import Problem

    User.objects.create_superuser("admin", password="x")
    call_command("add_practice_pack_1", "--dry-run", stdout=StringIO())
    assert not Problem.objects.filter(slug__startswith="p1-").exists()

    call_command("add_practice_pack_1", stdout=StringIO())
    pack = Problem.objects.filter(slug__startswith="p1-")
    assert pack.count() == 25 and not pack.exclude(is_public=True, status=Problem.Status.APPROVED).exists()
    assert set(pack.values_list("difficulty", flat=True)) == {"beginner", "easy"}
    assert all(p.testcases.count() >= 20 and p.testcases.filter(is_sample=True).count() == 2 for p in pack)

    call_command("add_practice_pack_1", stdout=StringIO())  # re-run: nothing new
    assert Problem.objects.filter(slug__startswith="p1-").count() == 25

    seeded = {s.title for mod in (seed_problems, seed_story_problems) for v in vars(mod).values()
              if isinstance(v, list) for s in v if hasattr(s, "title")}
    assert not seeded & {s["title"] for s in add_practice_pack_1.PROBLEMS}


def _solve_history(problem, tried, solved, prefix="s"):
    """`tried` students submitted to `problem`, the first `solved` of them with an AC."""
    from apps.submissions.models import Submission, UserProblemSolved

    py = Language.objects.get_or_create(code="python", defaults=dict(name="Python 3", docker_image="x", run_cmd="x"))[0]
    users = []
    for i in range(tried):
        u = User.objects.create_user(f"{prefix}{i}", password="x")
        s = Submission.objects.create(user=u, problem=problem, language=py, source="x",
                                      verdict="AC" if i < solved else "WA")
        if i < solved:
            UserProblemSolved.objects.create(user=u, problem=problem, first_ac_submission=s)
        users.append(u)
    return users


@pytest.mark.django_db
def test_points_follow_the_difficulty_at_once():
    from apps.submissions.solves import sync_practice_points

    author = User.objects.create_user("pa", password="x")
    p = Problem.objects.create(slug="pp", title="P", statement_md="x", author=author, difficulty="beginner")
    assert p.points == BANDS["beginner"][1]  # not the old flat 100
    solver = _solve_history(p, 1, 1)[0]
    sync_practice_points([solver.pk])
    p.difficulty = "medium"
    p.save(update_fields=["difficulty"])
    p.refresh_from_db()
    solver.refresh_from_db()
    assert p.points == BANDS["medium"][1] and solver.practice_points == BANDS["medium"][1]


@pytest.mark.django_db
def test_review_difficulty_moves_a_label_one_step_towards_how_students_did():
    from io import StringIO

    from django.core.management import call_command

    author = User.objects.create_user("ra", password="x")
    too_easy = Problem.objects.create(slug="looks-hard", title="Aslida oson", statement_md="x", author=author, difficulty="hard")
    _solve_history(too_easy, 10, 9, "a")  # 90%: the data says beginner
    fine = Problem.objects.create(slug="fair", title="Mos", statement_md="x", author=author, difficulty="medium")
    _solve_history(fine, 10, 4, "b")      # 40%: medium
    thin = Problem.objects.create(slug="new", title="Yangi", statement_md="x", author=author, difficulty="hard")
    _solve_history(thin, 3, 3, "c")       # too few to judge
    staff = User.objects.create_user("st", password="x", is_staff=True)
    read = Problem.objects.create(slug="sort-three", title="Uchta son", statement_md="x", author=staff, difficulty="medium")

    out = StringIO()
    call_command("review_difficulty", stdout=out)
    report = out.getvalue()
    assert "Aslida oson" in report and "Uchta son" in report and "Mos" not in report.split("mos emas:")[1]
    assert Problem.objects.get(pk=too_easy.pk).difficulty == "hard"  # only a report without --apply

    call_command("review_difficulty", "--apply", stdout=StringIO())
    assert Problem.objects.get(pk=too_easy.pk).difficulty == "medium"  # one step, not straight to beginner
    assert Problem.objects.get(pk=read.pk).difficulty == "easy"
    assert Problem.objects.get(pk=fine.pk).difficulty == "medium" and Problem.objects.get(pk=thin.pk).difficulty == "hard"
