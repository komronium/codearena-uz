# Unique Features (sub-project C) — Design Spec

Date: 2026-09-27
Program: CodeArena improvement, sub-projects A → B → C → D
(A honest results · B anti-cheat v2 · C unique features · D UI/UX overhaul)

## Goal

Close the classroom loop that big judges lack (the teacher assigns, the student learns
with graded help, the teacher reviews the code) and give students a reason to come back
every day. Everything stays honest: help costs points, and duels and daily problems
use the same judge and solve rules as practice.

## Decisions

User (2026-09-27): group homework, hints & editorials, teacher code review, skill map &
next problem, 1v1 duels, virtual contests, daily problem + streak. Not the AI tutor.

Defaults chosen while designing (overrule any):

| Topic | Default |
|---|---|
| Who runs a group's homework and reviews its code | the group's teacher, and staff |
| Homework problems | public, approved problems only (hidden ones would need a second access path) |
| "On time" | first AC at or before the deadline; an AC from before the assignment counts |
| Hint cost | set per hint by the author (default 10/20/30 % of the problem's price); total capped at 90 % |
| Which hints cost | only hints opened before the user's first eligible AC |
| Editorial | visible after your AC, or to staff and the author |
| Hints/editorial during a contest | locked while the problem is in a running or upcoming contest |
| Next problem | 3 unsolved public problems from the user's weakest tags, at the user's level |
| Daily problem | picked automatically once a day (Tashkent time), a public problem not used in 60 days, difficulty by weekday |
| Daily bonus | +5 practice points per daily problem solved on its day; streak = consecutive such days |
| Virtual contest | only for published contests the user did not take part in; own timer of the same length; unrated; rank shown among the real participants |
| Duel | challenge by username; 30 minutes; a public problem neither player solved or tried; first AC wins; no AC = draw; separate duel Elo (K 32, start 1200) |

## C1. Group homework (new app `apps/classroom`)

- `Assignment(group, title, description_md, start, deadline, created_by, created)`;
  `AssignmentProblem(assignment, problem, order)`.
- Teacher side under `/classroom/`: list/create/edit an assignment for a group they
  teach; progress grid students × problems: ✓ time (on time), ✓ kech (late),
  ✗ n (tries), — (not tried); `?format=csv` export.
- Student side: "Vazifalar" in the sidebar lists the assignments of their groups with
  x/y solved and a deadline countdown; the assignment page shows each problem's status.
- Status comes from submissions, so rejudges and DQs flow through without extra state.

## C2. Hints and editorials

- `ProblemHint(problem, order, body_md, cost_pct)`, `HintUnlock(user, hint, at)`,
  `Problem.editorial_md`.
- The problem page shows hints as locked cards; opening one (POST, in order) records the
  unlock and shows the cost first. Locked while the problem is in a running/upcoming
  contest.
- `UserProblemSolved.hint_pct` (0–90): the sum of costs of hints unlocked before the
  solve's AC, kept by `refresh_solves`. `sync_practice_points` sums
  `points × (100 − hint_pct) / 100`.
- Staff edit hints and the editorial on the problem form.

## C3. Teacher code review

- `ReviewComment(submission, author, line (null = general), body, created, read)`.
- Staff, the teacher of a group the student is in, and the student can comment; they and
  staff can see the comments. Line comments show under the line on the submission page.
- Unread comments on your own submissions show as a badge in the sidebar; opening the
  submission marks them read.

## C4. Skill map and next problem

- Profile: per tag, solved / public problems as a bar list.
- Problem list (logged in): "Keyingi masala" — 3 picks from the tags with the lowest solve
  share (tags with 3+ public problems), at the difficulty the user solves most at or one
  step above, most-solved first. Excludes solved, contest-locked and daily problems.

## C5. Daily problem and streak

- `DailyProblem(date unique, problem)`, created on first need for the day (race-safe).
- `DailySolve(user, daily)`: kept by the runner's finalize step like solves (a rejudge
  that takes the AC away removes it). Bonus: `sync_practice_points` adds 5 per row.
- Problem list shows the daily card; profile shows current and best streak.

## C6. Virtual contests

- `VirtualParticipation(user, contest, start)`; `Submission.virtual` (nullable FK).
- Start from an ended, published contest's page; the problems open in a virtual workspace
  with its own countdown; submissions in the window are tagged `virtual`.
- Result: score and penalty computed like standings with times from the virtual start,
  and the rank the user would have had among the real (non-DQ) participants.

## C7. 1v1 duels (in `apps/classroom`)

- `Duel(challenger, opponent, difficulty, problem, status, created, started_at,
  ends_at, winner)`; `User.duel_rating` (1200).
- Challenge → the opponent accepts or declines (pending expires after 1 hour). On accept,
  the problem is picked and the 30-minute clock starts. The duel page polls its status.
- The runner's finalize step ends an active duel on the first AC by either player for
  its problem after the start; page views end expired duels as draws. Elo is applied once.

## Migrations

One per app and task, named after the feature.

## Tasks

C1 homework · C2 hints & editorials · C3 code review · C4 skill map & next problem ·
C5 daily & streak · C6 virtual contests · C7 duels · C8 final verification.

## Out of scope

AI tutor, real-time websockets (duels poll), notifications by email/Telegram.
