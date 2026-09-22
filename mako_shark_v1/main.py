"""mako_shark: a mothership that grows one long dragon and sheds a stream of suicide bombers.

Roles are decided on a dragon's first turn with no communication at all: the round-1 spawn
(length 3) is the MOTHERSHIP; a split child of BOMBER_SIZE is a BOMBER; a split child of
BACKUP_SIZE or more is a backup MOTHERSHIP running identical logic.

Mothership: the score. Chases pearls (including tiles about to spawn one), never crosses a
portal, never ends a move next to an enemy head, and won't enter a pocket smaller than itself -
checked against a remembered full-map picture of kelp and its own body, since a long coil's far
end is outside the 7x7 window. With two or more enemy heads in view it drops the pearl chase and
just gets out from between them. Sheds a bomber off its tail every few rounds while an enemy has
been seen recently (slowly otherwise), keeping a floor length that rises with the round; every
BACKUP_EVERY-th split, or whenever it's the team's last dragon, sheds a backup mothership
instead. Broadcasts its position by sonar.

Bomber: expendable. An enemy head within (length - 1) tiles along a clear path gets sprinted
into on the spot - moves resolve sequentially so the target cannot dodge, and it drops
ceil(L/2) pearls where it dies. It only pays for that trade against an enemy showing real length
or one close to the mothership. Otherwise it tries to step into the tile the enemy is about to
enter, then closes distance. With no enemy in sight it screens off the mothership's bow (out of
its lane) so approaching enemies meet a bomber first, and the loot lands near the mothership.
"""
import os
import random
from collections import deque

import helper as unswbc
from helper import Direction, Position

ct: unswbc.Controller
game: unswbc.Game

random.seed(os.environ.get("BOT_SEED"))
DEBUG = bool(os.environ.get("MAKO_DEBUG"))

MOTHER, BOMBER = "mother", "bomber"
ROLE = MOTHER

# --- splitting cadence (mothership)
BOMBER_SIZE = 3            # can sprint 2 tiles once: kill radius 2
BACKUP_SIZE = 6            # a child this big becomes a mothership too
KEEP_MIN = 5               # the mothership never sheds below this...
KEEP_PER_ROUND = 1 / 20    # ...and the floor rises: 10 at round 200, 20 at round 400
BACKUP_EVERY = 5           # every Nth split is a backup mothership
BACKUP_MARGIN = 4          # ...and only when that still leaves keep + BACKUP_MARGIN
THREAT_TTL = 40            # rounds after an enemy sighting during which we shed fast
SPLIT_COOLDOWN_THREAT = 3
SPLIT_COOLDOWN_CALM = 20   # with nobody around, just keep a thin escort topped up
LAST_SPLIT_ROUND = 430     # after this, every pearl goes to length
SPLIT_SAFE_RADIUS = 3      # no splitting with an enemy head this close (a split costs the turn)

# --- movement safety
ENEMY_DANGER = 2           # mothership never ends a move within this manhattan dist of an enemy head
ROOM_CAP = 30              # local room beyond this many tiles stops earning score
ROOM_MARGIN = 4            # a pocket must hold length + this many tiles before we enter it
CROWD_WEIGHT = 0.6         # per dragon segment (any team, own coil included) within 2 of a step
CROWD_RADIUS = 2
PEARL_WEIGHT = 3
PEARL_WEIGHT_PANIC = 0.5
PANIC_HEADS = 2            # this many enemy heads in view and we stop chasing pearls
STICKY_MARGIN = 2
FUTURE_PEARL_PENALTY = 2   # extra cost of steering at a tile that only *will* spawn a pearl

# --- bombers
MIN_TRADE_SEGMENTS = 3     # don't swap a 3-segment bomber for an enemy showing fewer than this...
DEFEND_RADIUS = 4          # ...unless that enemy is this close to the mothership
ESCORT_AHEAD = 2
ESCORT_WIDE = 2
LANE_LENGTH = 3            # bombers keep off the tiles straight ahead of the mothership
MOTHER_TTL = 12            # rounds a remembered mothership position stays trusted
SIGHTING_TTL = 6           # rounds a sonar enemy sighting stays worth chasing
MOTHER_MIN_SEGMENTS = 4    # friendly dragon with this many visible segments is a mothership

# --- sonar protocol: top byte tags our own messages so random enemy ints are ignored
KIND_MOTHER = 0xA1
KIND_ENEMY = 0xA2

DIRS = Direction.get_direction_list()


def encode(kind: int, pos: Position) -> int:
    return (kind << 24) | (pos.x << 12) | pos.y


def decode(msg: int) -> "tuple[int, Position] | None":
    kind = msg >> 24
    if kind not in (KIND_MOTHER, KIND_ENEMY):
        return None
    pos = Position((msg >> 12) & 0xFFF, msg & 0xFFF)
    return (kind, pos) if pos.is_in_map() else None


def wrapped_delta(a: int, b: int, size: int) -> int:
    diff = (b - a) % size
    return diff if diff <= size // 2 else diff - size


def mdist(a: Position, b: Position) -> int:
    return abs(wrapped_delta(a.x, b.x, game.width)) + abs(wrapped_delta(a.y, b.y, game.height))


# ----------------------------------------------------------------------------- board view

class View:
    """This turn's 7x7 window, indexed for the pathing below."""

    def __init__(self):
        self.tiles: dict[tuple[int, int], unswbc.Tile] = {}
        self.enemy_heads: list[unswbc.DragonPart] = []
        self.friend_heads: list[unswbc.DragonPart] = []
        self.friend_segments: dict[int, list[unswbc.DragonPart]] = {}
        self.enemy_segments: dict[int, int] = {}
        self.pearls: list[Position] = []
        self.future_pearls: list[tuple[Position, int]] = []
        me, my_team = ct.get_id(), ct.get_team()
        for tile in ct.get_tiles():
            pos = tile.get_position()
            self.tiles[pos.x, pos.y] = tile
            part = tile.get_dragon()
            if part is not None:
                if part.get_team() != my_team:
                    self.enemy_segments[part.get_id()] = self.enemy_segments.get(part.get_id(), 0) + 1
                    if part.is_head():
                        self.enemy_heads.append(part)
                elif part.get_id() != me:
                    self.friend_segments.setdefault(part.get_id(), []).append(part)
                    if part.is_head():
                        self.friend_heads.append(part)
            elif tile.has_pearl():
                self.pearls.append(pos)
            elif tile.get_pearl_time() >= 0:
                self.future_pearls.append((pos, tile.get_pearl_time()))

    def tile(self, pos: Position) -> "unswbc.Tile | None":
        return self.tiles.get((pos.x, pos.y))

    def crowd(self, pos: Position) -> int:
        """Dragon segments of any kind within CROWD_RADIUS of pos: the stuff that boxes us in."""
        n = 0
        for (x, y), tile in self.tiles.items():
            if tile.get_dragon() is not None and mdist(pos, tile.get_position()) <= CROWD_RADIUS:
                n += 1
        return n

    def enemy_segment_count(self, dragon_id: int) -> int:
        return self.enemy_segments.get(dragon_id, 0)

    def free(self, pos: Position) -> bool:
        tile = self.tile(pos)
        return tile is not None and tile.get_dragon() is None

    def bfs(self, start: Position, goal: "Position | None" = None):
        """Shortest paths over seen, empty, non-portal tiles. `goal` may be occupied (an
        enemy head) - it gets a distance but is never expanded through. Returns
        (dist, parent, leaks) where leaks is True if the region runs out of the window."""
        dist = {start: 0}
        parent: dict[Position, tuple[Position, Direction]] = {}
        leaks = False
        queue = deque([start])
        while queue:
            pos = queue.popleft()
            if pos == goal:
                continue
            tile = self.tile(pos)
            if tile is None:
                continue
            for d in DIRS:
                edge = tile.get_edge(d)
                if not edge.is_passable() or edge.is_portal():
                    continue
                nxt = pos.add_dir(d)
                if nxt in dist:
                    continue
                nt = self.tile(nxt)
                if nt is None:
                    leaks = True
                    continue
                if nt.get_dragon() is not None and nxt != goal:
                    continue
                dist[nxt] = dist[pos] + 1
                parent[nxt] = (pos, d)
                queue.append(nxt)
        return dist, parent, leaks

    def path_dirs(self, parent, goal: Position) -> list[Direction]:
        dirs = []
        pos = goal
        while pos in parent:
            pos, d = parent[pos]
            dirs.append(d)
        dirs.reverse()
        return dirs


# ----------------------------------------------------------------------------- candidates

class Step:
    __slots__ = ("d", "pos", "portal", "room", "leaks", "score")

    def __init__(self, d: Direction, pos: Position, portal: bool):
        self.d, self.pos, self.portal = d, pos, portal
        self.room, self.leaks, self.score = 0, False, 0.0


def legal_steps(view: View, here: Position, allow_heads: bool = False) -> list[Step]:
    """Every direction that doesn't kill us outright this turn. Portal crossings are kept but
    flagged - the far side is unknown, so they're a last resort."""
    here_tile = view.tile(here)
    steps = []
    for d in DIRS:
        edge = here_tile.get_edge(d)
        if not edge.is_passable():
            continue
        if edge.is_portal():
            steps.append(Step(d, here.add_dir(d), True))
            continue
        pos = here.add_dir(d)
        tile = view.tile(pos)
        part = tile.get_dragon() if tile is not None else None
        if part is not None and not (allow_heads and part.is_head() and part.get_team() != ct.get_team()):
            continue
        step = Step(d, pos, False)
        dist, _, step.leaks = view.bfs(pos)
        step.room = len(dist)
        steps.append(step)
    return steps


def roomy(step: Step, need: int) -> bool:
    return step.leaks or step.room >= need


def pick(steps: list[Step], *filters) -> "Step | None":
    """Apply filters as successive tiers: keep narrowing while something survives, then take
    the best-scored survivor. Guarantees a move whenever any legal one exists."""
    pool = steps
    for f in filters:
        kept = [s for s in pool if f(s)]
        if kept:
            pool = kept
    if not pool:
        return None
    best = max(s.score for s in pool)
    return random.choice([s for s in pool if s.score == best])


# ----------------------------------------------------------------------------- map memory

class Memory:
    """What this dragon has learned about the static map, plus where its own body lies.
    The 7x7 window can't see a long body's far end, so a coil that looks open locally may
    already be sealed - this lets the trap check look past the window."""

    def __init__(self):
        self.blocked: set[tuple[int, int, int]] = set()  # (x, y, dir index) edges we can't cross
        self.trail: list[Position] = []                   # every head position, oldest first

    def observe(self, view: View) -> None:
        here = ct.get_position()
        if not self.trail or self.trail[-1] != here:
            self.trail.append(here)
        if len(self.trail) > 4 * ct.get_length() + 8:
            del self.trail[: len(self.trail) // 2]
        for tile in view.tiles.values():
            pos = tile.get_position()
            for d in DIRS:
                edge = tile.get_edge(d)
                if not edge.is_passable() or edge.is_portal():
                    self.blocked.add((pos.x, pos.y, d._index))
                    far = pos.add_dir(d)
                    self.blocked.add((far.x, far.y, d.get_opposite()._index))

    def body(self) -> set[Position]:
        return set(self.trail[-ct.get_length():])

    def region_ok(self, start: Position, need: int, view: View) -> bool:
        """Can at least `need` tiles be reached from start? Seen tiles use live occupancy,
        unseen ones count as free unless our own body is remembered there."""
        body = self.body()
        seen = {start}
        queue = deque([start])
        count = 0
        while queue:
            pos = queue.popleft()
            count += 1
            if count >= need:
                return True
            for d in DIRS:
                if (pos.x, pos.y, d._index) in self.blocked:
                    continue
                nxt = pos.add_dir(d)
                if nxt in seen:
                    continue
                tile = view.tile(nxt)
                if tile is not None:
                    if tile.get_dragon() is not None:
                        continue
                elif nxt in body:
                    continue
                seen.add(nxt)
                queue.append(nxt)
        return False


memory = Memory()


# ----------------------------------------------------------------------------- shared memory

_mother_pos: "Position | None" = None
_mother_dir: "Direction | None" = None
_mother_round = -100
_sighting: "Position | None" = None
_sighting_round = -100     # last enemy head seen by us or reported over sonar


def read_sonar() -> None:
    global _mother_pos, _mother_round, _sighting, _sighting_round
    rnd = game.get_round_num()
    for msg in ct.get_sonar_messages():
        got = decode(msg)
        if got is None:
            continue
        kind, pos = got
        if kind == KIND_MOTHER:
            _mother_pos, _mother_round = pos, rnd
        else:
            _sighting, _sighting_round = pos, rnd


def note_enemies(view: View) -> None:
    global _sighting, _sighting_round
    if view.enemy_heads:
        here = ct.get_position()
        nearest = min(view.enemy_heads, key=lambda h: mdist(here, h.get_position()))
        _sighting, _sighting_round = nearest.get_position(), game.get_round_num()


def dump_view(view: View, here: Position, why: str) -> None:
    """Debug aid: append an ASCII picture of the window to $MAKO_DUMP."""
    rows = []
    for dy in range(-3, 4):
        row = ""
        for dx in range(-3, 4):
            pos = Position((here.x + dx) % game.width, (here.y + dy) % game.height)
            tile = view.tile(pos)
            if tile is None:
                row += "?"
                continue
            part = tile.get_dragon()
            if part is None:
                row += "o" if tile.has_pearl() else "."
            elif part.get_id() == ct.get_id():
                row += "H" if part.is_head() else "#"
            elif part.get_team() == ct.get_team():
                row += "F" if part.is_head() else "f"
            else:
                row += "E" if part.is_head() else "e"
            row += "|" if not tile.get_edge(Direction.EAST).is_passable() else " "
        rows.append(row)
        under = ""
        for dx in range(-3, 4):
            pos = Position((here.x + dx) % game.width, (here.y + dy) % game.height)
            tile = view.tile(pos)
            under += ("-" if tile is not None and not tile.get_edge(Direction.SOUTH).is_passable() else " ") + " "
        rows.append(under)
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mako_dump.txt"), "a") as f:
        f.write(f"round {game.get_round_num()} id {ct.get_id()} len {ct.get_length()} "
                f"facing {ct.get_dir().value} at {here}: {why}" + chr(10))
        parts = sorted((p.get_id(), p.get_position().x, p.get_position().y, p.is_head())
                       for t in view.tiles.values() if (p := t.get_dragon()) is not None)
        f.write(chr(10).join(rows) + chr(10) + f"parts: {parts}" + chr(10)
                + f"trail tail..head: {[(q.x, q.y) for q in memory.trail[-ct.get_length():]]}" + chr(10) + chr(10))


# ----------------------------------------------------------------------------- mothership

_target: "Position | None" = None
_last_split_round = -100
_splits_done = 0


def choose_target(view: View, here: Position, dist: dict) -> "Position | None":
    """Nearest reachable pearl, sticky against flip-flopping; if none, the tile whose next
    pearl we can be standing on soonest."""
    global _target
    if _target is not None:
        tile = view.tile(_target)
        if tile is None or not tile.has_pearl():
            _target = None

    best, best_cost = None, None
    for pos in view.pearls:
        if pos in dist:
            cost = dist[pos]
            if best_cost is None or cost < best_cost:
                best, best_cost = pos, cost
    if best is None:
        for pos, when in view.future_pearls:
            if pos in dist:
                cost = max(dist[pos], when) + FUTURE_PEARL_PENALTY
                if best_cost is None or cost < best_cost:
                    best, best_cost = pos, cost
        return best  # future targets aren't sticky - the countdown does that for us

    if _target is None or _target not in dist or best == _target:
        _target = best
    elif best_cost + STICKY_MARGIN < dist[_target]:
        _target = best
    return _target


def maybe_split(view: View, here: Position) -> bool:
    global _last_split_round, _splits_done
    rnd = game.get_round_num()
    length = ct.get_length()
    threatened = rnd - _sighting_round <= THREAT_TTL
    cooldown = SPLIT_COOLDOWN_THREAT if threatened else SPLIT_COOLDOWN_CALM
    if rnd > LAST_SPLIT_ROUND or rnd - _last_split_round < cooldown:
        return False
    if ct.get_unit_count() >= ct.unit_limit:
        return False
    if any(mdist(here, h.get_position()) <= SPLIT_SAFE_RADIUS for h in view.enemy_heads):
        return False

    keep = max(KEEP_MIN, int(rnd * KEEP_PER_ROUND))
    child = BOMBER_SIZE
    backup_due = (_splits_done + 1) % BACKUP_EVERY == 0 or ct.get_unit_count() <= 2
    if backup_due and length >= keep + BACKUP_SIZE + BACKUP_MARGIN:
        child = BACKUP_SIZE  # a lone mothership is one collision from elimination: insure it
    elif length < keep + BOMBER_SIZE:
        return False
    if not ct.can_split(child):
        return False
    ct.do_split(child)
    ct.send_sonar(encode(KIND_MOTHER, here))
    _last_split_round = rnd
    _splits_done += 1
    if DEBUG:
        ct.set_indicator_string(f"M split {child}")
    return True


def mother_turn(view: View) -> None:
    here = ct.get_position()
    length = ct.get_length()
    read_sonar()
    note_enemies(view)
    memory.observe(view)
    if maybe_split(view, here):
        return

    steps = legal_steps(view, here)
    dist, _, _ = view.bfs(here)
    target = choose_target(view, here, dist)
    enemies = [h.get_position() for h in view.enemy_heads]
    need = length + ROOM_MARGIN

    # with a crowd of heads in view, pearls stop mattering: get out of the middle of them
    panic = len(enemies) >= PANIC_HEADS
    pearl_weight = PEARL_WEIGHT_PANIC if panic else PEARL_WEIGHT

    for s in steps:
        score = 0.0
        if target is not None and not s.portal:
            d_here, _, _ = view.bfs(s.pos)
            score -= pearl_weight * d_here.get(target, 20)
        if enemies:
            dists = [mdist(s.pos, e) for e in enemies]
            score += 2 * min(dists) + 0.5 * sum(min(d, 5) for d in dists)
        score += 0.2 * min(s.room, ROOM_CAP)
        score -= CROWD_WEIGHT * view.crowd(s.pos)
        if s.d == ct.get_dir():
            score += 0.3  # keep covering new ground when nothing pulls us elsewhere
        s.score = score

    step = pick(
        steps,
        lambda s: not s.portal,
        lambda s: all(mdist(s.pos, e) > 1 for e in enemies),
        lambda s: all(mdist(s.pos, e) > ENEMY_DANGER for e in enemies),
        lambda s: not s.portal and memory.region_ok(s.pos, need, view),
        lambda s: all(mdist(s.pos, e) > ENEMY_DANGER + 1 for e in enemies),
    )
    if step is None:
        if DEBUG:
            dump_view(view, here, "no legal step")
        ct.make_move(ct.get_dir())
        return
    ct.make_move(step.d)
    ct.send_sonar(encode(KIND_MOTHER, step.pos))
    if DEBUG:
        ct.set_indicator_string(f"M {length} r{step.room}")


# ----------------------------------------------------------------------------- bomber

_lateral = 0  # -1 / 0 / +1: which flank of the mothership's bow this bomber screens


def spot_mother(view: View) -> None:
    """A friendly dragon big enough to be a mothership, seen directly, beats any sonar."""
    global _mother_pos, _mother_dir, _mother_round
    here = ct.get_position()
    best, best_d = None, None
    for parts in view.friend_segments.values():
        if len(parts) < MOTHER_MIN_SEGMENTS:
            continue
        head = next((p for p in parts if p.is_head()), None)
        part = head if head is not None else min(parts, key=lambda p: mdist(here, p.get_position()))
        d = mdist(here, part.get_position())
        if best_d is None or d < best_d:
            best, best_d = part, d
    if best is not None:
        _mother_pos, _mother_round = best.get_position(), game.get_round_num()
        _mother_dir = best.get_dir()  # body segments face toward the head - close enough


def enemy_exits(view: View, head: unswbc.DragonPart) -> list[Position]:
    """Tiles the enemy head can legally step to, its straight-ahead one first."""
    pos = head.get_position()
    tile = view.tile(pos)
    if tile is None:
        return []
    order = [head.get_dir()] + [d for d in DIRS if d != head.get_dir()]
    exits = []
    for d in order:
        edge = tile.get_edge(d)
        if edge.is_passable() and not edge.is_portal() and view.free(pos.add_dir(d)):
            exits.append(pos.add_dir(d))
    return exits


def worth_trading(view: View, head: unswbc.DragonPart, mother_known: bool) -> bool:
    """A head-on kill costs this whole bomber, so only pay for it against an enemy that shows
    real length (its drop refunds us) or one that is bearing down on the mothership."""
    if mother_known and mdist(head.get_position(), _mother_pos) <= DEFEND_RADIUS:
        return True
    return view.enemy_segment_count(head.get_id()) >= MIN_TRADE_SEGMENTS


def try_kill(view: View, here: Position, mother_known: bool) -> bool:
    """Sprint into any enemy head within reach along a clear path. The engine resolves our
    whole sprint before anyone else moves, so this cannot miss."""
    reach = ct.get_length() - 1
    best_path = None
    for head in view.enemy_heads:
        if not worth_trading(view, head, mother_known):
            continue
        goal = head.get_position()
        dist, parent, _ = view.bfs(here, goal)
        if goal in dist and 1 <= dist[goal] <= reach:
            path = view.path_dirs(parent, goal)
            if best_path is None or len(path) < len(best_path):
                best_path = path
    if best_path is None:
        return False
    if len(best_path) == 1:
        ct.make_move(best_path[0])
    else:
        ct.make_moves(best_path)
    if DEBUG:
        ct.set_indicator_string(f"B KILL {len(best_path)}")
    return True


def bomber_turn(view: View) -> None:
    here = ct.get_position()
    rnd = game.get_round_num()
    read_sonar()
    spot_mother(view)
    mother_known = _mother_pos is not None and rnd - _mother_round <= MOTHER_TTL

    if try_kill(view, here, mother_known):
        return

    steps = legal_steps(view, here)
    friend_heads = [h.get_position() for h in view.friend_heads]
    facing = _mother_dir if _mother_dir is not None else ct.get_dir()
    lane = set()
    if mother_known:
        pos = _mother_pos
        for _ in range(LANE_LENGTH):
            pos = pos.add_dir(facing)
            lane.add(pos)

    def mother_head_adjacent(s: Step) -> bool:
        return mother_known and mdist(s.pos, _mother_pos) <= 1

    worthy = [h for h in view.enemy_heads if worth_trading(view, h, mother_known)]
    if worthy:
        target = min(worthy, key=lambda h: mdist(here, h.get_position()))
        tpos = target.get_position()
        exits = enemy_exits(view, target)
        from_enemy, _, _ = view.bfs(tpos)
        for s in steps:
            s.score = -from_enemy.get(s.pos, 20)
            if exits and s.pos == exits[0]:
                s.score += 4  # straight ahead of it: the cut-off tile
            elif s.pos in exits:
                s.score += 2
            if len(exits) == 1 and s.pos == exits[0]:
                s.score += 4  # it has one way out and we're taking it
        ct.send_sonar(encode(KIND_ENEMY, tpos))
        label = "B hunt"
    elif _sighting is not None and rnd - _sighting_round <= SIGHTING_TTL:
        for s in steps:
            s.score = -mdist(s.pos, _sighting) + 0.2 * min(s.room, ROOM_CAP)
        label = "B chase"
    elif mother_known:
        # screen off the mothership's bow, each bomber on its own flank, out of its lane
        goal = _mother_pos
        for _ in range(ESCORT_AHEAD):
            goal = goal.add_dir(facing)
        side = facing.get_left() if _lateral <= 0 else facing.get_right()
        for _ in range(ESCORT_WIDE if _lateral != 0 else 1):
            goal = goal.add_dir(side)
        if _lateral == 0:
            goal = goal.add_dir(facing)  # the middle bomber sits further out, off to one side
        for s in steps:
            s.score = -mdist(s.pos, goal) + 0.2 * min(s.room, ROOM_CAP)
            tile = view.tile(s.pos)
            if tile is not None and tile.has_pearl():
                s.score += 1.5  # free lunge fuel on the way
        ct.send_sonar(encode(KIND_MOTHER, _mother_pos))
        label = "B escort"
    else:
        for s in steps:
            s.score = 0.2 * min(s.room, ROOM_CAP) + (0.5 if s.d == ct.get_dir() else 0)
            tile = view.tile(s.pos)
            if tile is not None and tile.has_pearl():
                s.score += 1.5
        label = "B roam"

    step = pick(
        steps,
        lambda s: not s.portal,
        lambda s: not mother_head_adjacent(s),
        lambda s: all(mdist(s.pos, f) > 1 for f in friend_heads),
        lambda s: roomy(s, ct.get_length()),
        lambda s: s.pos not in lane,
    )
    if step is None:
        # nowhere clean to go: take a head-on trade if one is offered, else die trying
        ram = legal_steps(view, here, allow_heads=True)
        ct.make_move(ram[0].d if ram else ct.get_dir())
        return
    ct.make_move(step.d)
    if DEBUG:
        ct.set_indicator_string(label)


# ----------------------------------------------------------------------------- main

def main() -> None:
    global ct, game, ROLE, _lateral
    ct, game = unswbc.init()
    first = True
    while unswbc.update(ct, game):
        if first:
            first = False
            if game.get_round_num() <= 1 or ct.get_length() >= BACKUP_SIZE:
                ROLE = MOTHER
            else:
                ROLE = BOMBER
                _lateral = ct.get_id() % 3 - 1
        view = View()
        if ROLE == MOTHER:
            mother_turn(view)
        else:
            bomber_turn(view)
        unswbc.end_turn()


if __name__ == "__main__":
    main()
