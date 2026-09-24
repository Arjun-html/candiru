# Bots

Tracks every bot in this repo and its strategy. Update this file whenever a bot is added or its
logic changes.
New bot: `bash .claude/skills/new-bot/new_bot.sh <name> [source_bot]` adds the folder and a stub here.
Standings: `python .claude/skills/tournament/results.py matrix` (from `results.csv`, fed by every tournament run).

## mybot
Scaffold-default bot (`unswbc init` output). Shuffles the four directions and steps onto the
first one that isn't kelp and doesn't have a dragon on it; falls back to north.

## bot1 — random walker
Same as `mybot`: shuffles directions each turn and takes the first passable, dragon-free
neighbour. No pearl-seeking, no split logic. Baseline for comparison.

## bot2 — greedy pearl collector
Finds the nearest visible pearl (wrapped-map Manhattan distance) and orders directions to close
the gap on both axes, falling back to the rest of the direction list, then to random shuffle if
no pearl is visible. Only ever moves — never splits.

## bot3 — right-hand wall follower
Classic maze-solving rule: each turn tries turn-right, straight, turn-left, then reverse
(u-turn), relative to its current facing, taking the first passable/safe option. No pearl
targeting, no map awareness beyond the immediate tile — behaviour emerges entirely from the
wall-following order.

## bot4 — grower/splitter
Same pearl-chasing logic as bot2, but before moving it checks `can_split(length // 2)` every
turn and splits its tail in half whenever legal, trading a long single dragon for more dragons
under the team's unit limit. Splitting is checked first and takes priority over movement that
turn. Strategy: maximize dragon count early via aggressive splitting, then have each half
independently pearl-chase — more bodies covering more of the board outweighs one bigger body.

## bot5 — sonar coordinator
Pearl-chasing like bot2/bot4, plus inter-dragon coordination: encodes its intended next tile as
`x * 10_000 + y` and broadcasts it via `send_sonar` after each move. Before choosing a direction,
it decodes all incoming sonar messages this turn into a "claimed" tile set and treats those tiles
as unsafe, so teammates steer away from tiles another dragon just claimed instead of bunching up
on the same pearl. No splitting.

## reef_shark — personality-driven adaptive pearl chaser

The most complex bot in the repo. Built to fix three problems observed across earlier
round-robin testing: dying by self-collision in narrow spaces, blindly walking into portals
once too long to survive wherever they let out, and unconditional splitting (bot4's approach)
that spawns fragile short dragons instead of accumulating length.

**Personality**: each dragon decides once, from `ct.get_id() % 2`, whether it's *aggressive*
(odd id) or *conservative* (even id) — stable for that dragon's life, and naturally ~50/50 across
splits since every split spawns a fresh process with its own id, no shared memory needed.

**Pearl targeting (both personalities)**: sticky — commits to one visible pearl and keeps
pursuing it turn to turn rather than recomputing "nearest" every turn, which was causing
flip-flopping between two similar-distance pearls (`STICKY_MARGIN`, only switches targets for
one meaningfully closer). Movement direction is chosen by scoring all safe candidate directions
(pearl distance weighted ×3, positional bias weighted ×1) rather than a fixed preference order,
so the personality's positional pull blends with pearl-chasing instead of overriding it.

**Aggressive dragons**: always move to close distance on the nearest visible enemy head and
trade a head-on kill once adjacent (`hunt_direction`) — this takes priority over everything else
that turn. When no enemy is visible, drift toward the map's geometric center as a secondary pull
alongside pearl-chasing. Skip the dead-end lookahead entirely (risk-tolerant). Split early and
small (`AGGRESSIVE_SPLIT_LENGTH=5` → `AGGRESSIVE_SPLIT_KEEP=3`) to spawn more aggressive units
faster.

**Conservative dragons**: never seek a fight, and drift away from whichever dragon (friend or
foe) is currently nearest in vision as a secondary pull alongside pearl-chasing. Once at
`LONG_THRESHOLD` (6) length, require the landing tile to have ≥2 safe exits (not just the way
back) before taking a move — the "don't turn into a dead end" lookahead. Once at
`PORTAL_AVOID_LENGTH` (4), avoid stepping through portal edges (fallback to one only if it's the
only legal move) since a blind teleport can strand a long dragon somewhere too small. Split later
and bigger (`SPLIT_LENGTH=8` → `SPLIT_KEEP=5`), favoring accumulated length over unit count.

**Results** (see `.claude/skills/tournament/`): went 17-1 against the rest of the roster
(bot1-5, mybot; 3 random-map games each) in early testing — swept bot1/2/3/5/mybot 3-0, took 2/3
from bot4. bot4 remains the toughest single matchup: its unconditional every-turn splitting
floods tight maps with more dragons than reef_shark's threshold-gated splitting can match,
especially on `default_small`/`queen_of_spades`/`trophy`. All thresholds (`LONG_THRESHOLD`,
`PORTAL_AVOID_LENGTH`, `SPLIT_LENGTH`/`SPLIT_KEEP`, `AGGRESSIVE_SPLIT_LENGTH`/`_KEEP`,
`PEARL_WEIGHT`/`POSITION_WEIGHT`) are arbitrary starting points, not tuned.

## mako_shark — mothership + suicide bombers
Dylan's idea: one long dragon that sheds a stream of aggressive kamikaze dragons, and
occasionally another mothership. Roles need no communication: a dragon whose first turn is
round ≤1 is a **mothership**, a split child of length 3 is a **bomber**, a child of length ≥6 is
a **backup mothership**. (Maps spawn up to 4 dragons per team, so there can be 4 fleets.)

**Mothership** — the score. Each turn scores the four steps and picks from tiered filters
(never cross a portal → never end next to an enemy head → never within 2 → pocket big enough →
prefer ≥3 away). Key pieces:
- Pearl targeting via BFS over the window; sticky target (won't flip-flop for <2 tiles gain);
  if no pearl is visible it heads for the tile whose countdown means a pearl will be there
  soonest (`pearl_time` is visible).
- Trap check uses a persistent `Memory` of every kelp edge ever seen plus its own head trail
  (= its body), so a coil sealed outside the 7x7 window is still detected. Flood-fill exits
  early once `length + 4` tiles are reachable.
- Crowd avoidance: penalty per dragon segment (any team, own body included) within 2 of a step.
- Panic mode: with ≥2 enemy heads in view the pearl weight drops to ~0 and it maximises
  distance from all of them.
- Splitting: sheds a length-3 bomber every 3 rounds while an enemy has been seen (directly or
  via sonar) in the last 40 rounds, else every 20 rounds; never below a floor of
  `max(5, round/20)`; never after round 430; never with an enemy head within 3 (split costs the
  turn). Every 5th split, or whenever it's the team's last dragon, the child is a length-6
  backup mothership instead.
- Broadcasts `0xA1<<24 | x<<12 | y` (its post-move position) by sonar every turn.

**Bomber** — expendable, length 3. The rules make it a guaranteed 2-tile kill: sprint of n
steps costs n−1 segments and resolves fully before anyone else moves, so any enemy head within
BFS distance ≤ length−1 along a clear path is dead on the spot (`make_moves`). A kill drops
⌈L/2⌉ pearls. It only pays for that head-on trade against an enemy showing ≥3 segments, or any
enemy within 4 of the mothership (bot4's swarm of length-2 dragons isn't worth 3 segments each).
Otherwise: step into the tile the enemy is about to enter (its facing), then close distance.
Idle: screens off the mothership's bow — each bomber on a flank by `id % 3`, never in the 3-tile
lane straight ahead of it, never adjacent to its head — using the mothership's sonar position
or a directly-seen friendly dragon with ≥4 visible segments. Relays mothership position and
broadcasts enemy sightings (`0xA2`) so nearby bombers converge.

**Versions.** `mako_shark/` is v2 (below). `mako_shark_v1/` is the first version, kept for
comparison: window-only trap check, no exits tier, no teammate spacing, bombers escort at
head-clearance 2. Its 25–2–1 "random map" result was a kind draw; on a full round robin vs
bot4/reef_shark/bot5 across all 9 maps (seed 1, 2026-09-22) v1 went **14–13** and v2 **15–12** —
same strength overall, v2 clearly better on kelp/corridor maps (queen_of_spades vs bot4: v2
win, v1 loss).

**v2 additions** (from dumping the mothership's window on every fatal turn on queen_of_spades):
- Tail-aware region check: own segments count as free once the tail will have vacated them by
  the time the head could arrive (+2 moves slack), so following your own tail is recognised as
  safe and a sealed pocket of any size is not. Region size is scored (roomier = better), not
  just thresholded, and the mothership never splits while every option is boxed in.
- "≥2 onward exits" tier for both roles — a corridor tile is one a teammate can seal.
- Mothership keeps off friendly heads (tier) and bodies (score), since escorts running
  alongside were walling it into kelp corners.
- Bombers keep 2 from the mothership head and 1 from every segment of it, and repel each
  other (crowd penalty) so they stop bunching on the escort spot and boxing each other in.
- No split if the child's head (the tail tile) has no free neighbour.
- Tier order (mothership): not portal → not adjacent to enemy head → region ≥ length+4 → not
  adjacent to friendly head → >2 from enemy head → ≥2 exits → >3 from enemy head.

**Known weaknesses (both versions):** reef_shark's head-hunters on small maps early (arena,
default_small: the mothership gets rammed before it has an escort), and bot4-style
mass-splitters on tiny maps (Colosseum) or open maps where they hit the 64 cap (help) — the
board saturates and the mothership gets boxed in regardless of pathing.

---

## hammerhead / hammerhead_kami / hammerhead_port — safe-pocket pearl chaser

**hammerhead** — BFS to the nearest pearl in the 7x7, but every candidate step is gated on
a flood fill of the pocket behind it: a step is only taken if the reachable free space there is
at least `length + 1` (capped at 12). If nothing has an escape it takes the roomiest step
anyway. Splits 2 segments off every turn it can, until round 400. That one escape check is what
stopped the bots killing themselves (17-1 vs tiger_shark).

**hammerhead_kami** — hammerhead plus `enemy_head_trade()`: step into an adjacent *enemy
head* when their visible segment count exceeds our length. A head-to-head kills both dragons,
so it is a straight length swap, and we field many short dragons against their few long ones.
62-28 vs hammerhead over 90 games. The docstring in its `main.py` lists three rejected
alternatives (rho-based split pricing, later split cutoffs) and the measured population
collapse after round 400 that none of them fixed.

**hammerhead_port** — kami plus portal use. kami never crossed a portal on purpose: the
BFS refused to path through one, and `is_safe`/`has_escape` judged a portal step by the tile
`add_dir()` points at — which is *not* where the portal lands you, so the step was accepted
or rejected on a tile the dragon never visits. Where that phantom tile is walled in, kami reads
the only exit from its pocket as a dead end and circles at home all game, scoring whatever
length it spawned with (the leaderboard losses Arjun flagged). Changes:
- a portal edge is safe and counts as an escape by definition (`pocket_size` already treated
  one as a way out; the per-step checks did not),
- after `STARVE_TURNS` (6) turns with no pearl reachable in the window, a second BFS targets the
  nearest portal edge and crosses it — a portal is a goal, never a waypoint, since where it
  lands is unseeable,
- `PORTAL_COOLDOWN` (25) turns before hunting another one, so the dragon does not bounce back
  and forth through the same pair.

`test_portal_seek.py` (repo root) is the check: a dragon sealed in a pearl-less pocket whose
only exit is a portal onto a walled cell. kami never leaves in 200 turns; port leaves by turn 7
(median).

MEASURED: 20-16 vs hammerhead_kami over 36 games (the 6 maps that have portal edges, both
colours, 3 seeds, all run serially). That is 55.6%, z = +0.67 -- a lean, not a result. The
solid evidence is the defect it fixes, below.

The first version triggered the portal hunt on hunger (6 turns with no reachable pearl), which
fires constantly in open play: the whole swarm converged on the nearest portal mouth and rammed
each other there. On `default` it took 73 head-to-heads to kami's 51 on similar total deaths,
and since a cross-team head-to-head kills both dragons and counts for both sides, the extra ~22
were friendly. Final dragon count on `default`, v1 vs v3, six games each:

    v1 port:  4, 5 | 3, 4 | 1, 5      (pinned under 6 in every game, both colours)
    v3 port:  6, 58 | 33, 5 | 6, 37
    map:      0-6 under v1, 3-3 under v3

NOT YET MEASURED: the case this was built for. None of the nine local maps seals a spawn area
behind a portal, so kami never actually gets locked out here -- these 36 games measure the cost
of carrying the fix (about zero), not its benefit. A map with the pathology would settle it.

---

## Env vars

- `BOT_SEED` — read by bot1, bot2, bot4, bot5 (anything using `random`) as
  `random.seed(os.environ.get("BOT_SEED"))`. Unset means Python's default (OS entropy) seeding.
  Set it per run to get reproducible-but-varied results across repeats, e.g.
  `BOT_SEED=3 unswbc run maps/default.map bot1 bot4`. bot3 has no randomness and ignores it.
