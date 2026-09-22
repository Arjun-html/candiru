---
name: new-bot
description: Create a new bot folder in this repo (bot.toml, helper.py, main.py) from the scaffold or by forking an existing bot, and add its BOTS.md entry. Use when the user asks to make/write/add a new bot, a variant of an existing bot, or a "v2" of one.
---

```
bash .claude/skills/new-bot/new_bot.sh <name>                # fresh from mybot/ scaffold
bash .claude/skills/new-bot/new_bot.sh <name> <existing_bot> # fork a variant (e.g. mako_shark_v2 mako_shark)
```

Then:
1. Write the strategy in `<name>/main.py`. `helper.py` is the SDK and the source of truth for
   the API — read it, not the docs prose. Every dragon is its own process: module-level
   globals are per-dragon memory; the only inter-dragon channel is sonar.
2. Roles without communication: decide on the first turn from `game.get_round_num() <= 1`
   (starters — up to 4 per team, round 0) and `ct.get_length()` (a split child's size).
3. Smoke test before anything else: `unswbc run maps/default.map <name> bot1 -o /tmp/x.replay`.
   A bot that prints nothing valid dies at round 0 ("no valid action"); a crash shows as
   "exited with code 1" with no traceback — run the match again after adding a try/except that
   writes the traceback to a file next to `__file__`.
4. Replace the BOTS.md stub with the real entry (1–2 lines for a single-rule bot, a full
   writeup for anything with interacting rules) — same change as the code, per CLAUDE.md.
5. Measure with the `tournament` skill: `compare_bots.sh` against the bot it forked from, or
   `run_tournament.sh` with parallelism 1 if the user is on the machine.
6. Dying in ways you don't understand? `bot-autopsy` skill before changing constants.

Keep `helper.py` a verbatim copy of `mybot/helper.py`; if the competition updates the SDK,
re-copy it into every bot folder rather than patching one.
