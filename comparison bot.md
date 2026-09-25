# hammerhead2.0 microstrategy comparison

Compared the updated `hammerhead2.0` against the original `hammerhead2.0` tactical variant from
commit `82f6a86` using identical serial games:

```bash
PATH="/home/runner/.local/bin:$PATH" \
SEED=1 OUT=replays_compare_hh_final \
bash .claude/skills/tournament/compare_bots.sh hammerhead2.0 hammerhead2_baseline bot4 mako_shark
```

## Strategy changes tested

- opportunistic short sprint kills into visible enemy heads
- forward-bias when no pearl path is available
- larger local escape search (`ESCAPE_CAP = 15`)
- safer split gating that requires a roomy non-portal follow-up
- teammate crowding penalties to reduce self-sealing after splits
- direct portal filtering for adjacent head-trade decisions

## Identical-game comparison

| Map | Opponent | Updated | Baseline |
| --- | --- | --- | --- |
| Colosseum | bot4 | D | L |
| Arena | bot4 | L | L |
| big_empty | bot4 | W | W |
| default | bot4 | W | W |
| default_small | bot4 | W | W |
| help | bot4 | L | W |
| queen_of_spades | bot4 | W | W |
| schooltime | bot4 | W | W |
| trophy | bot4 | W | L |
| Colosseum | mako_shark | D | W |
| Arena | mako_shark | W | W |
| big_empty | mako_shark | W | W |
| default | mako_shark | W | W |
| default_small | mako_shark | W | W |
| help | mako_shark | W | W |
| queen_of_spades | mako_shark | L | L |
| schooltime | mako_shark | W | W |
| trophy | mako_shark | W | W |

## What improved

- **Against `bot4`** the updated microstrategy reduced losses from **3 to 2** and added one draw
  on the same 9-map set (`6W-1D-2L` vs `6W-0D-3L`).
- The biggest gains were on **Colosseum** (loss → draw) and **trophy** (loss → win), which match
  the goal of improving short-range tactical survival and trades in cramped fights.
- `default_small` also stayed favorable while preserving wins on the larger maps.

## What did not improve

- **Against `mako_shark`** the result softened slightly from `8W-0D-1L` to `7W-1D-1L`; the win on
  Colosseum became a draw while the rest of the matchup stayed the same.

## Takeaway

The revised close-combat microstrategy improves the `bot4` matchup on the identical checked game
set by converting one loss into a draw and another loss into a win, while mostly preserving the
existing `mako_shark` performance profile. Further tuning is still needed if we want a clear
overall improvement across both strong opponents.

---

# hammerhead3.0 comparison

`hammerhead3.0` keeps `hammerhead2.0` as the base model and only changes one weak replay pattern:
it blocks splits when the local window is already crowded, and it now requires **two** roomy
non-portal follow-up moves before splitting. This targets the repeated self-boxing / wall deaths
seen after local swarms form on cramped maps.

## Weak-map comparison

Compared on the replay-identified weak maps:

```bash
PATH="$(python -m site --user-base)/bin:$PATH" \
MAPS="maps/arena.map maps/Colosseum.map maps/default_small.map maps/help.map maps/trophy.map" \
SEED=1 OUT=replays_compare_hh3_probe2 \
bash .claude/skills/tournament/compare_bots.sh hammerhead3.0 hammerhead2.0 bot4 mako_shark
```

| Map | Opponent | hammerhead3.0 | hammerhead2.0 |
| --- | --- | --- | --- |
| arena | bot4 | W | W |
| arena | mako_shark | W | W |
| Colosseum | bot4 | D | D |
| Colosseum | mako_shark | D | D |
| default_small | bot4 | W | L |
| default_small | mako_shark | W | W |
| help | bot4 | W | W |
| help | mako_shark | W | W |
| trophy | bot4 | L | L |
| trophy | mako_shark | W | W |

Result on the weak-map set: **hammerhead3.0 7 wins vs hammerhead2.0 6 wins**.

## Full 9-map comparison

```bash
PATH="$(python -m site --user-base)/bin:$PATH" \
SEED=1 OUT=replays_compare_hh3_full \
bash .claude/skills/tournament/compare_bots.sh hammerhead3.0 hammerhead2.0 bot4 mako_shark
```

Result on the full 9-map set: **13 wins each**.

## Summary

- `hammerhead3.0` improved the targeted weak-map sample by converting `default_small` vs `bot4`
  from a loss to a win.
- Across the full checked 9-map seed-1 set, it stayed performance-neutral relative to
  `hammerhead2.0`.
- So this is a conservative upgrade aimed specifically at replay-proven crowding/split failures,
  not yet a broad all-map leap.
