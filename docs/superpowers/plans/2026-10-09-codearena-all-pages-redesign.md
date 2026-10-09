# CodeArena All-pages Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign every first-party CodeArena page around one clear, responsive design system while preserving real content, routes, permissions, and interactions.

**Architecture:** Keep Django templates, existing view/context contracts, HTMX, and current browser-side behavior. Establish the shared tokens and shell first, then restyle each page family using the right pattern for its content (editor workspace, list/table, learning path, profile, or focused form); finish with cross-role and responsive review.

**Tech Stack:** Django templates, `frontend/src/app.css` + Tailwind build, existing vanilla JS/HTMX, local Manrope/code fonts, Lucide icons.

**Spec:** `docs/superpowers/specs/2026-10-09-codearena-all-pages-redesign.md`

## Global Constraints

- Preserve CodeArena's Uzbek-first purpose, real data, current routes, permissions, judging behavior, and established functionality.
- Keep Manrope as the interface typeface and a local code typeface for source, sample input/output, and technical identifiers.
- Use crisp white surfaces on a very light cool blue canvas, high-contrast navy ink, blue-gray secondary text/borders, and CodeArena cobalt (`#2557E2`) for primary actions, active navigation, links, and focus states.
- Keep green for positive movement/success; reserve tier hues for rating/tier information and charts. Warning and failure colors stay semantic.
- Keep both light and dark themes, keyboard use, visible focus, semantic headings, and accessible contrast.
- Use a consistent 4/8/12/16/24/32/48 px spacing scale and modest, consistent radii.
- Preserve existing URLs, Django view/context contracts, model behavior, permission checks, HTMX interactions, editor behavior, and judging/submission semantics.
- Do not convert the product to a SPA, add a component framework, or invent analytics, feature content, rankings, or user state.
- Use lists/tables for dense information and bordered surfaces only when they clarify grouping.

## Review Focus

- **Phone navigation reachability:** all student and staff destinations remain discoverable and active state remains correct. Manually inspect the menu at 390px as guest, student, and staff.
- **Theme contrast:** primary content, metadata, controls, and semantic states remain readable in both themes. Manually inspect representative list, editor, and admin pages in light and dark.
- **Dense contest/admin data:** long titles, usernames, badges, score columns, and actions remain usable without page-level horizontal overflow. Inspect contest standings and moderation queues at desktop and phone widths.
- **Editor pane changes:** mobile pane switching preserves editor width, language selection, drafts, and full-screen controls. Switch panes, change language, and submit a local demo page.
- **Live/HTMX states:** countdowns, verdict updates, and refreshed rows retain styling and icons after swaps. Observe one active contest/submission and one swapped moderation/contest fragment.

---

### Task 1: Shared visual system and application shell

**Files:**
- Modify: `frontend/src/app.css`
- Modify: `templates/base.html`
- Modify: `templates/_navbar.html`
- Modify: `templates/_nav.html`
- Modify: `templates/_user_menu.html`
- Modify: `templates/_mod_tabs.html`
- Modify: `templates/_pagination.html`
- Modify: `static/js/palette.js`
- Generate: `static/css/app.css`
- Generate: `static/vendor/lucide.min.js`

**Interfaces:**
- Consumes: existing URL names, `nav`, `unread_reviews`, `streak_pill`, theme storage, and menu/search data attributes.
- Produces: shared design tokens and shell styles; consistent page container, controls, navigation groups, focus, active, badge, and menu states for all later tasks.

- [ ] **Step 1: Reconcile global CSS tokens and primitives** in `frontend/src/app.css`: specify typography scale, ink/surface/canvas/line/accent/semantic colors for both themes, spacing/radii, buttons, form controls, tables, alerts, page headers, and empty states. Preserve established class hooks used by templates.
- [ ] **Step 2: Restructure shared navigation and page frame** in the listed shell templates: group student destinations by task, keep account and staff access reachable, remove redundant competing actions, and provide clear current-page and mobile menu states without deleting destinations.
- [ ] **Step 3: Refine search, account, theme, and pagination controls** in `static/js/palette.js` and the shared templates without changing their existing URL, keyboard, persistence, or open/close behavior.
- [ ] **Step 4: Build assets** with `npm --prefix frontend run build`; confirm generated CSS/icons contain the new token and shell styles.
- [ ] **Step 5: Preview the shell** at 1440px and 390px in both themes as guest, student, and staff; confirm every navigation destination is reachable and no horizontal page overflow appears.

### Task 2: Landing, dashboard, and problem discovery

**Files:**
- Modify: `templates/home/landing.html`
- Modify: `templates/home/dashboard.html`
- Modify: `templates/home/_week.html`
- Modify: `templates/problems/list.html`
- Modify: `templates/problems/_daily_card.html`
- Modify: `templates/problems/_month.html`
- Modify: `templates/problems/_solved_card.html`
- Modify: `templates/problems/_sort_th.html`
- Modify: `frontend/src/app.css`

**Interfaces:**
- Consumes: current landing/dashboard/list view contexts, filters, pagination, daily card, weekly streak data, and recommendation/query state.
- Produces: visitor entry page, student next-action dashboard, and searchable problem catalog that use Task 1 primitives.

- [ ] **Step 1: Redesign the landing page** around the actual platform purpose, a clear register/sign-in action, and current factual sections; retain real counts/content and existing links.
- [ ] **Step 2: Redesign the signed-in dashboard** so today's item and time-sensitive work lead, followed by contests, assignments, duels, recent submissions, and next problems; retain all existing context-driven content and empty states.
- [ ] **Step 3: Restructure problem discovery** so search, difficulty, solved-state, and topic filters are compact and results/progress appear early; keep query parameters, sorting, pagination, solved markers, daily problem, and topic links intact.
- [ ] **Step 4: Preview** landing as guest, dashboard as student, and filtered/unfiltered catalogs at desktop and 390px; confirm filters and pagination still point to the same routes.

### Task 3: Problem statement, editor, and submission workflow

**Files:**
- Modify: `templates/problems/detail.html`
- Modify: `templates/problems/_difficulty.html`
- Modify: `templates/problems/_leaders_mini.html`
- Modify: `templates/submissions/detail.html`
- Modify: `templates/submissions/_status.html`
- Modify: `templates/submissions/_verdict.html`
- Modify: `frontend/src/app.css`
- Generate: `static/css/app.css`
- Generate: `static/vendor/lucide.min.js`

**Interfaces:**
- Consumes: current problem/contest context, examples, hints, editor data attributes, submission polling fragments, and verdict/test-result context.
- Produces: readable statement-to-editor workspace, paired copyable samples, and clear submission status/results without changing judge behavior.

- [ ] **Step 1: Finish the problem-page hierarchy**: establish title/context/constraints, statement, input/output, examples, and editor actions in that order; preserve contest clocks/restrictions/navigation, hints, rating, history, code settings, sample-copy hooks, and phone pane switching.
- [ ] **Step 2: Redesign submission status and detail** so verdict and progress lead, followed by test results/resource usage and source; keep polling target/attributes, links, and code highlighting intact.
- [ ] **Step 3: Preview** a practice problem, a contest problem, an accepted and a failed submission, and the phone statement/editor switch; retain editor draft and language after switching.

### Task 4: Contest discovery and live competition pages

**Files:**
- Modify: `templates/contests/list.html`
- Modify: `templates/contests/detail.html`
- Modify: `templates/contests/standings.html`
- Modify: `templates/contests/submissions.html`
- Modify: `templates/contests/clarifications.html`
- Modify: `templates/contests/_band.html`
- Modify: `templates/contests/_card.html`
- Modify: `templates/contests/_dq_banner.html`
- Modify: `templates/contests/_row.html`
- Modify: `templates/contests/_standings_live.html`
- Modify: `templates/contests/_submissions_live.html`
- Modify: `templates/contests/_tags.html`
- Modify: `frontend/src/app.css`

**Interfaces:**
- Consumes: current contest lifecycle, registration state, contest format/rating, problem labels, standings, live fragments, clarification forms, and submissions.
- Produces: consistent contest list/detail/round workspace and dense but legible standings and activity views.

- [ ] **Step 1: Redesign contest list and detail** around status/date/format/registration and a clear round header with problem set and destinations; preserve access gating and all registration controls.
- [ ] **Step 2: Redesign standings, submissions, and clarifications** using scan-friendly tables/lists and visible round context; preserve sorting, score/penalty semantics, clarification actions, and HTMX targets.
- [ ] **Step 3: Preview** upcoming, live, and ended contests, including a live standings refresh; inspect long titles and table behavior at 1440px and 390px.

### Task 5: Learning and classroom workflows

**Files:**
- Modify: `templates/learn/hub.html`
- Modify: `templates/learn/course.html`
- Modify: `templates/learn/list.html`
- Modify: `templates/learn/lists.html`
- Modify: `templates/learn/_plan_strip.html`
- Modify: `templates/learn/_problem_rows.html`
- Modify: `templates/learn/_save_menu.html`
- Modify: `templates/classroom/list.html`
- Modify: `templates/classroom/detail.html`
- Modify: `templates/classroom/form.html`
- Modify: `templates/classroom/duel.html`
- Modify: `templates/classroom/duels.html`
- Modify: `templates/classroom/_duel_row.html`
- Modify: `templates/classroom/_duel_status.html`
- Modify: `templates/classroom/_status.html`
- Modify: `frontend/src/app.css`

**Interfaces:**
- Consumes: course and plan progress, saved-list membership, assignments/groups/deadlines, duel participants/state/timers, and existing teacher form contexts.
- Produces: a navigable learning path, clear assignment/group workspaces, and focused duel challenge/result pages.

- [ ] **Step 1: Redesign learning hub, courses, problem lists, and saved lists** around progress and continue/solve actions; preserve plan navigation, problem status, save/unsave controls, and query state.
- [ ] **Step 2: Redesign classroom lists, assignment/group details, and forms** so deadlines, problem names, member progress, and teacher actions are explicit; preserve permissions and form behavior.
- [ ] **Step 3: Redesign duel list/detail/status** around participants, challenge action, timer, current state, and outcome; retain current submit and live-refresh behavior.
- [ ] **Step 4: Preview** an in-progress course, due assignment, teacher form, and active/completed duel at desktop and phone sizes.

### Task 6: Profiles, leaderboards, account flows, and trust content

**Files:**
- Modify: `templates/accounts/profile.html`
- Modify: `templates/accounts/profile_edit.html`
- Modify: `templates/accounts/rating.html`
- Modify: `templates/accounts/top.html`
- Modify: `templates/accounts/honor.html`
- Modify: `templates/accounts/_board_tabs.html`
- Modify: `templates/accounts/_leaderboard_nav.html`
- Modify: `templates/accounts/_rank.html`
- Modify: `templates/accounts/_user.html`
- Modify: `templates/registration/login.html`
- Modify: `templates/registration/register.html`
- Modify: `templates/registration/password_change_form.html`
- Modify: `templates/registration/password_reset_complete.html`
- Modify: `templates/registration/password_reset_confirm.html`
- Modify: `templates/registration/password_reset_done.html`
- Modify: `templates/registration/password_reset_form.html`
- Modify: `templates/registration/_auth_brand.html`
- Modify: `templates/registration/_auth_field.html`
- Modify: `templates/registration/_auth_script.html`
- Modify: `templates/403.html`
- Modify: `templates/404.html`
- Modify: `templates/500.html`
- Modify: `frontend/src/app.css`

**Interfaces:**
- Consumes: current profile, solved counts/charts, rating/practice leaderboards, honor-policy content, auth forms, and reset flows.
- Produces: clear identity/progress pages, comparable ranking views, focused authentication screens, and recoverable error states.

- [ ] **Step 1: Redesign profile and profile edit** so identity/current rating/progress lead and charts explain their metric; use the supplied profile screenshot as a composition reference (profile navigation, identity summary, metric groups, rating history, topic performance) only where the existing profile data supports it. Preserve chart data, solved breakdowns, contest history, and edit fields.
- [ ] **Step 2: Redesign rating and practice leaderboards** to distinguish the ranking metric and make rank/user/value columns scannable; keep filters, pagination, and profile links.
- [ ] **Step 3: Redesign honor, authentication, password, and error pages** with plain-language context and one obvious next action; preserve all form names, validation messages, email reset routes, and status semantics.
- [ ] **Step 4: Preview** profile, both leaderboards, login/register/reset, and 403/404 at desktop and phone widths in both themes.

### Task 7: Moderation and integrity workspaces

**Files:**
- Modify: `templates/moderation/dashboard.html`
- Modify: `templates/moderation/problems.html`
- Modify: `templates/moderation/queue.html`
- Modify: `templates/moderation/submit.html`
- Modify: `templates/moderation/submissions.html`
- Modify: `templates/moderation/contest_form.html`
- Modify: `templates/moderation/contest_official.html`
- Modify: `templates/moderation/contests.html`
- Modify: `templates/moderation/daily_problem.html`
- Modify: `templates/moderation/groups.html`
- Modify: `templates/moderation/group_form.html`
- Modify: `templates/moderation/plans.html`
- Modify: `templates/moderation/plan_form.html`
- Modify: `templates/moderation/tags.html`
- Modify: `templates/moderation/tag_form.html`
- Modify: `templates/moderation/users.html`
- Modify: `templates/moderation/user_form.html`
- Modify: `templates/moderation/_header.html`
- Modify: `templates/integrity/audit.html`
- Modify: `templates/integrity/contest_report.html`
- Modify: `templates/integrity/practice_report.html`
- Modify: `templates/integrity/replay.html`
- Modify: `templates/integrity/_audit_rows.html`
- Modify: `templates/integrity/_tracker.html`
- Modify: `frontend/src/app.css`

**Interfaces:**
- Consumes: staff queue counts, moderation/review contexts, all current form fields/actions, audit events, replay data, and integrity decisions.
- Produces: prioritized review queues, focused authoring/editing forms, clear audit timelines, and evidence-centered integrity reports.

- [ ] **Step 1: Redesign moderation dashboard and list/queue screens** around pending work and row-level review context; preserve filters, pagination, selected-row actions, and staff-only navigation.
- [ ] **Step 2: Redesign moderation authoring/forms** for problems, official contest content, contests, daily problem, groups, plans, tags, and users; retain every field, validation message, and destructive-action confirmation.
- [ ] **Step 3: Redesign integrity audit, contest/practice reports, and replay** around evidence and decision context; preserve event detail, links, timestamps, and moderation actions.
- [ ] **Step 4: Preview** staff pages at desktop and phone widths; check long identifiers, evidence/source blocks, validation errors, and confirmation flows.

### Task 8: Cross-page integration and final visual QA

**Files:**
- Modify as needed: all first-party templates under `templates/`
- Modify as needed: `frontend/src/app.css`
- Generate: `static/css/app.css`
- Generate: `static/vendor/lucide.min.js`

**Interfaces:**
- Consumes: all page-family changes and existing roles/view contexts.
- Produces: one coherent site-wide visual system with no broken page-family exceptions.

- [ ] **Step 1: Build the final frontend assets** with `npm --prefix frontend run build` and confirm the source and generated assets are synchronized.
- [ ] **Step 2: Run the app with local demo data** and manually visit representative guest/student/teacher/staff routes for every page family at 1440px and 390px in light/dark themes.
- [ ] **Step 3: Resolve visual and interaction regressions** found in Review Focus; preserve all view/context and browser-side contracts.
- [ ] **Step 4: Revisit every route family listed in the spec** and confirm navigation, forms, filters, copy actions, editor controls, live fragments, and status feedback remain present and usable.

## Plan self-review

- **Spec coverage:** Shared shell/tokens are Task 1; landing/dashboard/catalog Task 2; problem/editor/submissions Task 3; contests Task 4; learning/classroom Task 5; profiles/leaderboards/trust/auth/errors Task 6; all moderation/integrity pages Task 7; responsive/theme/role integration Task 8.
- **Step scan:** Each implementation step is scoped to one page family or one verification pass; no step changes backend/view contracts.
- **Interface consistency:** Later page families consume Task 1 CSS primitives and current Django contexts; no new JS/view API is introduced.
- **Review Focus:** The five highest-risk cases map to Tasks 1, 3, 4, 5, 7, and 8 for explicit manual review.
- **Proportion:** This plan maps work to the existing template families and avoids prescribing implementation details already present in the Django/HTMX app.
