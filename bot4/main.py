"""bot4: grower/splitter. Chases pearls like bot2, and splits off small children early
before banking length for the final-round tiebreak."""
import helper as unswbc
from helper import Direction, Position
import os
import random

ct: unswbc.Controller
game: unswbc.Game

random.seed(os.environ.get("BOT_SEED"))

SPLIT_CHILD_LENGTH = 2
LAST_SPLIT_ROUND = 430
MAX_SPLIT_UNITS = 40
SPLIT_INTERVAL = 3

def is_safe(direction: Direction) -> bool:
    here_tile = ct.get_tile(ct.get_position())
    if not here_tile.get_edge(direction).is_passable():
        return False
    ahead = ct.get_tile(ct.get_position().add_dir(direction))
    return ahead is None or ahead.get_dragon() is None

def fallback_rank(direction: Direction) -> int:
    """Prefer an enemy head-on trade over body or teammate-head collisions."""
    here_tile = ct.get_tile(ct.get_position())
    edge = here_tile.get_edge(direction)
    if not edge.is_passable():
        return 100

    dragon = ct.get_tile(ct.get_position().add_dir(direction)).get_dragon()
    if dragon is None:
        return 0
    if dragon.get_team() != ct.get_team() and dragon.is_head():
        return 1
    if dragon.is_head() and dragon.get_team() == ct.get_team():
        return 3
    return 2

def population_cap() -> int:
    width, height = game.get_map_size()
    return max(16, min(MAX_SPLIT_UNITS, width * height // 8))

def nearby_dragons(pos: Position, radius: int = 2) -> int:
    count = 0
    for tile in ct.get_tiles():
        if tile.get_dragon() is None:
            continue
        other = tile.get_position()
        width, height = game.get_map_size()
        dx = abs(wrapped_delta(pos.x, other.x, width))
        dy = abs(wrapped_delta(pos.y, other.y, height))
        if dx + dy <= radius:
            count += 1
    return count

def onward_exits(direction: Direction) -> int:
    destination = ct.get_position().add_dir(direction)
    tile = ct.get_tile(destination)
    if tile is None:
        return 4
    exits = 0
    for candidate in Direction.get_direction_list():
        if candidate == direction.get_opposite():
            continue
        if not tile.get_edge(candidate).is_passable():
            continue
        next_tile = ct.get_tile(destination.add_dir(candidate))
        if next_tile is None or next_tile.get_dragon() is None:
            exits += 1
    return exits

def intercept_enemy_head() -> bool:
    if ct.get_length() > 3:
        return False
    here = ct.get_position()
    for direction in Direction.get_direction_list():
        edge = ct.get_tile(here).get_edge(direction)
        if not edge.is_passable():
            continue
        dragon = ct.get_tile(here.add_dir(direction)).get_dragon()
        if (dragon is not None and dragon.is_head()
                and dragon.get_team() != ct.get_team()):
            ct.make_move(direction)
            return True
    return False

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
    if intercept_enemy_head():
        return

    # Small children preserve a long scoring dragon without saturating small maps.
    if (game.get_round_num() <= LAST_SPLIT_ROUND
            and (game.get_round_num() + ct.get_id()) % SPLIT_INTERVAL == 0
            and ct.get_unit_count() < population_cap()
            and ct.can_split(SPLIT_CHILD_LENGTH)):
        ct.do_split(SPLIT_CHILD_LENGTH)
        return

    target = nearest_pearl()
    directions = Direction.get_direction_list()
    preferred = []

    if target is not None:
        here = ct.get_position()
        width, height = game.get_map_size()
        dx = wrapped_delta(here.x, target.x, width)
        dy = wrapped_delta(here.y, target.y, height)
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

    safe = [direction for direction in directions if is_safe(direction)]
    if safe:
        late = game.get_round_num() > LAST_SPLIT_ROUND
        scored = []
        for direction in safe:
            pearl_bias = 2 if direction in directions[:len(preferred)] else 0
            exits = onward_exits(direction)
            crowd = nearby_dragons(ct.get_position().add_dir(direction))
            score = pearl_bias + exits * (4 if late else 1) - crowd * (3 if late else 0.5)
            scored.append((score, direction))
        ct.make_move(max(scored, key=lambda item: item[0])[1])
        return

    fallback = min(Direction.get_direction_list(), key=fallback_rank)
    if fallback_rank(fallback) < 100:
        ct.make_move(fallback)
    else:
        ct.make_move(Direction.NORTH)

def main() -> None:
    global ct, game
    ct, game = unswbc.init()

    while unswbc.update(ct, game):
        execute_turn()
        unswbc.end_turn()

if __name__ == "__main__":
    main()
