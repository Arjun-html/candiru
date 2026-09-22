#!/bin/bash
# Round-robin every bot against every other bot, across maps and seeds, in parallel.
# Usage: run_tournament.sh [output_dir] [maps_glob] [seeds] [parallelism] [bots...]
set -u
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

OUT="${1:-replays_tournament}"
MAPS_GLOB="${2:-maps/*.map}"
SEEDS="${3:-1 2 3 4 5}"
PARALLEL="${4:-8}"
shift $(( $# < 4 ? $# : 4 )) 2>/dev/null || true

if [ "$#" -gt 0 ]; then
  BOTS=("$@")
else
  BOTS=()
  for d in */; do
    d="${d%/}"
    [ -f "$d/bot.toml" ] && [ -f "$d/main.py" ] && BOTS+=("$d")
  done
fi

if [ "${#BOTS[@]}" -lt 2 ]; then
  echo "need at least 2 bot directories (each with bot.toml + main.py)"; exit 1
fi

mkdir -p "$OUT"
echo "bots: ${BOTS[*]}"
echo "maps: $MAPS_GLOB"
echo "seeds: $SEEDS"
echo "parallelism: $PARALLEL"

jobs_file=$(mktemp)
for mapfile in $MAPS_GLOB; do
  mapname=$(basename "$mapfile" .map)
  for ((i=0; i<${#BOTS[@]}; i++)); do
    for ((j=i+1; j<${#BOTS[@]}; j++)); do
      a="${BOTS[$i]}"; b="${BOTS[$j]}"
      for r in $SEEDS; do
        echo "$mapfile|$a|$b|$r" >> "$jobs_file"
      done
    done
  done
done

total=$(wc -l < "$jobs_file")
echo "total games: $total"

run_one() {
  IFS='|' read -r mapfile a b r <<< "$1"
  mapname=$(basename "$mapfile" .map)
  out="$2/${mapname}@@${a}_vs_${b}@@r${r}"
  if [ -f "${out}.replay" ]; then return 0; fi
  BOT_SEED="$r" unswbc run "$mapfile" "$a" "$b" -o "${out}.replay" > "${out}.log" 2>&1
}
export -f run_one

# first pass: parallel. Concurrent workers can race on the same bot's build cache on
# Windows (PermissionError on .unswbc-build/__pycache__), so a handful of jobs can fail —
# that's expected, the retry pass below mops them up sequentially.
cat "$jobs_file" | xargs -P "$PARALLEL" -I {} bash -c 'run_one "$1" "$2"' _ {} "$OUT"

# retry pass: sequential, no race possible, repeat until stable or a few rounds pass
for attempt in 1 2 3; do
  missing=0
  while IFS='|' read -r mapfile a b r; do
    mapname=$(basename "$mapfile" .map)
    out="$OUT/${mapname}@@${a}_vs_${b}@@r${r}"
    if [ ! -f "${out}.replay" ]; then
      missing=$((missing+1))
      BOT_SEED="$r" unswbc run "$mapfile" "$a" "$b" -o "${out}.replay" > "${out}.log" 2>&1
    fi
  done < "$jobs_file"
  echo "retry pass $attempt: $missing missing replays"
  [ "$missing" -eq 0 ] && break
done

rm -f "$jobs_file"
echo "ALL DONE: $(ls "$OUT"/*.replay 2>/dev/null | wc -l) / $total replays written"
python "$(dirname "$0")/results.py" record "$OUT"
