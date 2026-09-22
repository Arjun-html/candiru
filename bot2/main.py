"""bot2: greedy pearl collector. Heads toward the nearest visible pearl, else walks randomly."""
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
    """Shortest signed step direction from a to b on a wrapped axis of length size."""
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

    for direction in directions:
        if is_safe(direction):
            ct.make_move(direction)
            return

    ct.make_move(Direction.NORTH)

def main() -> None:
    global ct, game
    ct, game = unswbc.init()

    while unswbc.update(ct, game):
        execute_turn()
        unswbc.end_turn()

if __name__ == "__main__":
    main()
