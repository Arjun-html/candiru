---
name: bot-autopsy
description: Find out WHY a bot's dragons die ("hit a wall", "hit itself", "hit another dragon", "lost a head-to-head") by dumping the dragon's actual 7x7 view on its fatal turns and reading the ASCII. Use when the user points at a game/log where the bot makes "stupid mistakes", asks why dragons keep dying, or before bisecting a regression.
---

Every one of these log lines means the same thing: on that turn the bot **had no legal move**
(or chose a doomed one). Vision is live, so it is never stale information — it is always the
board state a few turns earlier that trapped it. Guessing the cause from the log does not work
(tried; three wrong theories in a row). Look at the window.

## Steps

1. Copy `botdebug.py` from this folder into the bot's directory (`bot.toml` includes `*.py`,
   so it ships with the bot — delete it again before submitting).
2. In the bot, add a `DEBUG = True` constant (env vars do **not** reach bot processes — only
   `BOT_SEED` does) and call the dump at the decision points that matter:
   - where the bot falls back because no candidate move survived:
     `if DEBUG: botdebug.dump(ct, game, "no legal step")`
   - right after choosing a step that fails the bot's own safety check (trap/region/exits) —
     this is the *onset* of doom, usually 2–5 turns before the death:
     `if DEBUG: botdebug.dump(ct, game, f"doomed step {d.value}", trail=my_trail)`
   Pass the bot's own head-position history as `trail` if it keeps one; the tail..head list
   tells you which own segments will vacate soon.
3. Run **one** match on the map from the user's log, same bots, same seed if known:
   `BOT_SEED=1 unswbc run maps/<map>.map <bot> <opponent> -o /tmp/autopsy.replay 2>&1 | grep died`
4. Read `<bot>/.unswbc-build/bot_dump.txt` (unswbc runs the built copy, so the file lands
   there). Start from the *first* "doomed" frame for the dragon that died, not the last.
5. Reading a frame — each cell is two characters, `<tile><east-edge>`, and the line under a row
   marks south edges:
   ```
   . . e e|o . .     H/# you   F/f friend   E/e enemy   o pearl   ? outside window
       -             | kelp on the east edge of that tile   - kelp on its south edge
   ```
   Column k is x = head.x − 3 + k; row is y = head.y − 3 + row. Cross-check with the
   `parts (id,x,y,is_head)` list — that is how a "bomber sealed the corridor" and a "the
   mothership itself stepped next to the bomber's body" were told apart.
6. Name the mechanism in one sentence before touching code ("teammate's body ran alongside
   and closed the corridor", "spiralled into own coil chasing pearls", "chose certain death
   over probable death because tier X outranks tier Y"). Then fix that mechanism, re-run the
   same match, confirm the frame is gone, and only then run the `tournament` skill's
   `compare_bots.sh` to check nothing else regressed.
7. Remove `botdebug.py` and set `DEBUG = False` (or gate on the constant) before finishing.

## Mechanisms already found this way (mako_shark, 2026-09-21/22) — check these first
- Own coil: pearl-chasing spirals inward; a region check that counts own segments as blocked
  can't see that following the tail is safe, and a window-only flood fill can't see the coil's
  far end. Fix: remember own trail + kelp map-wide; count a segment free if it vacates before
  the head can arrive.
- Teammate seals the corridor: an escort's *body* running alongside, or two dragons abreast in
  a 3-wide corridor. Head-clearance rules don't help — it's bodies. Keep a gap from every
  segment, prefer tiles with ≥2 onward exits.
- Tier order: "not adjacent to enemy head" ranked above "pocket big enough" makes the bot pick
  certain death over a 1-in-3 risk. Certain-death filters go first.
- Splitting while boxed in: the split costs the turn.
- Child spawned head-first into a dead end (the parent's tail was in a kelp corner).
- Swarm saturation (bot4 on Colosseum/help): the whole window is enemy bodies by round ~35.
  Not a pathing bug — nothing to fix in movement.
