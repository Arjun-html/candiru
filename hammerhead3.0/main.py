"""hammerhead_tactical: same as hammerhead, but adds enemy-aware tactical scoring and
safer split gating drawn from replay weaknesses.

Changes from hammerhead:
  - keep the escape-check / BFS pearl logic
  - add direct enemy-head danger scoring to avoid suicides and bad trades
  - prefer not to split when a split would leave us with no room or with too many enemies nearby
  - keep heading only when no pearl is visible, but with tactical bias to avoid walls and heads
"""
import os
import random
from collections import deque

import helper as unswbc
from helper import Direction, Position

SPLIT_CUTOFF = 430
ESCAPE_CAP = 15
TACTICAL_HEAD_RANGE = 2
SAFE_EXIT_MIN = 2
SHORT_TRADE_LENGTH = 3
PORTAL_PENALTY = 7.0
FRIEND_CROWD_PENALTY = 3.5
ENEMY_BODY_CROWD_PENALTY = 1.0
OPENING_ROUNDS = 24
SMALL_MAP_AREA = 169
REVISIT_WINDOW = 8
REVISIT_PENALTY = 2.0

ct: unswbc.Controller
game: unswbc.Game
_trail: list[Position] = []

random.seed(os.environ.get("BOT_SEED"))


def is_safe(direction: Direction) -> bool:
    here_tile = ct.get_tile(ct.get_position())
    if not here_tile.get_edge(direction).is_passable():
        return False
    ahead = ct.get_tile(ct.get_position().add_dir(direction))
    return ahead is None or ahead.get_dragon() is None


def is_portal_step(direction: Direction) -> bool:
    return ct.get_tile(ct.get_position()).get_edge(direction).is_portal()


def pocket_size(start: Position) -> int:
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
            if not edge.is_passable() or edge.is_portal():
                continue
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


def bfs_first_step() -> Direction | None:
    start = ct.get_position()
    seen = {(start.x, start.y): None}
    queue = deque([(start, None)])
    while queue:
        pos, first = queue.popleft()
        tile = ct.get_tile(pos)
        if tile is None:
            continue
        if first is not None and tile.has_pearl():
            return first
        for direction in Direction.get_direction_list():
            edge = tile.get_edge(direction)
            if not edge.is_passable() or edge.is_portal():
                continue
            nxt = pos.add_dir(direction)
            key = (nxt.x, nxt.y)
            if key in seen:
                continue
            ahead = ct.get_tile(nxt)
            if ahead is None or ahead.get_dragon() is not None:
                continue
            seen[key] = direction
            queue.append((nxt, direction if first is None else first))
    return None


def visible_enemy_heads():
    heads = []
    for tile in ct.get_tiles():
        part = tile.get_dragon()
        if part is not None and part.is_head() and part.get_team() != ct.get_team():
            heads.append((part.get_position(), part.get_dir(), part.get_id()))
    return heads


def visible_segment_counts() -> dict[int, int]:
    counts = {}
    for tile in ct.get_tiles():
        part = tile.get_dragon()
        if part is None:
            continue
        counts[part.get_id()] = counts.get(part.get_id(), 0) + 1
    return counts


def observe_trail() -> None:
    here = ct.get_position()
    if not _trail or _trail[-1] != here:
        _trail.append(here)
    if len(_trail) > 4 * ct.get_length() + 8:
        del _trail[: len(_trail) // 2]


def mdist(a: Position, b: Position) -> int:
    dx = abs((a.x - b.x + game.width // 2) % game.width - game.width // 2)
    dy = abs((a.y - b.y + game.height // 2) % game.height - game.height // 2)
    return dx + dy


def enemy_pressure_score(direction: Direction, heads=None) -> float:
    pos = ct.get_position().add_dir(direction)
    if heads is None:
        heads = visible_enemy_heads()
    if not heads:
        return 0.0
    score = 0.0
    for enemy_pos, enemy_dir, _ in heads:
        dist = mdist(pos, enemy_pos)
        if dist <= 1:
            score -= 25.0
        elif dist == 2:
            score -= 8.0
        if dist == 1:
            score -= 5.0
        if dist <= TACTICAL_HEAD_RANGE and enemy_dir == direction:
            score -= 6.0
    return score


def crowding_score(position: Position) -> float:
    score = 0.0
    for tile in ct.get_tiles():
        part = tile.get_dragon()
        if part is None or part.get_id() == ct.get_id():
            continue
        dist = mdist(position, part.get_position())
        if dist == 0 or dist > 2:
            continue
        if part.get_team() == ct.get_team():
            score -= FRIEND_CROWD_PENALTY / dist
        elif not part.is_head():
            score -= ENEMY_BODY_CROWD_PENALTY / dist
    return score


def min_enemy_distance(position: Position, heads) -> int:
    if not heads:
        return 99
    return min(mdist(position, enemy_pos) for enemy_pos, _, _ in heads)


def revisit_penalty(position: Position) -> float:
    recent = _trail[-REVISIT_WINDOW:]
    if position not in recent:
        return 0.0
    return REVISIT_PENALTY * recent.count(position)


def small_map_opening() -> bool:
    return game.get_round_num() <= OPENING_ROUNDS and game.width * game.height <= SMALL_MAP_AREA


def legal_exit_count(position: Position) -> int:
    tile = ct.get_tile(position)
    if tile is None:
        return 4
    count = 0
    for direction in Direction.get_direction_list():
        edge = tile.get_edge(direction)
        if not edge.is_passable() or edge.is_portal():
            continue
        nxt = position.add_dir(direction)
        ahead = ct.get_tile(nxt)
        if ahead is None or ahead.get_dragon() is None:
            count += 1
    return count


def adjacent_enemy_trade() -> Direction | None:
    if ct.get_length() > SHORT_TRADE_LENGTH:
        return None
    counts = visible_segment_counts()
    here = ct.get_position()
    here_tile = ct.get_tile(here)
    for direction in Direction.get_direction_list():
        edge = here_tile.get_edge(direction)
        if not edge.is_passable() or edge.is_portal():
            continue
        ahead = ct.get_tile(here.add_dir(direction))
        part = ahead.get_dragon() if ahead is not None else None
        if part is None or not part.is_head() or part.get_team() == ct.get_team():
            continue
        if counts.get(part.get_id(), 0) > ct.get_length():
            return direction
    return None


def sprint_kill_path() -> list[Direction] | None:
    if ct.get_length() < 4 or ct.get_length() > 5:
        return None
    reach = ct.get_length() - 1
    counts = visible_segment_counts()
    start = ct.get_position()
    queue = deque([(start, [])])
    seen = {(start.x, start.y)}

    while queue:
        pos, path = queue.popleft()
        if len(path) >= reach:
            continue
        tile = ct.get_tile(pos)
        if tile is None:
            continue
        for direction in Direction.get_direction_list():
            edge = tile.get_edge(direction)
            if not edge.is_passable() or edge.is_portal():
                continue
            nxt = pos.add_dir(direction)
            ahead = ct.get_tile(nxt)
            if ahead is None:
                continue
            part = ahead.get_dragon()
            next_path = path + [direction]
            if part is not None:
                if part.get_team() != ct.get_team() and part.is_head():
                    if counts.get(part.get_id(), 0) >= max(3, ct.get_length() - 1):
                        return next_path
                continue
            key = (nxt.x, nxt.y)
            if key in seen:
                continue
            seen.add(key)
            queue.append((nxt, next_path))
    return None


def move_candidates(directions: list[Direction], heads) -> list[Direction]:
    safe = [direction for direction in directions if is_safe(direction)]
    if not safe:
        return []
    roomy = [
        direction for direction in safe
        if has_escape(direction)
        and legal_exit_count(ct.get_position().add_dir(direction)) >= SAFE_EXIT_MIN
    ]
    if roomy:
        return roomy
    escape = [direction for direction in safe if has_escape(direction)]
    if escape:
        return escape
    pressure_safe = [direction for direction in safe if enemy_pressure_score(direction, heads) >= -8.0]
    if pressure_safe:
        return pressure_safe
    return safe


def should_split() -> bool:
    if game.get_round_num() >= SPLIT_CUTOFF:
        return False
    if not ct.can_split(2):
        return False
    if ct.get_length() < 4:
        return False
    if small_map_opening():
        return False
    head_pos = ct.get_position()
    for tile in ct.get_tiles():
        part = tile.get_dragon()
        if part is not None and part.is_head() and part.get_team() != ct.get_team():
            if mdist(head_pos, part.get_position()) <= 3:
                return False
    return any(
        is_safe(direction)
        and not is_portal_step(direction)
        and has_escape(direction)
        and legal_exit_count(head_pos.add_dir(direction)) >= SAFE_EXIT_MIN
        for direction in Direction.get_direction_list()
    )


def execute_turn() -> None:
    observe_trail()
    sprint = sprint_kill_path()
    if sprint is not None:
        ct.make_moves(sprint)
        return

    trade = adjacent_enemy_trade()
    if trade is not None:
        ct.make_move(trade)
        return

    if should_split():
        ct.do_split(2)
        return

    step = bfs_first_step()
    facing = ct.get_dir()
    heads = visible_enemy_heads()
    sides = [facing.get_left(), facing.get_right()]
    if step is not None:
        random.shuffle(sides)
    directions = [facing] + sides + [facing.get_opposite()]
    if step is not None:
        directions = [step] + [direction for direction in directions if direction != step]

    safe = move_candidates(directions, heads)
    scored = []
    for direction in safe:
        destination = ct.get_position().add_dir(direction)
        exits = legal_exit_count(destination)
        enemy_gap = min_enemy_distance(destination, heads)
        room = has_escape(direction)
        score = 0.0
        if step is not None and direction == step:
            score += 12.0
        if room:
            score += 20.0
        else:
            score -= 10.0 * (1 / max(1, pocket_size(destination)))
        score += enemy_pressure_score(direction, heads)
        score += 2.5 * exits
        score += crowding_score(destination)
        if small_map_opening() and heads and enemy_gap <= 3:
            score += 2.0 * enemy_gap
            if exits < SAFE_EXIT_MIN:
                score -= 6.0
        if step is None and direction == facing:
            score += 1.5
        if step is None:
            score -= revisit_penalty(destination)
        if is_portal_step(direction):
            score -= PORTAL_PENALTY
        scored.append((direction, score))

    if scored:
        scored.sort(key=lambda item: item[1], reverse=True)
        chosen = scored[0][0]
        if scored[0][1] < -15 and len(scored) > 1 and scored[1][1] >= scored[0][1] + 5:
            chosen = scored[1][0]
        ct.make_move(chosen)
        return

    best, best_score = Direction.NORTH, -99
    heads = heads or visible_enemy_heads()
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
        score += enemy_pressure_score(direction, heads)
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
