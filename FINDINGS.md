# What the ladder replays say (2026-09-22)

Written from 14,854 decoded ranked games and 400 top-team replays. Every number
here is measured, not inferred. Tooling lives in a separate analysis repo; this
file is the summary that matters for the bot.

## 1. We were never short of food. We destroyed it.

Per 1000 dragon-turns, our gross pearl intake matches or beats the top eight on
five of eight maps. What differs is what survives:

| | net length kept per 1000 pearls eaten |
|---|---|
| SSS (1914 ELO) | 342 |
| Sabotage-d (1831) | 262 |
| ~1780 cluster | 180-215 |
| **ours** | **15-132** |

On the maps we lose, we leave **2-5x more uneaten pearls standing** than they do
(schooltime 197 vs 70, queen_of_spades 118 vs 52). The food is there. Our
dragons cannot reach it because they box themselves in.

## 2. Self-inflicted death rate is the ladder's hidden ranking variable

`hit wall` and `hit self` both mean the dragon had **no legal move left**. They
are opponent-independent own-goals. Share of all deaths:

| team | ELO | self-inflicted |
|---|---|---|
| SSS | 1914 | 11.8% |
| Sabotage-d | 1831 | 12.1% |
| Matcha Latte / Team SKKU | ~1780 | 18-19% |
| Lon Co Kiri | 1751 | 29.5% |
| err404 / forgot to mention | ~1700 | 41-43% |
| **ours** | — | **58.8%** |

Rank on this ladder is largely a measure of who stops walking into corners.

## 3. The gap is kelp-shaped

At 0% kelp (Big Empty) we match the top teams exactly — 64 dragons vs 63 at
round 400. The entire aggregate gap is carried by the high-kelp maps. On
queen_of_spades (16.6% kelp) a pearl is inside our 7x7 window on **91%** of
dragon-turns and we eat on **2.5%** of them, because 69% of our steps revisit a
tile we occupied in the last 30 moves. That is a dragon oscillating against a
wall with food in sight.

## 4. Split policy — what the top eight actually do

- **Child size 2, always.** 65-100% of their splits are child-size 2; Lon Co
  Kiri and okbro are at exactly 100%. Median parent length *after* a split is 2
  for all eight, i.e. they split the instant they reach length 4.
- **Splitting partitions length, it does not cost it** (verified on 3,001 real
  splits: parent + child == pre-split length). Population ceiling is
  `floor(T/2)`, so 64 dragons needs team total length >= 128.
- **They stop.** 90% of their splits are done by round 313-445.
- **The king needs no rule.** Their longest dragon grows simply because hitting
  the 64 cap makes `can_split` fail for everyone, so survivors eat and grow.
  Ours sat at 4 because we never reached the cap. There is no king trajectory;
  there is a cap, and then food.

  ⚠️ **Correction to an earlier version of this doc.** I first reported their
  longest dragon climbing "5 -> 18" as a general pattern. That number is
  **survivorship-biased** and should not be used. It came from filtering to
  games that reached round 500 — but small maps end by elimination before then
  and drop out of the filter, so the aggregate was dominated by Big Empty
  (n=47) and Schooltime (n=37). Per map, the same eight teams finish at longest
  **36 on Big Empty, 19 on Schooltime, 9 on Default, 4 on Queen Of Spades**.
  Target the cap, not a length.

Splitting off *half* (bot4's rule) is the worst of both: it never builds a swarm
(both halves must regrow to 4) and it forfeits tiebreak 1.

## 5. The tiebreak loses games we are winning

Four games against Micron ran the full 500 rounds. We had far more total length
and lost every one, because tiebreak 1 is **longest single dragon**, total
length only second:

| map | our total | theirs | our longest | theirs |
|---|---|---|---|---|
| Big Empty | 721 | 257 | 34 | 49 |
| Schooltime | 145 | 33 | **4** | 9 |
| Trophy | 78 | 69 | **4** | 16 |
| Colosseum | 80 | 13 | **4** | 7 |

## 6. Benchmarking notes

- **Play every pair in both colours.** Seat and bot identity are otherwise
  perfectly confounded, and 4-6 of 9 maps flip winner on seat alone.
- **Do not tune on Arena or Colosseum.** Favourite win rate at >100 ELO gap is
  73.0% on Big Empty and 71.6% on Schooltime versus 65.3% on Colosseum and 67.2%
  on Arena — a third of small-map games are coin flips regardless of bot quality.
- **9 games per pair is not a sample.** At n=9 only differences above ~33pp are
  distinguishable from noise.
- Unranked battles do **not** move ELO. The reason to be sparing is that all
  battles are publicly viewable, so each one shows an opponent your strategy.
- The autoscrim is ranked and automatic, every 2h, whenever you have an active
  submission. Not challenging anyone does not protect your rating.


## 7. Still on the table: nobody is using `get_pearl_time()`

Tiles expose the number of rounds until they next try to spawn a pearl, and no
bot of ours reads it. Targeting a low countdown naively makes things *worse* —
it pins dragons in place, because on Schooltime 86% of tiles never spawn, so a
dragon always has some live tile in its window and oscillates between two of
them while the board fills with food it never walks to.

The fix is one condition: only walk to a countdown tile if the pearl will be
there when you arrive, `countdown <= steps + 3`. In a separate bot built to
imitate the top teams, that single change took Schooltime population from **7
to 41 at round 100** and **21 to 62 at round 200**.

Related: these maps are mostly dead ground. Schooltime has 326 live tiles out
of 2400; Queen Of Spades 442 of 875. Map control of the fast-respawn blocks is
where the income is.
