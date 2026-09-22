#!/bin/bash
# Play one target bot against every other bot, 3 times each on 3 randomly-picked maps
# (no seed looping — map variety is the source of variety here).
# Usage: run_vs_all.sh <target_bot> [output_dir] [games_per_opponent] [opponent1 opponent2 ...]
set -u
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

TARGET="${1:?usage: run_vs_all.sh <target_bot> [output_dir] [games_per_opponent] [opponents...]}"
OUT="${2:-replays_vs_all}"
GAMES="${3:-3}"
shift $(( $# < 3 ? $# : 3 )) 2>/dev/null || true

if [ "$#" -gt 0 ]; then
  OPPONENTS=("$@")
else
  OPPONENTS=()
  for d in */; do
    d="${d%/}"
    [ "$d" = "$TARGET" ] && continue
    [ -f "$d/bot.toml" ] && [ -f "$d/main.py" ] && OPPONENTS+=("$d")
  done
fi

mapfile -t ALL_MAPS < <(ls maps/*.map)
mkdir -p "$OUT"
echo "target: $TARGET"
echo "opponents: ${OPPONENTS[*]}"
echo "games per opponent: $GAMES (random map each)"

jobs_file=$(mktemp)
for opp in "${OPPONENTS[@]}"; do
  for ((k=0; k<GAMES; k++)); do
    map="${ALL_MAPS[$RANDOM % ${#ALL_MAPS[@]}]}"
    echo "$map|$TARGET|$opp|$k" >> "$jobs_file"
  done
done

total=$(wc -l < "$jobs_file")
echo "total games: $total"

run_one() {
  IFS='|' read -r mapfile a b k <<< "$1"
  mapname=$(basename "$mapfile" .map)
  out="$2/${mapname}@@${a}_vs_${b}@@g${k}"
  if [ -f "${out}.replay" ]; then return 0; fi
  unswbc run "$mapfile" "$a" "$b" -o "${out}.replay" > "${out}.log" 2>&1
}
export -f run_one

cat "$jobs_file" | xargs -P 8 -I {} bash -c 'run_one "$1" "$2"' _ {} "$OUT"

for attempt in 1 2 3; do
  missing=0
  while IFS='|' read -r mapfile a b k; do
    mapname=$(basename "$mapfile" .map)
    out="$OUT/${mapname}@@${a}_vs_${b}@@g${k}"
    if [ ! -f "${out}.replay" ]; then
      missing=$((missing+1))
      unswbc run "$mapfile" "$a" "$b" -o "${out}.replay" > "${out}.log" 2>&1
    fi
  done < "$jobs_file"
  echo "retry pass $attempt: $missing missing replays"
  [ "$missing" -eq 0 ] && break
done

rm -f "$jobs_file"
echo "ALL DONE: $(ls "$OUT"/*.replay 2>/dev/null | wc -l) / $total replays written"
python "$(dirname "$0")/results.py" record "$OUT"
