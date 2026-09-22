#!/usr/bin/env python3
"""Persistent game ledger: results.csv at the repo root, one row per game.

  results.py record <replay_dir> [--rename old=new ...]   append games from a run dir (deduped)
  results.py matrix [--since YYYY-MM-DD] [--bots a,b,..]  win-rate matrix + overall ranking

Columns: date, run_dir, map, seed, bot_a, bot_b, winner (bot name or "draw"), rounds, how,
bot_a_hash, bot_b_hash. Hashes are of <bot>/main.py *at record time* - record right after the
run, or the hash won't match the code that played. --rename maps a log's bot name to the
folder that actually played (e.g. after moving a version folder).
"""
import csv
import glob
import hashlib
import os
import re
import sys
from collections import defaultdict
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
CSV = os.path.join(ROOT, "results.csv")
FIELDS = ["date", "run_dir", "map", "seed", "bot_a", "bot_b", "winner", "rounds", "how",
          "bot_a_hash", "bot_b_hash"]


def bot_hash(bot):
    p = os.path.join(ROOT, bot, "main.py")
    if not os.path.exists(p):
        return ""
    return hashlib.md5(open(p, "rb").read()).hexdigest()[:8]


def load():
    if not os.path.exists(CSV):
        return []
    with open(CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def record(run_dir, renames):
    rows = load()
    seen = {(r["run_dir"], r["map"], r["seed"], r["bot_a"], r["bot_b"]) for r in rows}
    run_name = os.path.basename(os.path.normpath(run_dir))
    added = 0
    hashes = {}
    with open(CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if not rows:
            w.writeheader()
        for path in sorted(glob.glob(os.path.join(run_dir, "*.log"))):
            m = re.match(r"(.+)@@(.+)_vs_(.+)@@[rg](\d+)$", os.path.basename(path)[:-4])
            if not m:
                continue
            mp, a, b, seed = m.groups()
            a, b = renames.get(a, a), renames.get(b, b)
            text = open(path, encoding="utf-8", errors="replace").read()
            win = re.search(r"team (A|B) wins after (\d+) rounds \((?:by |on )?(\w+)\)", text)
            draw = re.search(r"draw after (\d+) rounds", text)
            if win:
                winner = a if win.group(1) == "A" else b
                rounds, how = win.group(2), win.group(3)
            elif draw:
                winner, rounds, how = "draw", draw.group(1), "draw"
            else:
                continue  # crashed / unfinished
            if re.search(r"round 0: bot \d+ \(team [AB]\) died: no valid action", text):
                continue  # build-cache race, not a real game
            key = (run_name, mp, seed, a, b)
            if key in seen:
                continue
            seen.add(key)
            for bot in (a, b):
                hashes.setdefault(bot, bot_hash(bot))
            w.writerow({"date": date.today().isoformat(), "run_dir": run_name, "map": mp,
                        "seed": seed, "bot_a": a, "bot_b": b, "winner": winner, "rounds": rounds,
                        "how": how, "bot_a_hash": hashes[a], "bot_b_hash": hashes[b]})
            added += 1
    print(f"recorded {added} new games from {run_dir} -> {CSV}")


def matrix(since, bots):
    rows = [r for r in load() if r["date"] >= since]
    if bots:
        rows = [r for r in rows if r["bot_a"] in bots and r["bot_b"] in bots]
    if not rows:
        print("no games recorded" + (f" since {since}" if since else ""))
        return
    wins = defaultdict(lambda: defaultdict(int))   # wins[bot][opp]
    games = defaultdict(lambda: defaultdict(int))
    for r in rows:
        a, b = r["bot_a"], r["bot_b"]
        games[a][b] += 1
        games[b][a] += 1
        if r["winner"] == a:
            wins[a][b] += 1
        elif r["winner"] == b:
            wins[b][a] += 1
    names = sorted(games, key=lambda n: -sum(wins[n].values()) / max(1, sum(games[n].values())))
    col = max(6, max(len(n) for n in names))
    print(f"{len(rows)} games" + (f" since {since}" if since else "") + " - row bot's win rate vs column bot")
    print(" " * (col + 1) + " ".join(f"{n[:col]:>{col}}" for n in names) + f" {'overall':>9}")
    for n in names:
        cells = []
        for o in names:
            g = games[n][o]
            cells.append(f"{'-':>{col}}" if n == o or g == 0 else f"{wins[n][o]}/{g}".rjust(col))
        tg, tw = sum(games[n].values()), sum(wins[n].values())
        print(f"{n:<{col}} " + " ".join(cells) + f" {tw}/{tg} {100 * tw // tg:3d}%".rjust(10))
    print("\ndeploy candidate: " + names[0] + "  (highest overall win rate; check its row for weak matchups)")


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ("record", "matrix"):
        print(__doc__)
        sys.exit(1)
    if args[0] == "record":
        renames = dict(x.split("=", 1) for x in args[2:] if "=" in x and not x.startswith("--"))
        record(args[1], renames)
    else:
        since, bots = "", None
        for i, a in enumerate(args):
            if a == "--since":
                since = args[i + 1]
            if a == "--bots":
                bots = set(args[i + 1].split(","))
        matrix(since, bots)


if __name__ == "__main__":
    main()
