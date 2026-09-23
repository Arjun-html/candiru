"""f_escape: v_meta plus one rule -- never step into a pocket you cannot get out of.

v_meta's only safety test is "is the next tile passable and empty". That happily
walks a length-2 dragon into a one-tile dead end, and the engine logs the result
as `hit wall` / `hit self` on a later turn when nothing legal is left. This bot
keeps v_meta's greedy axis-stepping and its random-walk exploration untouched and
only adds a liveness filter: flood-fill the free space reachable from each
candidate tile inside the 7x7 window and reject any tile whose pocket is smaller
than the dragon's own length. Anything this bot gains over v_meta is
attributable to the escape check alone.
"""
import helper as unswbc
from helper import Direction, Position
import os
import random
from collections import deque

SPLIT_CUTOFF = 400
ESCAPE_CAP = 12          # stop the flood fill once the pocket is clearly big enough

ct: unswbc.Controller
game: unswbc.Game

random.seed(os.environ.get("BOT_SEED"))


def is_safe(direction: Direction) -> bool:
    here_tile = ct.get_tile(ct.get_position())
    if not here_tile.get_edge(direction).is_passable():
        return False
    ahead = ct.get_tile(ct.get_position().add_dir(direction))
    return ahead is None or ahead.get_dragon() is None


def pocket_size(start: Position) -> int:
    """Free tiles reachable from start inside the window, capped at ESCAPE_CAP.

    A tile outside the window counts as escape: if the flood fill walks off the
    edge of vision the dragon is not trapped, so return the cap immediately.
    """
    seen = {(start.x, start.y)}
    queue = deque([start])
    count = 1
    while queue:
        pos = queue.popleft()
        tile = ct.get_tile(pos)
        if tile is None:
            return ESCAPE_CAP
        for direction in Direction.get_direction_list():
            edge = tile.get_edge(direction)
            if not edge.is_passable():
                continue
            if edge.is_portal():
                return ESCAPE_CAP          # a portal is always a way out
            nxt = pos.add_dir(direction)
            key = (nxt.x, nxt.y)
            if key in seen:
                continue
            ahead = ct.get_tile(nxt)
            if ahead is None:
                return ESCAPE_CAP
            if ahead.get_dragon() is not None:
                continue
            seen.add(key)
            count += 1
            if count >= ESCAPE_CAP:
                return ESCAPE_CAP
            queue.append(nxt)
    return count


def has_escape(direction: Direction) -> bool:
    need = min(ct.get_length() + 1, ESCAPE_CAP)
    return pocket_size(ct.get_position().add_dir(direction)) >= need


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
    if game.get_round_num() < SPLIT_CUTOFF and ct.can_split(2):
        ct.do_split(2)
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

    safe = [d for d in directions if is_safe(d)]
    for direction in safe:
        if has_escape(direction):
            ct.make_move(direction)
            return
    if safe:
        # every exit is a pocket: take the roomiest one rather than the first
        best = max(safe, key=lambda d: pocket_size(ct.get_position().add_dir(d)))
        ct.make_move(best)
        return

    best, best_score = Direction.NORTH, -99
    for direction in Direction.get_direction_list():
        here_tile = ct.get_tile(ct.get_position())
        if here_tile is None:
            continue
        if not here_tile.get_edge(direction).is_passable():
            score = -1
        else:
            ahead = ct.get_tile(ct.get_position().add_dir(direction))
            part = ahead.get_dragon() if ahead is not None else None
            if part is None:
                score = 2
            elif not part.is_head():
                score = -1
            elif part.get_team() != ct.get_team():
                score = 1
            else:
                score = -3
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
