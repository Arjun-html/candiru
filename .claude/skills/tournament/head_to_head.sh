#!/bin/bash
# Play two bots directly against each other: every map, BOTH colours, several seeds.
#
# Use this instead of compare_bots.sh once both bots beat the roster (bot4/reef_shark/bot5).
# There they both sweep, the logs print no final lengths, and the comparison saturates -- the
# only game that can separate them is the two of them playing each other.
#
# Usage: head_to_head.sh <botA> <botB>
# Env:   SEEDS (default "1 2 3"), MAPS (default maps/*.map), OUT (default replays_h2h)
#
# One game at a time, deliberately: a single game already spawns one process per dragon, so
# concurrent games oversubscribe the box and starve bots past their 25ms turn budget, which
# corrupts results rather than merely slowing them. Logs are named for the ledger, so finish
# with: python .claude/skills/tournament/results.py record <OUT>
set -u
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
A="${1:?usage: head_to_head.sh <botA> <botB>}"
B="${2:?usage: head_to_head.sh <botA> <botB>}"
SEEDS="${SEEDS:-1 2 3}"; MAPS="${MAPS:-maps/*.map}"; OUT="${OUT:-replays_h2h}"
mkdir -p "$OUT"

declare -A win; win[$A]=0; win[$B]=0; draws=0; bad=0
printf "%-18s %5s %-6s %s\n" map seed first winner
for s in $SEEDS; do
  for mapfile in $MAPS; do
    m=$(basename "$mapfile" .map)
    for side in ab ba; do
      if [ "$side" = ab ]; then p1=$A; p2=$B; else p1=$B; p2=$A; fi
      log="$OUT/$m@@${p1}_vs_${p2}@@r$s.log"
      [ -f "$log" ] || BOT_SEED=$s unswbc run "$mapfile" "$p1" "$p2" \
          -o "${log%.log}.replay" > "$log" 2>&1
      # a killed run leaves a log with no verdict line; never let one into the tally
      if grep -q "team A wins" "$log"; then w=$p1
      elif grep -q "team B wins" "$log"; then w=$p2
      elif grep -qi "draw" "$log"; then w=draw
      else w=INCOMPLETE; fi
      case "$w" in
        draw) draws=$((draws+1)) ;;
        INCOMPLETE) bad=$((bad+1)) ;;
        *) win[$w]=$(( win[$w] + 1 )) ;;
      esac
      printf "%-18s %5s %-6s %s\n" "$m" "$s" "$p1" "$w"
    done
  done
done
echo
echo "HEAD-TO-HEAD  $A=${win[$A]}  $B=${win[$B]}  draws=$draws  incomplete=$bad"
[ "$bad" -gt 0 ] && echo "delete the incomplete logs and rerun them before quoting this"
echo "record it: python .claude/skills/tournament/results.py record $OUT"
