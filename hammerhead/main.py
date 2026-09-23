"""hammerhead: tiger_shark plus the three changes that stop us killing ourselves.

Built from the decoded replays of the top eight ladder teams. The headline
finding is that our bots were never short of food -- per dragon-turn we ate as
much as the top 8 on five of eight maps -- we destroyed it. Net length kept per
1000 pearls eaten: ours 15-132, theirs 187-278. Self-inflicted deaths (hit wall
/ hit self, both meaning the dragon had no legal move left) were 58.8% of our
deaths against 11.8% for SSS, and that rate tracks ELO across the whole ladder.

Three changes, each measured in isolation against the bot it was built from:

  1. ESCAPE CHECK (16-2 alone -- the big one). Before committing to a step,
     flood-fill the free space reachable from the destination inside the 7x7
     window and reject any direction whose pocket is smaller than our length.
     Reaching the window edge or a portal counts as escape. This is what stops
     a dragon walking into a one-tile pocket and suffocating three turns later.

  2. BFS PATHING (17-7 alone). Replaces greedy axis-stepping toward the nearest
     pearl by wrapped Manhattan distance, which oscillates against kelp walls
     with food in plain sight -- on queen_of_spades a pearl was visible on 91%
     of our dragon-turns and we ate on 2.5% of them. BFS over the 49 visible
     tiles instead; first pearl popped is the target. Portals are never pathed
     through, because add_dir does not land where the portal goes.

  3. HOLD HEADING when no pearl is visible, instead of a random shuffle.
     ONLY ships bundled: on its own it is 8-16, a 2-to-1 losing change.

Split policy is unchanged from tiger_shark and matches the top teams: child
size 2 the moment length reaches 4 (65-100% of their splits are child 2, median
parent length after a split is 2), stopping at round 400. The long "king"
dragon needs no special rule -- once the team hits the 64 unit cap can_split
starts failing for everyone and the survivors simply grow.

Measured, 9 maps x both colours: 16-2 (89%) against tiger_shark, z=+3.30.
CPU is ~312k points per dragon-round against v_meta's ~331k, because BFS stops
at the first pearl instead of scanning all 49 tiles unconditionally.
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


def bfs_first_step() -> Direction | None:
    """First step of a shortest path through the window to the nearest pearl."""
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
            # kelp blocks; a portal does not land where add_dir says it does,
            # so never path through one.
            if not edge.is_passable() or edge.is_portal():
                continue
            nxt = pos.add_dir(direction)
            key = (nxt.x, nxt.y)
            if key in seen:
                continue
            ahead = ct.get_tile(nxt)
            if ahead is None:
                continue          # outside the window: stop expanding there
            if ahead.get_dragon() is not None:
                continue
            seen[key] = direction
            queue.append((nxt, direction if first is None else first))
    return None


def execute_turn() -> None:
    if game.get_round_num() < SPLIT_CUTOFF and ct.can_split(2):
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
    for direction in safe:
        if has_escape(direction):
            ct.make_move(direction)
            return
    if safe:
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
