# CodeArena public API (v1)

Read-only JSON over HTTP, no key needed. Base URL: `https://<site>/api/v1/`. It shows what an anonymous visitor
already sees on the site, nothing more: no emails, no source code, no drafts, no problems of a round that has not
begun, and a marathon's (personal-clock round's) problems and board stay shut until it ends.

- **Times** are ISO 8601 in UTC (`2026-10-22T07:53:24Z`). `duration_minutes` is whole minutes.
- **Limits:** 120 requests a minute per address (`429` with `Retry-After`). Responses are cacheable for 30 s and
  open to any origin (CORS `*`).
- **Language:** all text is English. Problem titles and statements, contest descriptions and badges, country names,
  division labels and the usual cities and schools come back in English; `?lang=uz` asks for the Uzbek the site was
  written in. `language` on a problem or contest says which language its text is actually in (`uz` only while a
  translation is not confirmed yet). Names people typed themselves (usernames, full names) are returned as typed.
- **Lists** page like samcoding.uz: `{"status":"ok","page":1,"pagesCount":3,"pageSize":50,"count":123,"data":[…]}`.
  `?page=` and `?page_size=` (max 200). A page past the last has empty `data`.
- **Errors:** `{"status":"error","error":"not found"}` with the HTTP status.

| Endpoint | What |
|---|---|
| `GET /` | index of endpoints |
| `GET /meta/` | rating tiers, divisions and their rating ranges, contest rules |
| `GET /contests/` | contests (not drafts). `?status=upcoming\|running\|past` `?kind=round\|marathon` `?rated=1\|0` `?start_after=` `?start_before=` `?q=` `?order=start` (default newest first) |
| `GET /contests/{id}/` | one contest and, once it has begun, its problems. `?lang=en\|uz` picks the confirmed translation of the description |
| `GET /contests/{id}/standings/` | the board, paged (default 100 rows), with the problem list |
| `GET /contests/{id}/clist-standings/` | the whole board in the shape of clist's `Statistic.get_standings` |
| `GET /problems/` | public problems. `?difficulty=` `?kind=` `?tag=` `?q=` `?lang=` |
| `GET /problems/{slug}/` | statement, input/output, samples |
| `GET /users/` | the open rating board, best first, with rank. `?q=` `?country=UZ` `?city=` `?school=` |
| `GET /users/{username}/` | public profile: rating, tier, rank, country, city, school, club, counts |
| `GET /users/{username}/ratings/` | rating history, oldest first |

## Contest

`id`, `key`, `title`, `url`, `standings_url`, `start_time`, `end_time`, `duration_minutes`, `personal_minutes`
(marathon clock, else null), `status` (`upcoming`/`running`/`past`), `kind`, `number`, `division` (null = open),
`rules` (`score`/`cf`/`icpc`), `is_rated`, `rating_applied`, `n_problems`, `n_participants`, `authors`, `updated`.

## Standings row

`member` (username), `name`, `country`, `place` (null for authors and the disqualified), `score`, `solved`,
`penalty` (minutes), `rating_before`/`rating_after`/`rating_change` (null until the rating is applied), `author`,
`disqualified`, `out_of_competition` (authors and players outside the division's range: on the board, not rated),
`problems`: `{ "A": {"result":"+","points":500,"wrong_tries":0,"time":"00:12","minutes":12,"first_solve":true,"solved_at":…}, "B": {"result":"-2",…} }`.

## For clist

`/contests/` is the schedule source (`id`→`key`, `title`, `url`, `start_time`, `end_time`). `/contests/{id}/clist-standings/`
returns `problems: [{short,name,url,full_score}]` and `standings: [{member,name,place,solving,penalty,solved,problems:{short:{result,time}},old_rating,new_rating}]`.
For an ICPC round `solving` is the number solved and results are `+`, `+N`, `-N`; for the other rules `solving` is the score and a result is the points.
While a round has not begun, or a marathon is running, `problems` and `standings` are empty and `hidden`/`contest_status` say why.
