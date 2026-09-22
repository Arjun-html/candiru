"""reef_shark: pearl chaser with a per-dragon coin-flip personality.

Personality is decided once per dragon, from its id parity (odd = aggressive, even =
conservative) — stable for that dragon's whole life, and naturally ~50/50 across splits since
every split spawns a fresh process with its own id.

Aggressive dragons: always move to trade a head-on kill with a visible enemy head, split early
and often, drift toward the map's center, skip the dead-end lookahead (risk-tolerant).

Conservative dragons: never seek a fight, drift away from whatever dragon (friend or foe) is
closest in vision, split later and less, keep the dead-end lookahead once long, avoid portals
once long enough that a blind teleport could strand them somewhere too small.
"""
import helper as unswbc
from helper import Direction, Position

ct: unswbc.Controller
game: unswbc.Game

AGGRESSIVE = False  # set once per dragon in main(), from ct.get_id() parity

LONG_THRESHOLD = 6
PORTAL_AVOID_LENGTH = 4
STICKY_MARGIN = 2  # only abandon the current pearl target for one this much closer

SPLIT_LENGTH = 8
SPLIT_KEEP = 5
AGGRESSIVE_SPLIT_LENGTH = 5
AGGRESSIVE_SPLIT_KEEP = 3

PEARL_WEIGHT = 3
POSITION_WEIGHT = 1

_target_pearl: Position | None = None

def wrapped_delta(a: int, b: int, size: int) -> int:
    diff = (b - a) % size
    return diff if diff <= size // 2 else diff - size

def wrapped_dist(a: Position, b: Position) -> int:
    width, height = game.get_map_size()
    return abs(wrapped_delta(a.x, b.x, width)) + abs(wrapped_delta(a.y, b.y, height))

def nearest_pearl() -> Position | None:
    best, best_dist = None, None
    here = ct.get_position()
    for tile in ct.get_tiles():
        if not tile.has_pearl():
            continue
        pos = tile.get_position()
        dist = wrapped_dist(here, pos)
        if best_dist is None or dist < best_dist:
            best, best_dist = pos, dist
    return best

def target_pearl() -> Position | None:
    """The pearl we're committed to. Sticks with it turn to turn instead of retargeting to
    whatever's nearest each turn (which causes flip-flopping between two similar-distance
    pearls and lets a steadier competitor beat us to both)."""
    global _target_pearl
    here = ct.get_position()

    if _target_pearl is not None:
        tile = ct.get_tile(_target_pearl)
        if tile is not None and not tile.has_pearl():
            _target_pearl = None  # eaten by someone, or was never real — drop it

    candidate = nearest_pearl()
    if candidate is None:
        return _target_pearl
    if _target_pearl is None or candidate == _target_pearl:
        _target_pearl = candidate
        return _target_pearl

    if wrapped_dist(here, candidate) + STICKY_MARGIN < wrapped_dist(here, _target_pearl):
        _target_pearl = candidate
    return _target_pearl

def nearest_enemy_head() -> "unswbc.DragonPart | None":
    my_team = ct.get_team()
    here = ct.get_position()
    best, best_dist = None, None
    for tile in ct.get_tiles():
        part = tile.get_dragon()
        if part is None or not part.is_head() or part.get_team() == my_team:
            continue
        dist = wrapped_dist(here, part.get_position())
        if best_dist is None or dist < best_dist:
            best, best_dist = part, dist
    return best

def nearest_other_dragon_pos() -> Position | None:
    my_id = ct.get_id()
    here = ct.get_position()
    best, best_dist = None, None
    for tile in ct.get_tiles():
        part = tile.get_dragon()
        if part is None or part.get_id() == my_id:
            continue
        dist = wrapped_dist(here, part.get_position())
        if best_dist is None or dist < best_dist:
            best, best_dist = part.get_position(), dist
    return best

def safe_exit_count(pos: Position) -> int:
    """How many directions out of pos are passable and dragon-free. Unseen tiles count as wide open."""
    tile = ct.get_tile(pos)
    if tile is None:
        return 99
    count = 0
    for d in Direction.get_direction_list():
        edge = tile.get_edge(d)
        if not edge.is_passable():
            continue
        ahead = ct.get_tile(pos.add_dir(d))
        if ahead is not None and ahead.get_dragon() is not None:
            continue
        count += 1
    return count

def is_immediately_safe(direction: Direction, here_tile: "unswbc.Tile") -> bool:
    if not here_tile.get_edge(direction).is_passable():
        return False
    ahead = ct.get_tile(ct.get_position().add_dir(direction))
    return ahead is None or ahead.get_dragon() is None

def hunt_direction(here: Position, here_tile: "unswbc.Tile", enemy_pos: Position) -> Direction | None:
    """Closes distance on a visible enemy head, walking straight into it to trade kills once
    adjacent. Won't blunder through some other dragon's body along the way to get there."""
    best, best_dist = None, None
    for d in Direction.get_direction_list():
        edge = here_tile.get_edge(d)
        if not edge.is_passable():
            continue
        dest = here.add_dir(d)
        if dest != enemy_pos:
            ahead = ct.get_tile(dest)
            if ahead is not None and ahead.get_dragon() is not None:
                continue
        dist = wrapped_dist(dest, enemy_pos)
        if best_dist is None or dist < best_dist:
            best, best_dist = d, dist
    return best

def choose_move() -> Direction:
    here = ct.get_position()
    here_tile = ct.get_tile(here)
    length = ct.get_length()

    if AGGRESSIVE:
        enemy = nearest_enemy_head()
        if enemy is not None:
            hunt = hunt_direction(here, here_tile, enemy.get_position())
            if hunt is not None:
                return hunt

    avoid_portals = length >= PORTAL_AVOID_LENGTH
    careful = (not AGGRESSIVE) and length >= LONG_THRESHOLD

    candidates = [d for d in Direction.get_direction_list() if is_immediately_safe(d, here_tile)]

    non_portal = [d for d in candidates if not here_tile.get_edge(d).is_portal()]
    if avoid_portals and non_portal:
        candidates = non_portal

    if careful:
        # prefer moves that don't land in a dead end (only the way back)
        roomy = [d for d in candidates if safe_exit_count(here.add_dir(d)) >= 2]
        if roomy:
            candidates = roomy

    if not candidates:
        return Direction.NORTH

    target = target_pearl()
    width, height = game.get_map_size()
    threat_pos = None if AGGRESSIVE else nearest_other_dragon_pos()
    anchor = Position(width // 2, height // 2) if AGGRESSIVE else None

    def score(d: Direction) -> float:
        new_pos = here.add_dir(d)
        s = 0.0
        if target is not None:
            s -= PEARL_WEIGHT * wrapped_dist(new_pos, target)
        if AGGRESSIVE:
            s -= POSITION_WEIGHT * wrapped_dist(new_pos, anchor)
        elif threat_pos is not None:
            s += POSITION_WEIGHT * wrapped_dist(new_pos, threat_pos)
        return s

    return max(candidates, key=score)

def execute_turn() -> None:
    length = ct.get_length()
    split_length = AGGRESSIVE_SPLIT_LENGTH if AGGRESSIVE else SPLIT_LENGTH
    split_keep = AGGRESSIVE_SPLIT_KEEP if AGGRESSIVE else SPLIT_KEEP

    if length >= split_length:
        child_size = length - split_keep
        if ct.can_split(child_size):
            ct.do_split(child_size)
            return

    ct.make_move(choose_move())

def main() -> None:
    global ct, game, AGGRESSIVE
    ct, game = unswbc.init()
    AGGRESSIVE = ct.get_id() % 2 == 1

    while unswbc.update(ct, game):
        execute_turn()
        unswbc.end_turn()

if __name__ == "__main__":
    main()
