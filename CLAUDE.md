# BATTLECODE

Arjun's entry for the **UNSW Battlecode** competition (game.battlecode.au).

## Docs
https://game.battlecode.au/docs/ — game rules, CLI tools, execution order/timeouts, stdlib/helper reference, IO protocol, map files.

## The game
You control up to 64 autonomous "dragons" (snake-like creatures), each running an independent
copy of your bot with ~25ms/turn. Dragons move around a wrapped grid, collecting **pearls** to
grow longer. At the end of the mission your longest dragon (and its pearls) is scored — goal is
to stay alive and grow the longest dragon relative to the opponent.

Key mechanics:
- **Movement**: 4 directions (N/E/S/W), one step per turn, or a multi-step `make_moves` sprint
  that costs segments.
- **Kelp**: blocks an edge between tiles — impassable.
- **Portals**: paired edges that teleport a dragon crossing them.
- **Splitting**: a dragon can split off part of its tail into a new dragon (`do_split`), subject
  to min size and the team's unit limit.
- **Sonar**: the only inter-dragon communication — dragons don't share memory, so coordination
  happens by sending/reading integer sonar messages.
- **Vision**: each dragon only sees a 7x7 window centered on its head.
- **Death**: hitting another dragon's head, or other collision rules per the docs, kills you.

## Project layout
- `mybot/` — the actual bot submitted via `unswbc` tooling (`bot.toml`, `main.py`, `helper.py`,
  build output in `.unswbc-build/`). This is the canonical bot structure to copy for variants.
- `mybot/helper.py` — the SDK: `Controller`, `Game`, `Vision`, `Tile`, `Edge`, `Direction`,
  `EdgeType`, `Team`, `Position`, etc. Read this for the exact current API before writing bot
  logic — it's the source of truth, not the docs prose.
- `maps/` — map files for local play.
- `*.replay` — replay files from local arena runs (e.g. bot vs itself).

## Goal for this repo
Build and iterate on bot strategies (pathing, pearl collection, splitting, sonar coordination)
and test them against each other locally via the arena/replay tooling.

## Engine facts verified by experiment (not in the docs prose)
- Vision is **live**: your 7x7 shows lower-id dragons at their post-move positions this round.
  So a death logged as "hit a wall / hit itself / hit another dragon" always means the bot had
  no legal move left (boxed in) — never stale information.
- Games start at **round 0 with up to 4 dragons per team** (Colosseum: 1). Role-by-first-turn
  logic must test `round <= 1`.
- A sprint (`make_moves`) resolves entirely inside your turn: a length-L dragon has a
  guaranteed kill on any enemy head within BFS distance L−1 along a clear path.
- Head-to-head kills **both** dragons, teammates included. A kill drops ⌈L/2⌉ pearls.
- Sonar travels in a straight line from the head, stops at the first kelp/dragon, and is
  readable by both teams — tag your messages (e.g. a magic top byte) and don't trust them.
- Env vars do **not** reach bot processes (only `BOT_SEED` does). Debug with a constant and a
  file next to `__file__`; it lands in `<bot>/.unswbc-build/`.
- Replays are a binary format; the `.log` from `unswbc run` is what you read.

## Testing — read before quoting a win rate
- Match results are noisy: some maps differ run to run even at the same seed, and
  `run_vs_all.sh` draws random maps (the same bot scored 25–2 there and 14–13 on a full round
  robin). Compare versions only on the identical game set: `compare_bots.sh` in the
  `tournament` skill. ±2 games across a roster is noise; 3 seeds per map is the minimum for a
  per-map claim.
- `round 0: bot N died: no valid action` in a *completed* parallel run is the build-cache race,
  not the bot — rerun that game serially.
- Run matches **one at a time, always** -- not just when Arjun is on the machine. A single game
  already spawns one process per dragon (up to 128), so 6 concurrent games put 773 Python
  processes on 12 cores: rounds slowed to ~1s, one bot died with `exited with code 3221225794`
  (0xC0000142, Windows resource exhaustion), and others logged `died: no valid action`
  mid-game -- bots starved past their 25ms turn budget. Results from a loaded box are silently
  wrong, not just slow. Game-level parallelism is not available here. Run it in the background.
- Killing a run leaves the in-progress game's `.log` on disk looking like any other. It has no
  `team X wins` line -- check for one before counting a log, or a half-played game silently
  enters the tally.
- Once two bots both beat the roster (bot4/reef_shark/bot5), `compare_bots.sh` cannot separate
  them -- both sweep, and the log prints no final lengths. Use
  `.claude/skills/tournament/head_to_head.sh` to play the two against each other instead, and
  read only the maps where their code can actually differ.
- Every tournament script appends its games to `results.csv` (repo root). `python
  .claude/skills/tournament/results.py matrix` prints the bot×bot win-rate matrix and the
  current deploy candidate — answer "which bot is strongest / what should we submit" from it,
  not from memory of past runs.
- Dragons dying for unclear reasons → `bot-autopsy` skill (dump the window on fatal turns)
  before bisecting constants; bisecting one toggle per run does not converge at this noise.

## Skills in this repo
`new-bot` (scaffold/fork a bot + BOTS.md stub) → `tournament` (`compare_bots.sh`,
`run_tournament.sh`, `run_vs_all.sh`, `tally_results.py`) → `bot-autopsy` (`botdebug.py`).

## Working notes for Claude
- Write multi-line Python patch scripts with the Write tool and run them; bash heredocs in this
  environment mangle quotes and `\n` in Python source.

## Bot tracking workflow
[BOTS.md](BOTS.md) is the running index of every bot in this repo and its strategy. Whenever a
bot is added or its logic changes meaningfully, update its entry there: a 1-2 line summary for
simple/single-rule bots, a fuller writeup for anything with multiple interacting rules
(splitting logic, coordination via sonar, pathing heuristics, etc). Check BOTS.md before writing
a new bot to see what's already been tried, and update it as part of the same change that edits
the bot's `main.py`.
