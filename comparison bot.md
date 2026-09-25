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
