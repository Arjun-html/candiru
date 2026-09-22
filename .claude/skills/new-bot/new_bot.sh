#!/bin/bash
# Scaffold a new bot folder from mybot/ and add a BOTS.md stub.
# Usage: new_bot.sh <name> [source_bot]   (source_bot defaults to mybot; use it to fork a variant)
set -eu
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
NAME="${1:?usage: new_bot.sh <name> [source_bot]}"
SRC="${2:-mybot}"
[ -d "$NAME" ] && { echo "$NAME already exists"; exit 1; }
[ -f "$SRC/bot.toml" ] && [ -f "$SRC/main.py" ] || { echo "$SRC is not a bot folder"; exit 1; }
mkdir "$NAME"
cp "$SRC/bot.toml" "$SRC/helper.py" "$SRC/main.py" "$NAME/"
if [ "$SRC" = mybot ]; then
  printf '"""%s: TODO one-line strategy."""\n' "$NAME" | cat - "$NAME/main.py" > "$NAME/main.py.tmp" && mv "$NAME/main.py.tmp" "$NAME/main.py"
fi
# BOTS.md stub, inserted before the trailing "## Env vars" section
python - "$NAME" "$SRC" <<'EOF'
import sys
name, src = sys.argv[1], sys.argv[2]
p = "BOTS.md"; s = open(p, encoding="utf-8").read()
stub = f"## {name}\nTODO: strategy summary (forked from `{src}`).\n\n"
marker = "---\n\n## Env vars"
s = s.replace(marker, stub + marker, 1) if marker in s else s + "\n" + stub
open(p, "w", encoding="utf-8").write(s)
EOF
echo "created $NAME/ from $SRC; BOTS.md stub added"
echo "smoke test: unswbc run maps/default.map $NAME bot1 -o /tmp/$NAME.replay"
