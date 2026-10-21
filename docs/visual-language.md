# Visual language: levels, ranks and difficulty

Three different ladders live in the product. Each has one look so a learner never has to decode a colour twice.

| What | Where | Look | Never |
|---|---|---|---|
| **Difficulty** of a problem (Beginner, Easy, Medium, Hard) | problem lists, course cards, problem pages | a coloured word, or the `ca-diff-chip` pill on cards | metal colours, chevrons |
| **Rating tier** (Newbie … Legendary) | profile band, rating board | the tier's colour and its chevrons (`apps/accounts/tiers.py`) | metals |
| **Badge level** (I–V) | badge tiles, awards | the five metals (bronze, silver, gold, platinum, diamond), five pips on the tile, a metal dot on each threshold | difficulty words |

Rules that follow:

- A badge's **name** must not repeat a rating tier's name or a problem's title. The courses badge was "Bilimdon" (also the Expert tier) and is now "O‘rganuvchi".
- Level numbers appear as metals in words ("Kumush"), not as Roman numerals, wherever a person reads them.
- A locked badge previews its first metal (bronze, faint) instead of going grey, so it reads as something to earn.
- A course is finished once and stays finished (`PlanDone`), whatever happens to its problems later.
