# UI/UX Overhaul (sub-project D) — Design Spec

Date: 2026-09-27
Program: CodeArena improvement, sub-projects A → B → C → D
(A honest results · B anti-cheat v2 · C unique features · D UI/UX overhaul)

The user was away and asked to go on; every decision below is Claude's, made from an
audit of the running app (desktop 1366×900 and phone 390×844, light and dark, as a
guest, a student, a teacher and staff). Overrule any of them.

## Goal

Keep the existing visual language (it is consistent and already themed for light and
dark) and fix what the audit found: pages that break or can't be reached on a phone,
numbers that are wrong, a front end that depends on third-party CDNs, and the lack of a
place that tells a student what to do next.

## Audit findings

| # | Finding | Kind |
|---|---|---|
| 1 | Tailwind was compiled in every visitor's browser by the Play CDN (development-only), and htmx, icons, KaTeX, the editor and fonts came from five CDNs; where one is slow or blocked the site is unstyled or the editor never loads. The editor's modules were unversioned (whatever esm.sh served). | robustness |
| 2 | On a phone the sidebar is hidden and the bottom bar has five items, so Vazifalar, Duellar, Foydalanuvchilar and all staff pages are unreachable | bug |
| 3 | On a phone the problem table overlaps: long titles run over the difficulty chips, columns are cut | bug |
| 4 | Countdowns stop after an htmx swap (the duel timer goes blank after its first 5 s refresh) | bug |
| 5 | Profile: solved-per-difficulty can exceed the total ("Beginner 2/1") | bug |
| 6 | Guests land in a table with no word on what the site is; signed-in students have no page that gathers today's problem, homework due, duel challenges and contests | UX |
| 7 | "Keyingi masala" shows one card when the user's level is the top one | UX |
| 8 | Problem page on a phone: the editor is below the whole statement | UX |
| 9 | Duel page is a bare status box; the challenge form needs an exact username | UX |
| 10 | Homework grid columns are just numbers | UX |
| 11 | The fonts were Anthropic's proprietary brand fonts, committed to a public repo | licensing |

## Decisions

1. **Self-hosted front end** (done): `frontend/build.mjs` builds Tailwind ahead of time and
   vendors everything at pinned versions; outputs are committed so deploys need no
   Node. Inter, JetBrains Mono and Fira Code (SIL OFL) replace the proprietary fonts. A
   test fails on a stale build or a third-party script/stylesheet.
2. **Mobile navigation**: the bottom bar keeps four destinations (Bosh sahifa,
   Masalalar, Musobaqalar, Urinishlar) and a fifth "Menyu" button opens a sheet with
   every sidebar link, staff links included, and the unread-review badge.
3. **Home**: `/` becomes a page of its own. Signed in: greeting, streak, today's problem,
   homework due soonest, duel challenges waiting, running and next contests, next
   problems, latest submissions. Guest: what CodeArena is (practice, rated contests,
   homework, duels, honest judging), today's problem and the next contest, sign-up.
4. **Problem list on a phone**: the table becomes stacked rows (title, difficulty, solve
   rate); number, tags and rating columns hide below `sm`.
5. **Problem page on a phone**: a "Masala | Yechim" switcher shows one pane at a time
   below `lg`; the editor re-measures when shown.
6. **Duel page**: two player cards (rating, attempts, solved-at) around the timer;
   the challenge form suggests classmates from the user's groups.
7. **Smaller fixes**: countdowns re-scan after swaps; per-difficulty counts come from the
   same catalog as the totals; next problem widens to one level below at the top
   level; homework grid lists problem titles above the columns.

## Out of scope

A new colour palette or component library, a SPA, PWA/offline mode.
