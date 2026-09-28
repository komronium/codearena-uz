"""Medium and hard problems: the catalog's first that need an algorithm, not just a loop
(prefix sums, two pointers, binary search, a stack, DP, BFS, Dijkstra, a segment tree,
Kruskal). Inputs are big enough that the naive solution runs out of time.

Each spec has samples, a generator and a reference solution; tests are materialised
deterministically: small ones to catch wrong answers, then a few of the maximum size.
Re-running is safe: problems are matched by slug and their tests are rebuilt.
"""
import heapq
import random
from bisect import bisect_left, bisect_right
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User
from apps.problems.models import Problem, Tag, TestCase

D = Problem.Difficulty
# Upper bound handed to the generator per test after the samples: small, medium, then maximum.
SIZES = ["small"] * 8 + ["medium"] * 6 + ["max"] * 3


@dataclass
class Spec:
    slug: str
    title: str
    statement: str
    input: str
    output: str
    gen: Callable[[random.Random, str], str]  # (rng, size) -> stdin text
    solve: Callable[[str], str]               # stdin text -> expected stdout
    samples: list[str]
    difficulty: str
    tags: list[str]
    tl_ms: int = 1000
    ml_mb: int = 64
    edge: list[str] = field(default_factory=list)  # fixed corner cases, judged but not shown


def _n(rng: random.Random, size: str, big: int) -> int:
    return {"small": rng.randint(1, 8), "medium": rng.randint(9, 1000), "max": big}[size]


def _join(xs) -> str:
    return " ".join(map(str, xs))


# ---- medium ------------------------------------------------------------------

def _range(r, n, size):
    """1 <= l <= r <= n; the maximum tests ask for long ranges, where a loop per query is slowest."""
    if size == "max":
        return r.randint(1, n // 10 + 1), r.randint(n - n // 10, n)
    lo, hi = sorted((r.randint(1, n), r.randint(1, n)))
    return lo, hi


def _gen_prefix(r, size):
    n, q = _n(r, size, 100_000), _n(r, size, 100_000)
    a = [r.randint(-10**9, 10**9) for _ in range(n)]
    qs = [_range(r, n, size) for _ in range(q)]
    return f"{n} {q}\n{_join(a)}\n" + "".join(f"{lo} {hi}\n" for lo, hi in qs)


def _solve_prefix(s):
    it = iter(s.split())
    n, q = int(next(it)), int(next(it))
    pre = [0]
    for _ in range(n):
        pre.append(pre[-1] + int(next(it)))
    return "".join(f"{pre[int(hi)] - pre[int(lo) - 1]}\n" for lo, hi in ((next(it), next(it)) for _ in range(q)))


def _gen_window(r, size):
    n = _n(r, size, 100_000)
    a = [r.randint(1, 10_000) for _ in range(n)]
    budget = r.randint(1, max(1, sum(a) // r.choice([1, 2, 5, 50])))
    return f"{n} {budget}\n{_join(a)}\n"


def _solve_window(s):
    n, budget, *a = map(int, s.split())
    best = lo = total = 0
    for hi in range(n):
        total += a[hi]
        while total > budget:
            total -= a[lo]
            lo += 1
        best = max(best, hi - lo + 1)
    return f"{best}\n"


def _gen_prices(r, size):
    n, q = _n(r, size, 100_000), _n(r, size, 100_000)
    top = r.choice([10, 1000, 10**9])
    return (f"{n}\n{_join(r.randint(1, top) for _ in range(n))}\n"
            f"{q}\n{_join(r.randint(0, top + 1) for _ in range(q))}\n")


def _solve_prices(s):
    it = iter(s.split())
    n = int(next(it))
    prices = sorted(int(next(it)) for _ in range(n))
    q = int(next(it))
    return _join(bisect_right(prices, int(next(it))) for _ in range(q)) + "\n"


_PAIRS = {")": "(", "]": "[", "}": "{"}


def _gen_brackets(r, size):
    n = _n(r, size, 100_000)
    if r.random() < 0.5:  # a balanced one, maybe with one character spoiled
        stack, out = [], []
        for _ in range(n):
            if stack and (r.random() < 0.5 or len(out) + len(stack) >= n):
                out.append({"(": ")", "[": "]", "{": "}"}[stack.pop()])
            else:
                stack.append(r.choice("([{"))
                out.append(stack[-1])
        out += [{"(": ")", "[": "]", "{": "}"}[c] for c in reversed(stack)]
        if r.random() < 0.5:
            out[r.randrange(len(out))] = r.choice("()[]{}")
        return "".join(out) + "\n"
    return "".join(r.choice("()[]{}") for _ in range(n)) + "\n"


def _solve_brackets(s):
    stack = []
    for c in s.strip():
        if c in "([{":
            stack.append(c)
        elif not stack or stack.pop() != _PAIRS[c]:
            return "NO\n"
    return "YES\n" if not stack else "NO\n"


def _gen_coins(r, size):
    n = {"small": r.randint(1, 4), "medium": r.randint(5, 30), "max": 100}[size]
    target = {"small": r.randint(0, 50), "medium": r.randint(51, 3000), "max": 10_000}[size]
    low = r.choice([1, 2, 7, 50])  # without a 1 some sums can't be paid
    return f"{n} {target}\n{_join(r.randint(low, 10_000 if size == 'max' else 60) for _ in range(n))}\n"


def _solve_coins(s):
    n, target, *coins = map(int, s.split())
    inf = target + 1
    best = [0] + [inf] * target
    for c in set(coins):
        for x in range(c, target + 1):
            if best[x - c] + 1 < best[x]:
                best[x] = best[x - c] + 1
    return f"{best[target] if best[target] < inf else -1}\n"


# ---- hard --------------------------------------------------------------------

def _gen_lis(r, size):
    n = _n(r, size, 100_000)
    top = r.choice([5, 1000, 10**9])
    if size == "max" and r.random() < 0.5:  # a long answer: a noisy rising line
        return f"{n}\n{_join(i * 10 + r.randint(-30, 30) for i in range(n))}\n"
    return f"{n}\n{_join(r.randint(-top, top) for _ in range(n))}\n"


def _solve_lis(s):
    n, *a = map(int, s.split())
    tails = []
    for x in a:
        i = bisect_left(tails, x)
        tails[i:i + 1] = [x]
    return f"{len(tails)}\n"


def _gen_maze(r, size):
    rows = {"small": r.randint(2, 6), "medium": r.randint(7, 60), "max": 500}[size]
    cols = {"small": r.randint(2, 6), "medium": r.randint(7, 60), "max": 500}[size]
    wall = r.choice([0.1, 0.25, 0.35])
    grid = [["#" if r.random() < wall else "." for _ in range(cols)] for _ in range(rows)]
    cells = [(i, j) for i in range(rows) for j in range(cols)]
    (si, sj), (fi, fj) = r.sample(cells, 2)
    grid[si][sj], grid[fi][fj] = "S", "F"
    return f"{rows} {cols}\n" + "".join("".join(row) + "\n" for row in grid)


def _solve_maze(s):
    lines = s.split("\n")
    rows, cols = map(int, lines[0].split())
    grid = lines[1:rows + 1]
    start = next((i, row.index("S")) for i, row in enumerate(grid) if "S" in row)
    dist = {start: 0}
    queue = deque([start])
    while queue:
        i, j = queue.popleft()
        if grid[i][j] == "F":
            return f"{dist[(i, j)]}\n"
        for ni, nj in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
            if 0 <= ni < rows and 0 <= nj < cols and grid[ni][nj] != "#" and (ni, nj) not in dist:
                dist[(ni, nj)] = dist[(i, j)] + 1
                queue.append((ni, nj))
    return "-1\n"


def _gen_roads(r, size):
    n = max(2, _n(r, size, 100_000))
    m = {"small": r.randint(0, 12), "medium": r.randint(n - 1, 3 * n), "max": 100_000}[size]
    edges = [(r.randint(1, n), r.randint(1, n), r.randint(1, 10**6)) for _ in range(m)]
    return f"{n} {m}\n" + "".join(f"{u} {v} {w}\n" for u, v, w in edges)


def _solve_roads(s):
    it = iter(map(int, s.split()))
    n, m = next(it), next(it)
    adj = [[] for _ in range(n + 1)]
    for _ in range(m):
        u, v, w = next(it), next(it), next(it)
        adj[u].append((v, w))
        adj[v].append((u, w))
    dist = [None] * (n + 1)
    heap = [(0, 1)]
    while heap:
        d, u = heapq.heappop(heap)
        if dist[u] is not None:
            continue
        dist[u] = d
        for v, w in adj[u]:
            if dist[v] is None:
                heapq.heappush(heap, (d + w, v))
    return f"{dist[n] if dist[n] is not None else -1}\n"


def _gen_rmq(r, size):
    n, q = _n(r, size, 100_000), _n(r, size, 100_000)
    ops = []
    for _ in range(q):
        if r.random() < 0.5:
            ops.append(f"1 {r.randint(1, n)} {r.randint(-10**9, 10**9)}")
        else:
            ops.append("2 {} {}".format(*_range(r, n, size)))
    return f"{n} {q}\n{_join(r.randint(-10**9, 10**9) for _ in range(n))}\n" + "".join(op + "\n" for op in ops)


def _solve_rmq(s):
    it = iter(s.split())
    n, q = int(next(it)), int(next(it))
    size = 1
    while size < n:
        size *= 2
    tree = [float("inf")] * (2 * size)
    for i in range(n):
        tree[size + i] = int(next(it))
    for i in range(size - 1, 0, -1):
        tree[i] = min(tree[2 * i], tree[2 * i + 1])
    out = []
    for _ in range(q):
        kind, x, y = next(it), int(next(it)), int(next(it))
        if kind == "1":
            i = size + x - 1
            tree[i] = y
            i //= 2
            while i:
                tree[i] = min(tree[2 * i], tree[2 * i + 1])
                i //= 2
        else:
            lo, hi, best = size + x - 1, size + y, float("inf")
            while lo < hi:
                if lo & 1:
                    best = min(best, tree[lo])
                    lo += 1
                if hi & 1:
                    hi -= 1
                    best = min(best, tree[hi])
                lo //= 2
                hi //= 2
            out.append(f"{best}\n")
    return "".join(out)


def _gen_mst(r, size):
    n = _n(r, size, 100_000)
    m = {"small": r.randint(0, 12), "medium": r.randint(max(0, n - 1), 3 * n), "max": 100_000}[size]
    edges = []
    if r.random() < 0.8:  # usually connected: a random spanning tree first
        order = list(range(1, n + 1))
        r.shuffle(order)
        edges = [(order[i], order[r.randrange(i)], r.randint(1, 10**6)) for i in range(1, n)][:m]
    edges += [(r.randint(1, n), r.randint(1, n), r.randint(1, 10**6)) for _ in range(m - len(edges))]
    r.shuffle(edges)
    return f"{n} {m}\n" + "".join(f"{u} {v} {w}\n" for u, v, w in edges)


def _solve_mst(s):
    it = iter(map(int, s.split()))
    n, m = next(it), next(it)
    edges = sorted(((next(it), next(it), next(it)) for _ in range(m)), key=lambda e: e[2])
    parent = list(range(n + 1))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    total, joined = 0, 1
    for u, v, w in edges:
        ru, rv = find(u), find(v)
        if ru != rv:
            parent[ru] = rv
            total += w
            joined += 1
    return f"{total if joined == n else -1}\n"


SPECS: list[Spec] = [
    Spec("oraliq-yigindilari", "Oraliqdagi yig‘indilar",
         "$n$ ta butun sondan iborat $a$ massiv berilgan. $q$ ta so‘rovning har birida $l$ va $r$ berilgan: "
         "$a_l + a_{l+1} + \\ldots + a_r$ yig‘indini toping.\n\n"
         "So‘rovlar ko‘p: har biri uchun massivni qaytadan aylanib chiqish vaqtga sig‘maydi.",
         "Birinchi qatorda $n$ va $q$ ($1 \\le n, q \\le 10^5$). Ikkinchi qatorda $n$ ta butun son "
         "($|a_i| \\le 10^9$). Keyingi $q$ ta qatorning har birida $l$ va $r$ ($1 \\le l \\le r \\le n$).",
         "Har bir so‘rov javobini alohida qatorda chiqaring.",
         _gen_prefix, _solve_prefix, ["5 3\n1 2 3 4 5\n1 5\n2 4\n3 3\n", "3 2\n-5 10 -5\n1 2\n1 3\n"],
         D.MEDIUM, ["prefix-sums", "arrays"]),
    Spec("eng-uzun-oraliq", "Byudjetga sig‘adigan eng uzun oraliq",
         "Do‘konda $n$ ta mahsulot javonda ketma-ket turibdi, $i$-sining narxi $a_i$. Aziz javonning "
         "**ketma-ket** bir qismidagi hamma mahsulotni olmoqchi, lekin jami narx $S$ dan oshmasligi kerak. "
         "U ko‘pi bilan nechta mahsulot ola oladi?",
         "Birinchi qatorda $n$ va $S$ ($1 \\le n \\le 10^5$, $1 \\le S \\le 10^9$). Ikkinchi qatorda $n$ ta "
         "natural son $a_i$ ($1 \\le a_i \\le 10^4$).",
         "Eng ko‘p mahsulotlar soni. Bitta mahsulot ham sig‘masa, `0`.",
         _gen_window, _solve_window, ["5 7\n2 1 3 4 1\n", "3 1\n5 6 7\n"],
         D.MEDIUM, ["two-pointers", "arrays"], edge=["1 10000\n10000\n", "4 1000000000\n1 1 1 1\n"]),
    Spec("narxlar-sorovlari", "Qancha mahsulot sig‘adi",
         "Do‘konda $n$ ta mahsulot bor, narxlari $p_1, \\ldots, p_n$. $q$ ta xaridor keladi, $j$-sining puli "
         "$x_j$. Har bir xaridor uchun do‘kondagi mahsulotlardan nechtasining narxi uning pulidan oshmasligini "
         "(ya’ni $p_i \\le x_j$ ekanini) toping.",
         "Birinchi qatorda $n$ ($1 \\le n \\le 10^5$), ikkinchi qatorda $n$ ta narx ($1 \\le p_i \\le 10^9$). "
         "Uchinchi qatorda $q$ ($1 \\le q \\le 10^5$), to‘rtinchi qatorda $q$ ta son $x_j$ "
         "($0 \\le x_j \\le 10^9 + 1$).",
         "Bitta qatorda probel bilan $q$ ta javob.",
         _gen_prices, _solve_prices, ["5\n30 10 50 20 40\n4\n25 5 50 100\n"],
         D.MEDIUM, ["binary-search", "sorting"]),
    Spec("qavslar-balansi", "Qavslar balansi",
         "Satr faqat `(`, `)`, `[`, `]`, `{`, `}` belgilaridan iborat. U to‘g‘ri qavslar ketma-ketligimi? "
         "To‘g‘ri ketma-ketlikda har bir ochilgan qavs o‘z turidagi qavs bilan va to‘g‘ri tartibda "
         "yopiladi: `([]{})` — to‘g‘ri, `([)]` va `((` — noto‘g‘ri.",
         "Bitta qatorda satr, uzunligi $1$ dan $10^5$ gacha.",
         "`YES` yoki `NO`.",
         _gen_brackets, _solve_brackets, ["([]{})\n", "([)]\n", "((\n"],
         D.MEDIUM, ["data-structures", "strings"], edge=[")\n", "(\n", "{}\n", "}{\n"]),
    Spec("tangalar-bilan-tolash", "Eng kam tanga",
         "Mamlakatda $n$ xil tanga bor, har turidan istalgancha. $S$ so‘mni aniq to‘lash uchun eng kamida "
         "nechta tanga kerak? Masalan, tangalar $1, 3, 4$ va $S = 6$ bo‘lsa, $3 + 3$ — ikkita tanga "
         "(eng kattasidan boshlab olish $4 + 1 + 1$ — uchta tanga beradi, bu kam emas).",
         "Birinchi qatorda $n$ va $S$ ($1 \\le n \\le 100$, $0 \\le S \\le 10^4$). Ikkinchi qatorda $n$ ta "
         "tanga qiymati ($1 \\le c_i \\le 10^4$).",
         "Eng kam tangalar soni; aniq to‘lab bo‘lmasa, `-1`.",
         _gen_coins, _solve_coins, ["3 6\n1 3 4\n", "2 7\n2 4\n", "1 0\n5\n"],
         D.MEDIUM, ["dynamic-programming"]),

    Spec("eng-uzun-osuvchi", "Eng uzun o‘suvchi qism ketma-ketlik",
         "$n$ ta sondan iborat ketma-ketlik berilgan. Undan ba’zi hadlarni o‘chirib (tartibini "
         "o‘zgartirmasdan), **qat’iy o‘suvchi** ketma-ketlik hosil qilish kerak. Eng uzuni necha hadli?\n\n"
         "Masalan, $3, 1, 4, 1, 5, 9, 2, 6$ dan $1, 4, 5, 9$ yoki $1, 4, 5, 6$ — to‘rtta had.",
         "Birinchi qatorda $n$ ($1 \\le n \\le 10^5$). Ikkinchi qatorda $n$ ta butun son ($|a_i| \\le 10^9$).",
         "Eng uzun qat’iy o‘suvchi qism ketma-ketlik uzunligi.",
         _gen_lis, _solve_lis, ["8\n3 1 4 1 5 9 2 6\n", "4\n7 7 7 7\n"],
         D.HARD, ["dynamic-programming", "binary-search"], tl_ms=1000),
    Spec("labirint", "Labirint",
         "Labirint $n \\times m$ kataklardan iborat: `.` — yo‘lak, `#` — devor, `S` — kirish, `F` — chiqish. "
         "Bir qadamda qo‘shni (yuqori, past, chap, o‘ng) yo‘lakka o‘tish mumkin. Kirishdan chiqishgacha "
         "eng kamida necha qadam kerak?",
         "Birinchi qatorda $n$ va $m$ ($2 \\le n, m \\le 500$). Keyingi $n$ ta qatorda $m$ tadan belgi. "
         "`S` va `F` bittadan.",
         "Eng kam qadamlar soni; chiqishga yetib bo‘lmasa, `-1`.",
         _gen_maze, _solve_maze, ["3 4\nS..#\n.#..\n...F\n", "2 3\nS#F\n.#.\n"],
         D.HARD, ["graphs"], tl_ms=1000, ml_mb=128),
    Spec("shaharlar-yollari", "Eng qisqa yo‘l",
         "Viloyatda $n$ ta shahar va ularni tutashtiruvchi $m$ ta ikki tomonlama yo‘l bor, har bir yo‘lning "
         "uzunligi ma’lum. 1-shahardan $n$-shaharga eng qisqa yo‘l uzunligini toping.",
         "Birinchi qatorda $n$ va $m$ ($2 \\le n \\le 10^5$, $0 \\le m \\le 10^5$). Keyingi $m$ ta qatorda "
         "$u$, $v$, $w$ — $u$ va $v$ shaharlar orasidagi yo‘l uzunligi ($1 \\le u, v \\le n$, "
         "$1 \\le w \\le 10^6$). Bir juft shahar orasida bir nechta yo‘l, shahardan o‘ziga yo‘l bo‘lishi mumkin.",
         "Eng qisqa yo‘l uzunligi; $n$-shaharga borib bo‘lmasa, `-1`.",
         _gen_roads, _solve_roads, ["4 5\n1 2 4\n1 3 1\n3 2 2\n2 4 5\n3 4 9\n", "3 1\n1 2 5\n"],
         D.HARD, ["graphs"], tl_ms=2000, ml_mb=128),
    Spec("oraliq-minimumi", "O‘zgaruvchan massivda minimum",
         "$n$ ta sondan iborat massiv berilgan. $q$ ta amal bajariladi:\n\n"
         "- `1 i x` — $a_i$ ning qiymati $x$ ga o‘zgaradi;\n"
         "- `2 l r` — $a_l, \\ldots, a_r$ orasidagi eng kichik sonni chiqaring.\n\n"
         "Har bir so‘rovda oraliqni aylanib chiqish vaqtga sig‘maydi.",
         "Birinchi qatorda $n$ va $q$ ($1 \\le n, q \\le 10^5$). Ikkinchi qatorda $n$ ta butun son. Keyingi "
         "$q$ ta qatorda amallar ($1 \\le i \\le n$, $1 \\le l \\le r \\le n$). Barcha sonlar modul bo‘yicha "
         "$10^9$ dan oshmaydi.",
         "Har bir `2` amali javobini alohida qatorda chiqaring.",
         _gen_rmq, _solve_rmq, ["5 5\n5 3 8 1 4\n2 1 3\n2 1 5\n1 4 10\n2 3 5\n2 4 4\n"],
         D.HARD, ["data-structures"], tl_ms=1000, ml_mb=128),
    Spec("yollar-tarmogi", "Yo‘llar tarmog‘i",
         "$n$ ta qishloqni yo‘l bilan bog‘lash kerak: istalgan qishloqdan istalganiga (boshqa qishloqlar "
         "orqali bo‘lsa ham) borish mumkin bo‘lsin. $m$ ta mumkin bo‘lgan yo‘l va har birini qurish narxi "
         "ma’lum. Eng kam umumiy narxni toping.",
         "Birinchi qatorda $n$ va $m$ ($1 \\le n \\le 10^5$, $0 \\le m \\le 10^5$). Keyingi $m$ ta qatorda "
         "$u$, $v$, $w$ — $u$ va $v$ qishloqlar orasidagi yo‘l narxi ($1 \\le w \\le 10^6$).",
         "Eng kam umumiy narx; hamma qishloqni bog‘lab bo‘lmasa, `-1`.",
         _gen_mst, _solve_mst, ["4 5\n1 2 3\n2 3 1\n1 3 2\n3 4 4\n1 4 10\n", "3 1\n1 2 5\n"],
         D.HARD, ["graphs", "greedy"], tl_ms=2000, ml_mb=128, edge=["1 0\n"]),
]


def build_tests(problem: Problem, spec: Spec) -> list[TestCase]:
    rng = random.Random(spec.slug)  # same slug -> same tests on every run
    inputs = list(spec.samples) + list(spec.edge)
    seen = set(inputs)
    for size in SIZES:
        for _ in range(100):
            inp = spec.gen(rng, size)
            if inp not in seen:
                break
        seen.add(inp)
        inputs.append(inp)
    return [TestCase(problem=problem, input=inp, expected=spec.solve(inp),
                     is_sample=i < len(spec.samples), order=i) for i, inp in enumerate(inputs)]


class Command(BaseCommand):
    help = "Create/refresh the medium and hard algorithm problems (matched by slug)."

    def add_arguments(self, parser):
        parser.add_argument("--author", default=None, help="Username of the author (default: first staff user).")

    def handle(self, *args, **opts):
        author = (User.objects.get(username=opts["author"]) if opts["author"]
                  else User.objects.filter(is_staff=True).order_by("pk").first())
        if author is None:
            self.stderr.write("No staff user found; run `seed` first or pass --author.")
            return
        with transaction.atomic():
            for spec in SPECS:
                problem, created = Problem.objects.update_or_create(slug=spec.slug, defaults=dict(
                    title=spec.title, statement_md=spec.statement, input_md=spec.input, output_md=spec.output,
                    difficulty=spec.difficulty, kind=Problem.Kind.CODE, author=author, tl_ms=spec.tl_ms,
                    ml_mb=spec.ml_mb, is_public=True, status=Problem.Status.APPROVED,
                ))
                problem.tags.set([Tag.objects.get_or_create(name=t)[0] for t in spec.tags])
                problem.testcases.all().delete()
                TestCase.objects.bulk_create(build_tests(problem, spec))
                self.stdout.write(f"{'created' if created else 'updated'} {spec.slug}")
        self.stdout.write(self.style.SUCCESS(f"{len(SPECS)} algorithm problems"))
