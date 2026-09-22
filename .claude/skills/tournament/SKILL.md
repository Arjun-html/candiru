---
name: tournament
description: Round-robin battle-test every bot in this repo against every other bot, across maps and random seeds, in parallel — then tally win/loss standings. Use when the user asks to test/battle/run bots against each other, run a tournament, or compare bot win rates.
---

Runs a full round-robin: every bot directory (has `bot.toml` + `main.py`) plays every other bot,
on every map, at a range of seeds, using `unswbc run`. Jobs run in parallel via `xargs -P` for
speed, since each match is an independent process.

## Testing one new bot against everyone (the common case)

When you just built/changed one bot and want to know how it does against the rest of the
roster, use `run_vs_all.sh` instead of the full round robin — it plays the target bot against
every other bot 3 times each (3 randomly-picked maps per matchup, no seed looping needed since
map variety already gives you spread):

```
bash .claude/skills/tournament/run_vs_all.sh <target_bot> [output_dir] [games_per_opponent] [opponent1 opponent2 ...]
```

Example:
```
bash .claude/skills/tournament/run_vs_all.sh reef_shark
```

Then tally the same way: `python .claude/skills/tournament/tally_results.py replays_vs_all`.

## Full round robin (every bot vs every bot)

```
bash .claude/skills/tournament/run_tournament.sh [output_dir] [maps_glob] ["seeds"] [parallelism] [bot1 bot2 ...]
```

All args are optional and positional, with sane defaults:
- `output_dir` — default `replays_tournament`
- `maps_glob` — default `maps/*.map` (quote it, e.g. `"maps/default.map"` for just one)
- `"seeds"` — default `"1 2 3 4 5"`, quoted space-separated list, passed as `BOT_SEED` env var
  (bots read it via `random.seed(os.environ.get("BOT_SEED"))` — see [BOTS.md](../../../BOTS.md))
- `parallelism` — default `8`
- `bot1 bot2 ...` — default: auto-discovers every directory with both `bot.toml` and `main.py`

Example — quick test of just two bots on one map:
```
bash .claude/skills/tournament/run_tournament.sh replays_quick "maps/default.map" "1 2 3" 4 reef_shark bot4
```

Example — full tournament, everything, all maps:
```
bash .claude/skills/tournament/run_tournament.sh
```

## Why there's a retry pass

Running many `unswbc run` calls in parallel that share a bot directory can race on that bot's
`.unswbc-build/__pycache__` on Windows — a `PermissionError` when two workers rebuild the same
bot's cache at once. This happened during earlier manual testing (~1-2% of jobs). The script
handles it automatically: a parallel first pass, then up to 3 sequential retry passes (no
parallelism, no race possible) that only touch jobs missing a `.replay` file. Don't try to "fix"
this by increasing parallelism further — the retry pass is the fix.

## After it finishes

Tally standings with:
```
python .claude/skills/tournament/tally_results.py <output_dir>
```
This prints win/loss per bot, ranked, plus a list of any still-unresolved logs (crashes, timeouts)
worth reading directly.

Report the standings table to the user; if any games are unresolved after the retries, read those
specific `.log` files and say what happened rather than silently excluding them.

## The ledger: results.csv (which bot is strong against which, what to deploy)

Every run script ends by appending its games to `results.csv` at the repo root (one row per
game, deduped by run dir + map + seed + pairing; build-race games and crashes are skipped).
Ask it questions with:
```
python .claude/skills/tournament/results.py matrix                 # win-rate matrix + deploy candidate
python .claude/skills/tournament/results.py matrix --since 2026-09-22
python .claude/skills/tournament/results.py matrix --bots mako_shark,bot4,reef_shark
python .claude/skills/tournament/results.py record <dir> [--rename logname=folder]
```
Rows carry an md5 of each bot's `main.py` at record time, so a bot that was edited between
runs shows as different hashes — filter with `--since` when a bot changed. If a run's logs
name a bot by a folder that has since been renamed, record with `--rename old=new`. When the
user asks "which bot should we submit", answer from the matrix's overall column *and* its row
(a bot with a bad matchup against a likely opponent style is not the pick).

## Comparing two versions of a bot (did my change help?)

Use `compare_bots.sh`, never `run_vs_all.sh`, for this. It plays both versions against the same
opponents on every map at the same seed, sequentially, and prints a per-map table with the
games that differ flagged:
```
bash .claude/skills/tournament/compare_bots.sh mako_shark mako_shark_v1            # vs bot4 reef_shark bot5
bash .claude/skills/tournament/compare_bots.sh mako_shark mako_shark_v1 bot4 bot2  # custom opponents
SEED=2 OUT=replays_compare2 bash .claude/skills/tournament/compare_bots.sh a b     # another seed
```
Existing logs in `OUT` are reused, so re-running after editing one bot only replays that bot's
games if you delete its logs (`rm replays_compare/*@@<bot>_vs_*`).

Lessons from the mako_shark work (2026-09-22) — read before trusting any number:
- `run_vs_all.sh` picks random maps, so its result depends on the draw: the same bot scored
  25–2 there and 14–13 on the full-map round robin. Only identical game sets are comparable.
- Some maps (`help`, anything where a splitter hits the 64-dragon cap) vary run to run even
  with the same `BOT_SEED`. One game is not evidence; 3 seeds on a map is the minimum for a
  claim about that map, and a whole-roster difference of ±2 games is noise.
- A completed game whose log has `round 0: bot N (team A) died: no valid action` is the
  parallel `__pycache__` race, not the bot (compare_bots.sh reruns those once automatically).
- When the user is using the machine, run with parallelism 1 (compare_bots.sh already does;
  pass `1` as the 4th arg to `run_tournament.sh`). A full-map round robin of one bot vs three
  opponents takes ~15 min that way — run it in the background and report when done.
- Bisecting a regression by toggling one constant per run does not work at this noise level;
  dump the bot's view on its fatal turns instead (see the `bot-autopsy` skill).
