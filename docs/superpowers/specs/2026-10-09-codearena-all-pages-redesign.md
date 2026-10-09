# CodeArena — All-pages UI/UX redesign

Date: 2026-10-09  
Status: design draft for owner review  
Scope: all first-party CodeArena pages and shared navigation, desktop and mobile

## Goal

Redesign CodeArena's complete interface so students, teachers, and staff can find the next action quickly and understand dense programming-contest information without visual clutter. Preserve the platform's Uzbek-first purpose, real data, current routes, permissions, judging behavior, and other established functionality.

The provided screenshots are visual references: the first shows the paired sample input/output component; the second shows a profile composition with identity/navigation, progress, metric summaries, rating history, and topic performance. Reuse these cues where they fit existing content, not as constraints on unrelated pages.

## Design principles

- Make task content and the next useful action the strongest visual elements on each page.
- Use plain language, descriptive section labels, and predictable control placement.
- Use lists and tables for dense information; reserve bordered surfaces for content that benefits from separation.
- Establish a small number of repeatable page archetypes instead of styling every route as a new dashboard.
- Keep all existing useful content, route destinations, actions, permissions, filters, and feedback states.
- Design for narrow phones first where layout order changes; desktop should use its width without stretching reading content.
- Keep both light and dark themes, keyboard use, visible focus, semantic headings, and accessible contrast.

## Visual system

### Typography

- Keep Manrope as the interface typeface, consistent with the current product preference.
- Use a local code typeface for source, sample input/output, and technical identifiers.
- Use a compact type scale with clear roles: page title, section title, body, metadata, and labels. Avoid using weak grey text for primary instructions or important values.
- Use restrained semibold weights for titles and controls; reserve bold for key values and status.

### Color and surfaces

- Use crisp white surfaces on a very light cool blue canvas, with high-contrast navy ink and blue-gray secondary text/borders. Important descriptions, labels, values, and navigation should not rely on pale grey text.
- Use CodeArena cobalt (`#2557E2`) for primary actions, active navigation, links, and focus states; tune its dark-theme token for contrast.
- Keep green for positive movement/success; reserve tier hues for rating/tier information and charts. Warning and failure colors stay semantic. Do not use status colors as decoration.
- Define matching dark-theme tokens with equivalent contrast.
- Prefer hairline borders and surface separation. Avoid gradients, heavy shadows, glass effects, and card grids that do not clarify grouping.

### Spacing and shape

- Use a consistent 4/8/12/16/24/32/48 px spacing scale.
- Use modest radii consistently: smaller for controls, slightly larger for grouped surfaces.
- Use comfortable reading widths and a shared responsive page container; allow tables and editors to use more width.

## Information architecture and page patterns

### Shared application shell

- Keep the CodeArena mark and the primary destinations visible and recognizable.
- Group navigation around the user's work: practice, learning, contests, and classroom; keep account and staff destinations accessible without crowding the primary navigation.
- Preserve current route coverage and active-page indication. Badges should show actionable counts only.
- On mobile, use a compact navigation pattern with a discoverable menu for every destination, including staff tools; no page may become unreachable.
- Keep global search, theme controls, account actions, and contest status available in consistent locations.

### Public entry and student home

- Landing page: explain what CodeArena does, who it serves, how practice/contests/classroom work, and provide one clear registration or sign-in action. Use real platform data only.
- Signed-in home: surface today's work and time-sensitive obligations first, followed by contests, assignments, duels, recent activity, and next recommended problems. Avoid decorative KPI tiles without a clear decision value.

### Practice and problem solving

- Problem catalog: place search, difficulty, solved state, and topic filters in a compact filter bar; keep results and progress visible without scrolling past promotional cards. Use a responsive table/list suited to the data density.
- Problem detail: prioritize title, contest/problem context, statement, input/output rules, examples, and constraints. Keep sample input/output paired and copyable. Keep the code editor, language choice, run/submit actions, and verdict feedback intact. On phones, make the statement/editor switch obvious and keep the editor usable after switching.
- Preserve contest-specific restrictions, clocks, problem navigation, hints, editor settings, and submission history.

### Submissions

- Submission list: make problem, verdict, language, time, and contest context easy to scan and filter.
- Submission detail: establish verdict and progress first, then execution details and source code. Polling and per-test results must remain clear and stable.

### Contests

- Contest list: distinguish upcoming, running, and ended rounds with their dates, registration state, format, and rating status.
- Contest detail: make round status, registration, problem list, and the standings/submissions/clarification destinations easy to find.
- Standings: preserve the dense, sortable ranking table and solved/penalty or score semantics. Provide a workable compact mobile presentation rather than hiding meaningful values.
- Clarifications and contest submissions should retain live refresh, contest context, and clear problem labels.

### Learning and classroom

- Learning hub, courses, lessons, and saved lists should expose topic/course progression and a clear continue action.
- Assignments and groups should make deadlines, problem names, completion state, and teacher actions explicit.
- Duels should make participants, current state, timer, challenge action, and result understandable at a glance.

### People, ratings, and trust

- Profile pages should lead with identity and current rating/progress, then explain activity charts and solved-problem breakdowns. Use the supplied profile screenshot as a composition reference: compact identity/navigation, a strong profile summary, scannable metric groups, rating history, and topic performance, adapted to data the product actually has.
- Rating and practice leaderboards should be scan-friendly and clearly distinguish their ranking metric.
- Honor/trust pages should explain expectations using the current policy content and point to relevant evidence or actions.

### Moderation and integrity

- Staff dashboards, queues, forms, user/group/plan/tag management, contest authoring, daily-problem controls, submission review, audit, replay, and integrity reports are in scope.
- Preserve permissions, dangerous-action confirmation, review context, and existing admin workflows.
- Make queue priority and review outcome obvious; use dense tables for searchable collections and focused forms for editing.

### Authentication and system states

- Login, registration, profile settings, password reset, 403/404/500, and empty/error states should use the same typography, spacing, and brand language while keeping their primary recovery action clear.

## Implementation boundaries

- Redesign existing Django templates, shared partials, CSS tokens, and frontend assets in place.
- Preserve existing URLs, Django view/context contracts, model behavior, permission checks, HTMX interactions, editor behavior, and judging/submission semantics.
- Do not convert the product to a SPA or add a new component framework.
- Do not invent analytics, feature content, rankings, or user state. Reframe only the data the product already provides.
- Keep the earlier uncommitted problem-page work in the same implementation scope and reconcile it with this site-wide design rather than discarding it.

## Delivery sequence

1. Establish global tokens, typography, navigation, page container, common controls, tables, forms, alerts, and empty/loading states.
2. Apply the shared system to public/student destinations: landing/home, catalog/detail, submissions, contests, learning/classroom, profiles, and leaderboards.
3. Apply it to account and staff destinations, including moderation and integrity tools.
4. Review responsive behavior and light/dark contrast across representative pages and roles; then correct page-family exceptions.

The implementation plan will enumerate concrete template files and route/role combinations before code changes begin.

## Acceptance criteria

- Every first-party route family listed above follows the same design system and intentional page hierarchy.
- Existing important content and core actions remain available with the same behavior and access rules.
- Desktop pages use balanced columns and appropriate content widths; mobile pages remain navigable and do not require horizontal page scrolling.
- Dense contest, leaderboard, and moderation data remains understandable on mobile without removing essential fields.
- Light and dark themes retain readable primary text, metadata, controls, status, and focus states.
- Sample copying, editor language/settings, trial runs, submissions, live contest behavior, forms, filters, pagination, and account actions remain usable.
- Build and application smoke checks succeed, and representative guest/student/teacher/staff pages render at desktop and phone widths.

## Self-review

- Scope includes public, authenticated, teacher, and staff routes; no page family is implicitly excluded.
- The design keeps the established Manrope choice and full dark-theme support while addressing the request for stronger text contrast. Both supplied screenshots are mapped to relevant page patterns without making unrelated pages look identical.
- The proposal changes information hierarchy and page patterns, not only decorative styling.
- Backend contracts and user-visible functionality are explicit implementation constraints.
- No placeholder content, new feature assumptions, or unresolved design choices remain in this draft.
