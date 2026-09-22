#!/bin/bash
bots=(bot1 bot2 bot3 bot4 bot5)
for mapfile in maps/*.map; do
  mapname=$(basename "$mapfile" .map)
  for i in "${!bots[@]}"; do
    for j in "${!bots[@]}"; do
      if [ $i -lt $j ]; then
        a=${bots[$i]}; b=${bots[$j]}
        for r in 1 2 3 4 5; do
          echo "$mapfile|$a|$b|$r"
        done
      fi
    done
  done
done | xargs -P 8 -I {} bash -c '
  IFS="|" read -r mapfile a b r <<< "{}"
  mapname=$(basename "$mapfile" .map)
  out="replays_allmaps/${mapname}_${a}_vs_${b}_r${r}"
  if [ -f "${out}.replay" ]; then exit 0; fi
  BOT_SEED=$r unswbc run "$mapfile" "$a" "$b" -o "${out}.replay" > "${out}.log" 2>&1
'
echo "ALL DONE"
