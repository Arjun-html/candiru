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

SPLIT_CUTOFF = 400
ESCAPE_CAP = 12
TACTICAL_HEAD_RANGE = 2
SAFE_EXIT_MIN = 2

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
                return ESCAPE_CAP
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
            if ahead is None:
                continue
            if ahead.get_dragon() is not None:
                continue
            seen[key] = direction
            queue.append((nxt, direction if first is None else first))
    return None


def visible_enemy_heads():
    here = ct.get_position()
    heads = []
    for tile in ct.get_tiles():
        part = tile.get_dragon()
        if part is not None and part.is_head() and part.get_team() != ct.get_team():
            heads.append((part.get_position(), part.get_dir(), part.get_id()))
    return heads


def mdist(a: Position, b: Position) -> int:
    dx = abs((a.x - b.x + game.width // 2) % game.width - game.width // 2)
    dy = abs((a.y - b.y + game.height // 2) % game.height - game.height // 2)
    return dx + dy


def enemy_pressure_score(direction: Direction) -> float:
    pos = ct.get_position().add_dir(direction)
    heads = visible_enemy_heads()
    if not heads:
        return 0.0
    # Penalize stepping adjacent to or directly toward enemy heads.
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


def legal_exit_count(position: Position) -> int:
    tile = ct.get_tile(position)
    if tile is None:
        return 4
    count = 0
    for d in Direction.get_direction_list():
        edge = tile.get_edge(d)
        if not edge.is_passable() or edge.is_portal():
            continue
        nxt = position.add_dir(d)
        ahead = ct.get_tile(nxt)
        if ahead is None or ahead.get_dragon() is None:
            count += 1
    return count


def should_split() -> bool:
    if game.get_round_num() >= SPLIT_CUTOFF:
        return False
    if not ct.can_split(2):
        return False
    if ct.get_length() < 4:
        return False
    # Do not split if the current local view is crowded or if nearby enemy heads are close.
    head_pos = ct.get_position()
    nearby_enemy = False
    for tile in ct.get_tiles():
        part = tile.get_dragon()
        if part is not None and part.is_head() and part.get_team() != ct.get_team():
            if mdist(head_pos, part.get_position()) <= 3:
                nearby_enemy = True
                break
    if nearby_enemy:
        return False
    return True


def execute_turn() -> None:
    if should_split():
        ct.do_split(2)
        return

    step = bfs_first_step()
    facing = ct.get_dir()
    sides = [facing.get_left(), facing.get_right()]
    random.shuffle(sides)
    directions = [facing] + sides + [facing.get_opposite()]
    if step is not None:
        directions = [step] + [d for d in directions if d != step]

    safe = [d for d in directions if is_safe(d)]
    scored = []
    for direction in safe:
        score = 0.0
        if step is not None and direction == step:
            score += 12.0
        if has_escape(direction):
            score += 20.0
        else:
            score -= 10.0 * (1 / max(1, pocket_size(ct.get_position().add_dir(direction))))
        score += enemy_pressure_score(direction)
        # Prefer directions that keep room open and avoid getting boxed in.
        score += 2.0 * legal_exit_count(ct.get_position().add_dir(direction))
        scored.append((direction, score))

    if scored:
        scored.sort(key=lambda x: x[1], reverse=True)
        chosen = scored[0][0]
        # If the top move is still bad due to enemy pressure, prefer a safer local move.
        if scored[0][1] < -15 and len(scored) > 1 and scored[1][1] >= scored[0][1] + 5:
            chosen = scored[1][0]
        ct.make_move(chosen)
        return

    # Fallback: choose the least bad option across all directions.
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
        score += enemy_pressure_score(direction)
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
