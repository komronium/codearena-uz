# Learn Section ("O‘rganish") Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give CodeArena a structured learning layer, in the spirit of LeetCode's Library / Quest / Explore / Study Plan / My Lists, built on the existing problems, tags and solves, with no AI.

**Architecture:** A new app `apps/learn` owns study plans (plan → sections → problems), the quest path (an ordered subset of plans), topic pages (a theory text on the existing `Tag`), and user problem lists. Progress is never stored: it is read from `UserProblemSolved` against the problems a user may see right now (`apps.problems.skills.open_problems`), so rejudges, publishes and disqualifications flow through by themselves. Staff edit everything in `/moderation/`; a management command seeds the first plans and topic texts from problems already on the portal.

**Tech Stack:** Django 5.2 (Python 3.12 in prod), server-rendered templates with Tailwind CDN classes and the existing `ca-*` components, lucide icons, pytest + pytest-django.

**Spec:** this conversation (2026-10-01): "LeetCode'dagidek: Library, Quest, Explore, Study Plan, My Lists — hammasini". Mapping agreed there:

| LeetCode | CodeArena | Where |
|---|---|---|
| Library | Masalalar | exists (`problems:list`) |
| Study Plan | O‘quv rejalar | `/learn/`, `/learn/plans/<slug>/` |
| Quest | Yo‘l (quest path of plans + earned badges) | top of `/learn/`, profile |
| Explore | Mavzular (topic theory + its problems) | `/learn/topics/`, `/learn/topics/<name>/` |
| My Lists | Ro‘yxatlarim | `/learn/lists/`, save button on the problem page |

## Global Constraints

- No new dependencies; `requirements.txt` stays unchanged.
- No Django admin. Staff tools live under `/moderation/` (memory: no-django-admin).
- UI copy is Uzbek (Latin); new strings use `‘` (U+2018) as the apostrophe.
- Code must run on Python 3.12.
- A problem is shown in any learn page only if it is in `open_problems()` (public, approved, not held by a running or upcoming contest). Hidden ones are neither listed nor counted.
- Markdown (plan description, section intro, topic theory) is rendered with `apps.problems.views._render_statement` (mistune + bleach) — never `|safe` on raw input.
- Migrations: `problems/00xx_tag_about_md` (next number), `learn/0001_initial`.
- Do not run `migrate` against the dev `db.sqlite3` as part of tests; pytest builds its own DB.
- Git: no commits unless the user asks. "Commit" steps are conditional.
- Tests: `pytest -q`.

## Review Focus

1. A plan problem that gets pulled into an upcoming contest (or unpublished) must disappear from the plan, topic and list pages and from every `done/total` — not 404 the page (Task 1 `test_progress_ignores_hidden_problems`, Task 2 `test_plan_page_hides_hidden_problem`).
2. A private list must 404 for anyone but its owner, and nobody may add to someone else's list or add a hidden problem (Task 5 `test_list_privacy_and_ownership`, `test_cannot_save_hidden_problem`).
3. A plan whose problems are all hidden has `total == 0` and is never "completed" (no badge for nothing) (Task 1 `test_empty_plan_is_not_completed`).
4. Staff typing an unknown, pending or duplicate slug into a section gets a form error naming it, and nothing is saved (Task 6 `test_plan_form_rejects_bad_slugs`).
5. A bogus or unrelated `?plan=` on a problem page is ignored, never a 500 (Task 4 `test_problem_page_ignores_bad_plan_param`).

---

## File Structure

- Create `apps/learn/` — `__init__.py`, `apps.py`, `models.py`, `progress.py`, `views.py`, `urls.py`, `forms.py`, `tests.py`, `migrations/`, `management/commands/add_study_plans.py`.
- Create templates `templates/learn/`: `hub.html`, `plan.html`, `topics.html`, `topic.html`, `lists.html`, `list.html`, `_plan_card.html`, `_problem_rows.html`, `_save_menu.html`, `_plan_strip.html`.
- Create staff templates `templates/moderation/plans.html`, `plan_form.html`, `tag_form.html`.
- Modify `apps/problems/models.py` (`Tag.about_md`), `config/settings/base.py` (INSTALLED_APPS), `config/urls.py`, `apps/problems/views.py` (problem page context), `templates/problems/detail.html`, `apps/moderation/{views,urls,forms}.py`, `templates/moderation/tags.html`, `templates/_rail.html`, `templates/_nav.html`, `templates/base.html` (bottom nav, topbar section), `templates/moderation/_mod_tabs.html`, profile view/template (badges).

---

### Task 1: Models and progress

**Files:** create `apps/learn/{__init__,apps,models,progress}.py`, migrations; modify `apps/problems/models.py`, settings, test `apps/learn/tests.py`.

**Produces:**

```python
# apps/problems/models.py — Tag
about_md = models.TextField(blank=True)  # topic theory, shown on /learn/topics/<name>/

# apps/learn/models.py
class StudyPlan(models.Model):
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=120)
    summary = models.CharField(max_length=200, blank=True)   # one line on the card
    description_md = models.TextField(blank=True)
    level = models.CharField(max_length=10, choices=Problem.Difficulty.choices, default=Problem.Difficulty.BEGINNER)
    icon = models.CharField(max_length=40, default="book-open")  # lucide name
    order = models.PositiveIntegerField(default=0)
    in_quest = models.BooleanField(default=False)  # a stage of the "Yo‘l"
    is_public = models.BooleanField(default=False)
    class Meta: ordering = ["order", "id"]

class PlanSection(models.Model):
    plan = FK(StudyPlan, CASCADE, related_name="sections")
    title = models.CharField(max_length=120)
    intro_md = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    class Meta: ordering = ["order", "id"]

class PlanItem(models.Model):
    section = FK(PlanSection, CASCADE, related_name="items")
    problem = FK(Problem, CASCADE, related_name="+")
    order = models.PositiveIntegerField(default=0)
    class Meta: ordering = ["order", "id"]

class ProblemList(models.Model):
    owner = FK(User, CASCADE, related_name="problem_lists")
    name = models.CharField(max_length=80)
    is_public = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ["-created", "-id"]

class ProblemListItem(models.Model):
    list = FK(ProblemList, CASCADE, related_name="items")
    problem = FK(Problem, CASCADE, related_name="+")
    added = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ["-added", "-id"]; unique_together = ("list", "problem")

# apps/learn/progress.py
def plan_problem_ids(plans) -> dict[int, list[int]]   # plan id -> open problem ids in plan order
def plan_progress(user, plans) -> dict[int, dict]     # plan id -> {"done", "total", "pct", "completed"}
def solved_ids(user, ids) -> set[int]                 # empty for anonymous
```

`plan_progress`: one query for items of all plans filtered by `problem__in=open_problems()`, one for solves; `completed = total > 0 and done == total`.

- [ ] Write tests `test_progress_ignores_hidden_problems` (plan with one open and one `is_public=False` problem: total 1; solving the hidden one changes nothing) and `test_empty_plan_is_not_completed`.
- [ ] Run, expect import failure. Implement models, `apps.py` (`LearnConfig`, name `apps.learn`), add to INSTALLED_APPS, `makemigrations problems learn`, implement progress.
- [ ] Run tests, expect PASS. Commit (conditional): `feat(learn): study plan, list models and derived progress`.

### Task 2: Hub (quest path + plans) and plan page, navigation

**Files:** `apps/learn/{views,urls}.py`, `config/urls.py` (`path("learn/", include("apps.learn.urls"))`), templates `hub.html`, `plan.html`, `_plan_card.html`, `_problem_rows.html`, nav templates.

**Produces:** URL names `learn:hub` (`/learn/`), `learn:plan` (`/learn/plans/<slug>/`).

- Hub: "Yo‘l" — `in_quest` plans as a vertical path in `order`; each stage shows icon, title, `done/total` bar; the first not-completed stage is marked "Siz shu yerdasiz" (logged-in) — stages are never locked. Below: "Davom ettiring" (plans with `0 < done < total`, logged-in only), then all public plans as cards grouped by level, then links to Mavzular and Ro‘yxatlarim.
- Plan page: header (title, level chip, description, overall bar), sections in order, each with rendered intro and a row per open problem (solved check, title linking to `problems:detail` + `?plan=<slug>`, difficulty chip, first tag). Non-public plan → 404 for non-staff (staff see a "Yashirin" chip).
- Nav: "O‘rganish" (icon `graduation-cap`) after Masalalar in `_rail.html`, `_nav.html` (under "Mashq"), the phone bottom bar, and the topbar section title (`ns == "learn"`). Problem-page highlighting of "Masalalar" stays as is.
- Tests: `test_hub_and_plan_render_for_anonymous`, `test_plan_page_shows_progress` (2 of 3 solved → "2/3"), `test_plan_page_hides_hidden_problem` (title of hidden problem absent, total 1), `test_private_plan_404_for_students_not_staff`.
- [ ] Tests first, fail, implement, pass. Commit (conditional): `feat(learn): learn hub with quest path and study plan pages`.

### Task 3: Explore — topics

**Files:** views/urls/templates `topics.html`, `topic.html`.

**Produces:** `learn:topics` (`/learn/topics/`), `learn:topic` (`/learn/topics/<str:name>/`).

- Topics index: cards from `apps.problems.skills.skill_map(user)` for logged-in (it already gives `solved/total/pct` per tag over open problems); for anonymous, the same rows with `solved=0` (refactor: `skill_map(user)` accepts an anonymous user → empty solved set). Grouped by `Tag.kind` (Dasturlash / SQL). A card shows a "Nazariya" mark when `about_md` is set.
- Topic page: rendered `about_md` (or "Bu mavzu uchun nazariya hali yozilmagan."), open problems of the tag grouped by difficulty with solved marks, and public plans containing the tag. Unknown tag or no open problems → 404.
- Tests: `test_topic_page_lists_only_open_problems`, `test_unknown_topic_404`, `test_topic_theory_is_sanitized` (`<script>` in about_md not rendered).
- [ ] Tests first, implement, pass. Commit (conditional): `feat(learn): topic pages with theory and problems`.

### Task 4: Plan strip on the problem page

**Files:** `apps/learn/progress.py` (`plan_nav`), `apps/problems/views.py` (`problem_detail` context), `templates/learn/_plan_strip.html`, `templates/problems/detail.html`.

**Produces:**

```python
def plan_nav(user, plan_slug: str, problem_id: int) -> dict | None
# {"plan", "done", "total", "prev": Problem|None, "next": Problem|None} or None when the slug is
# empty/unknown/non-public or the problem is not an open problem of that plan.
```

- Strip above the statement: "← Reja: <title> · 12/30" with prev/next links that keep `?plan=`. Not shown inside a contest (`contest is not None`).
- Tests: `test_problem_page_shows_plan_strip_with_next`, `test_problem_page_ignores_bad_plan_param` (unknown slug, plan without that problem, private plan → 200 and no strip).
- [ ] Tests first, implement, pass. Commit (conditional): `feat(learn): plan navigation strip on the problem page`.

### Task 5: My Lists

**Files:** views/urls/forms, templates `lists.html`, `list.html`, `_save_menu.html`, problem page.

**Produces:** `learn:lists` (GET index + POST create), `learn:list` (`/learn/lists/<int:pk>/`), `learn:list_edit` (POST rename/public toggle), `learn:list_delete` (POST), `learn:save` (`/learn/save/<slug>/`, POST `list=<pk>`: toggles the problem in that list; `list=new` + `name` creates a list and adds it). `ListForm(name, is_public)`.

- Login required for everything except viewing a public list. A list is fetched with `owner=request.user` for every write (404 otherwise). Private list GET by non-owner → 404.
- Save: only problems in `open_problems()`; otherwise 404. Toggle is idempotent per POST (add if missing, remove if present); redirects back to `next` if it is a safe local URL (`url_has_allowed_host_and_scheme`), else to the problem page.
- Problem page: a "Saqlash" `<details>` menu listing the user's lists with checked state + "Yangi ro‘yxat" input (not in a contest).
- List page shows only open problems (hidden ones are counted as "N ta masala hozir yopiq").
- Max 50 lists per user (form error "Ko‘pi bilan 50 ta ro‘yxat.").
- Tests: `test_list_privacy_and_ownership`, `test_cannot_save_hidden_problem`, `test_save_toggles_and_creates_list`, `test_save_rejects_external_next`.
- [ ] Tests first, implement, pass. Commit (conditional): `feat(learn): personal problem lists`.

### Task 6: Staff editing

**Files:** `apps/moderation/{views,urls,forms}.py`, templates `moderation/plans.html`, `plan_form.html`, `tag_form.html`, `_mod_tabs.html`, `_nav.html` admin group, `templates/moderation/tags.html` (edit link).

**Produces:** `moderation:plans`, `moderation:plan_new`, `moderation:plan_edit`, `moderation:plan_delete` (POST), `moderation:tag_edit`. `StudyPlanForm` (all plan fields), `PlanSectionFormSet` (inline, `extra=1`, `can_delete`, `can_order` not used — `order` field), each `PlanSectionForm` has a `slugs` textarea (one slug per line, `#` comments and blanks ignored).

- `PlanSectionForm.clean_slugs`: resolve to `Problem` with `status=APPROVED`; unknown/pending/rejected → `"Topilmadi yoki tasdiqlanmagan: a, b"`; duplicate inside the section → error. The formset's `clean` rejects a slug repeated across sections. Saving rewrites the section's items in the given order inside one transaction.
- A problem that is approved but not public (contest problem) is allowed — it will show once open; the form shows a warning count "N ta masala hozir yopiq".
- `TagForm` gets an edit view with `name`, `kind`, `about_md` (with the same markdown preview area as the problem editor if reusable; otherwise a plain textarea).
- Tests: `test_staff_creates_plan_with_sections`, `test_plan_form_rejects_bad_slugs`, `test_plan_pages_require_staff`, `test_staff_edits_topic_theory`.
- [ ] Tests first, implement, pass. Commit (conditional): `feat(moderation): edit study plans and topic theory`.

### Task 7: Quest badges and seed content

**Files:** profile view/template (`apps/accounts/views.py`, `templates/accounts/profile.html`), `apps/learn/management/commands/add_study_plans.py`.

- Profile: "Yo‘l nishonlari" row — completed public plans (`plan_progress(...)["completed"]`) as icon chips; nothing when none.
- `add_study_plans [--dry-run]`: idempotent (`update_or_create` by plan slug; sections rebuilt), plans public. Missing slugs are skipped with a warning line, never an error. Also fills `Tag.about_md` for core topics only where it is empty (never overwrites staff edits).
- Seed plans (quest order 1–3, SQL outside the quest):
  1. `birinchi-qadam` "Birinchi qadam" (beginner): Kirish va chiqish → Shartlar → Sikllar → Hayotiy masalalar.
  2. `massiv-va-satrlar` "Massiv va satrlar" (easy): Massivlar → Satrlar → Hash-jadval → Ikki ko‘rsatkich → Matematika va bitlar.
  3. `algoritmlarga-kirish` "Algoritmlarga kirish" (medium): Prefiks yig‘indilar → Ikki ko‘rsatkich → Ikkilik qidiruv → Stek → Dinamik dasturlash → Graflar.
  4. `sql-asoslari` "SQL asoslari": SELECT va WHERE → Saralash → Guruhlash → JOIN → Murakkab so‘rovlar.
- Topic theory for: input-output, conditionals, loops, math, arrays, strings, hash-table, two-pointers, prefix-sums, sorting, binary-search, dynamic-programming, graphs, greedy, data-structures, bit-manipulation.
- Tests: `test_add_study_plans_is_idempotent_and_skips_missing`, `test_profile_shows_completed_plan_badge`.
- [ ] Tests first, implement, pass. Run full `pytest -q`. Commit (conditional): `feat(learn): quest badges and starter study plans`.

## Out of scope (YAGNI, add when asked)

XP/levels, hard-locked quest stages, per-day plan schedules with reminders, list sharing beyond a public URL, teacher assigning a plan to a group (Assignment already covers homework), AI anything.
