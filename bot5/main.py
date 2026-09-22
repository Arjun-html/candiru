"""bot5: sonar coordinator. Broadcasts its own position each turn and steers away from tiles
recently announced by teammates, so dragons spread out instead of bunching onto one pearl."""
import helper as unswbc
from helper import Direction, Position
import os
import random

ct: unswbc.Controller
game: unswbc.Game

random.seed(os.environ.get("BOT_SEED"))

def encode(pos: Position) -> int:
    return pos.x * 10_000 + pos.y

def decode(value: int) -> Position:
    return Position(value // 10_000, value % 10_000)

def is_safe(direction: Direction, claimed: set[tuple[int, int]]) -> bool:
    here_tile = ct.get_tile(ct.get_position())
    if not here_tile.get_edge(direction).is_passable():
        return False
    ahead_pos = ct.get_position().add_dir(direction)
    ahead = ct.get_tile(ahead_pos)
    if ahead is not None and ahead.get_dragon() is not None:
        return False
    return (ahead_pos.x, ahead_pos.y) not in claimed

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
    claimed = {(decode(m).x, decode(m).y) for m in ct.get_sonar_messages()}

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
        if is_safe(direction, claimed):
            ct.make_move(direction)
            ct.send_sonar(encode(ct.get_position().add_dir(direction)))
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
