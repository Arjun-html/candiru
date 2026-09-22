#!/bin/bash
# Compare two bot versions on the IDENTICAL set of games: each plays the same opponents on
# every map at the same seed, one game at a time. Prints a per-map side-by-side table.
# Usage: compare_bots.sh <botA> <botB> [opponents...]   (default opponents: bot4 reef_shark bot5)
# Env: SEED (default 1), MAPS (default "maps/*.map"), OUT (default replays_compare)
set -u
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
A="${1:?usage: compare_bots.sh <botA> <botB> [opponents...]}"
B="${2:?usage: compare_bots.sh <botA> <botB> [opponents...]}"
shift 2
OPP=("$@"); [ "${#OPP[@]}" -eq 0 ] && OPP=(bot4 reef_shark bot5)
SEED="${SEED:-1}"; MAPS="${MAPS:-maps/*.map}"; OUT="${OUT:-replays_compare}"
mkdir -p "$OUT"

result() {  # map bot opp -> "W"/"L"/"D"/"?"  (bot is always team A)
  local log="$OUT/$1@@$2_vs_$3@@r$SEED.log"
  if [ ! -f "$log" ]; then
    BOT_SEED=$SEED unswbc run "maps/$1.map" "$2" "$3" -o "${log%.log}.replay" > "$log" 2>&1
    # build race shows up as a round-0 crash in a completed game: rerun once
    if grep -q "round 0: bot [0-9]* (team A) died: no valid action" "$log"; then
      BOT_SEED=$SEED unswbc run "maps/$1.map" "$2" "$3" -o "${log%.log}.replay" > "$log" 2>&1
    fi
  fi
  if grep -q "team A wins" "$log"; then echo W
  elif grep -q "team B wins" "$log"; then echo L
  elif grep -q "draw" "$log"; then echo D
  else echo "?"; fi
}

printf "%-18s %-12s %6s %6s\n" map opponent "$A" "$B"
declare -A wins; wins[$A]=0; wins[$B]=0
for mapfile in $MAPS; do
  m=$(basename "$mapfile" .map)
  for o in "${OPP[@]}"; do
    ra=$(result "$m" "$A" "$o"); rb=$(result "$m" "$B" "$o")
    [ "$ra" = W ] && wins[$A]=$(( wins[$A] + 1 ))
    [ "$rb" = W ] && wins[$B]=$(( wins[$B] + 1 ))
    flag=""; [ "$ra" != "$rb" ] && flag="  <-- differs"
    printf "%-18s %-12s %6s %6s%s\n" "$m" "$o" "$ra" "$rb" "$flag"
  done
done
echo
echo "wins: $A=${wins[$A]}  $B=${wins[$B]}  (out of $(( $(ls $MAPS | wc -l) * ${#OPP[@]} )) each; logs in $OUT)"
python "$(dirname "$0")/results.py" record "$OUT"
