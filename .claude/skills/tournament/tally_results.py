#!/usr/bin/env python3
"""Tally win/loss standings from a tournament output directory of unswbc run logs.
Usage: tally_results.py <output_dir>
"""
import re
import sys
import glob
import os
from collections import defaultdict

def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "replays_tournament"
    wins, losses = defaultdict(int), defaultdict(int)
    draws = 0
    unresolved = []

    for path in sorted(glob.glob(os.path.join(out_dir, "*.log"))):
        name = os.path.basename(path).removesuffix(".log")
        m = re.match(r"(.+)@@(.+)_vs_(.+)@@[rg]\d+$", name)
        if not m:
            unresolved.append(name)
            continue
        _, a, b = m.groups()
        text = open(path, encoding="utf-8").read()
        win = re.search(r"team (A|B) wins", text)
        if win:
            winner, loser = (a, b) if win.group(1) == "A" else (b, a)
            wins[winner] += 1
            losses[loser] += 1
        elif "draw" in text:
            draws += 1
        else:
            unresolved.append(name)

    bots = sorted(set(wins) | set(losses), key=lambda b: -wins[b])
    total = sum(wins.values()) + draws
    print(f"games: {total} (draws: {draws}, unresolved: {len(unresolved)})")
    print(f"{'bot':20}{'W':>6}{'L':>6}")
    for b in bots:
        print(f"{b:20}{wins[b]:>6}{losses[b]:>6}")
    if unresolved:
        print("\nunresolved (check these logs):")
        for name in unresolved:
            print(" ", name)

if __name__ == "__main__":
    main()
