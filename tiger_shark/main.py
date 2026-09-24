"""tiger_shark: bot4 plus the one change that measurably beats it.

Built 2026-09-22 from bot4, changing ONE thing: the fallback when no direction
is safe. bot4 called make_move(NORTH) blind, which walked it into its own body
or a teammate; self-inflicted deaths were 64% of its total (30% own body,
34% another body) against 9% for elite ladder teams.

Here the ways to die are ranked by what they cost:
  enemy head  +1  a trade, 1 for 1
  free tile   +2  not actually fatal
  kelp/body   -1  we die alone
  friendly    -3  we lose two dragons

Measured, not assumed: this change alone (v_rank) beat bot4 6-2 across
schooltime / trophy / default_small / big_empty, both colours.

Deliberately NOT included:
  * split-off-2 (v_min) -- did not show a clear gain over bot4 in isolation.
  * round-430 split cutoff -- never isolated, only ever tested inside
    candiru_v1, which LOST to bot4 3-5 across the same maps.
Both stay out until each one wins its own head-to-head.
"""
import helper as unswbc
from helper import Direction, Position
import os
import random

ct: unswbc.Controller
game: unswbc.Game

random.seed(os.environ.get("BOT_SEED"))

def is_safe(direction: Direction) -> bool:
    here_tile = ct.get_tile(ct.get_position())
    if not here_tile.get_edge(direction).is_passable():
        return False
    ahead = ct.get_tile(ct.get_position().add_dir(direction))
    return ahead is None or ahead.get_dragon() is None

def wrapped_delta(a: int, b: int, size: int) -> int:
    diff = (b - a) % size
    return diff if diff <= size // 2 else diff - size

def nearest_pearl() -> Position | None:
    best, best_dist = None, None
    for tile in ct.get_tiles():
        if not tile.has_pearl():
            continue
        pos = tile.get_position()
        here = ct.get_position()
        width, height = game.get_map_size()
        dist = abs(wrapped_delta(here.x, pos.x, width)) + abs(wrapped_delta(here.y, pos.y, height))
        if best_dist is None or dist < best_dist:
            best, best_dist = pos, dist
    return best

def execute_turn() -> None:
    # split off half the tail whenever it's legal, to spread into more dragons
    half = ct.get_length() // 2
    if ct.can_split(half):
        ct.do_split(half)
        return

    target = nearest_pearl()
    directions = Direction.get_direction_list()

    if target is not None:
        here = ct.get_position()
        width, height = game.get_map_size()
        dx = wrapped_delta(here.x, target.x, width)
        dy = wrapped_delta(here.y, target.y, height)
        preferred = []
        if dx > 0:
            preferred.append(Direction.EAST)
        elif dx < 0:
            preferred.append(Direction.WEST)
        if dy > 0:
            preferred.append(Direction.SOUTH)
        elif dy < 0:
            preferred.append(Direction.NORTH)
        directions = preferred + [d for d in directions if d not in preferred]
    else:
        random.shuffle(directions)

    for direction in directions:
        if is_safe(direction):
            ct.make_move(direction)
            return

    # Nothing is safe. Rank the ways to die by what they cost: ramming an enemy
    # head trades 1 for 1, dying alone costs 1, and a friendly head-on costs 2.
    # Blindly stepping north takes a teammate with us far too often.
    best, best_score = Direction.NORTH, -99
    for direction in Direction.get_direction_list():
        here_tile = ct.get_tile(ct.get_position())
        if here_tile is None:
            continue
        if not here_tile.get_edge(direction).is_passable():
            score = -1                      # kelp: we die alone
        else:
            ahead = ct.get_tile(ct.get_position().add_dir(direction))
            part = ahead.get_dragon() if ahead is not None else None
            if part is None:
                score = 2                   # actually free
            elif not part.is_head():
                score = -1                  # body: we die alone
            elif part.get_team() != ct.get_team():
                score = 1                   # enemy head: we trade 1 for 1
            else:
                score = -3                  # friendly head: we lose two dragons
        if score > best_score:
            best, best_score = direction, score
    ct.make_move(best)

def main() -> None:
    global ct, game
    ct, game = unswbc.init()

    while unswbc.update(ct, game):
        execute_turn()
        unswbc.end_turn()

if __name__ == "__main__":
    main()
