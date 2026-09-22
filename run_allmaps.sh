#!/bin/bash
set -e
bots=(bot1 bot2 bot3 bot4 bot5)
for mapfile in maps/*.map; do
  mapname=$(basename "$mapfile" .map)
  for i in "${!bots[@]}"; do
    for j in "${!bots[@]}"; do
      if [ $i -lt $j ]; then
        a=${bots[$i]}; b=${bots[$j]}
        for r in 1 2 3 4 5; do
          out="replays_allmaps/${mapname}_${a}_vs_${b}_r${r}"
          BOT_SEED=$r unswbc run "$mapfile" "$a" "$b" -o "${out}.replay" > "${out}.log" 2>&1
        done
      fi
    done
  done
  echo "done: $mapname"
done
