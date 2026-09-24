"""A dragon sealed in a pearl-less 3x3 pocket whose only exit is a portal.

kami gets out only when its random walk happens to step across the portal; port heads
for it once it has starved. Measures turns-to-escape for both.
Run: python test_portal_seek.py
"""
import importlib
import random
import statistics
import sys
import pathlib

ROOT = pathlib.Path(__file__).parent
POCKET = {(x, y) for x in range(2, 7) for y in range(2, 7)}
DEAD_CELL = (1, 4)                   # sealed 1-tile cell on the far side of the portal edge
PORTAL_EDGE = ((2, 4), "W")          # the one way out of the pocket


def load(bot: str):
    for name in ("helper", "main"):
        sys.modules.pop(name, None)
    sys.path.insert(0, str(ROOT / bot))
    helper = importlib.import_module("helper")
    main = importlib.import_module("main")
    sys.path.pop(0)
    return helper, main


def build(helper, head):
    """Vision tiles around head, as {(x, y): Tile}."""
    H = helper
    H.game = H.Game(9, 9, 64)

    def region(pos):
        return "pocket" if pos in POCKET else "cell" if pos == DEAD_CELL else "outside"

    def edge(pos, d):
        nxt = ((pos[0] + d._offset[0]) % 9, (pos[1] + d._offset[1]) % 9)
        if (pos, d.value) == PORTAL_EDGE or (nxt, d.get_opposite().value) == PORTAL_EDGE:
            # the tile add_dir() points at is a sealed 1-tile cell: to kami's escape check
            # the portal looks like a dead end, which is exactly why it refuses to take it.
            return H.Edge(d in (H.Direction.EAST, H.Direction.WEST), H.EdgeType.PORTAL, 0)
        kelp = region(pos) != region(nxt)
        return H.Edge(False, H.EdgeType.KELP if kelp else H.EdgeType.EMPTY)

    tiles = {}
    for x in range(head[0] - 3, head[0] + 4):
        for y in range(head[1] - 3, head[1] + 4):
            pos = (x % 9, y % 9)
            edges = tuple(edge(pos, d) for d in H.Direction.get_direction_list())
            tiles[pos] = H.Tile(H.Position(*pos), None, 0, False, edges)
    return tiles


class Stub:
    """The slice of Controller the bot actually calls."""

    def __init__(self, helper):
        self.H = helper
        self.head = (4, 4)
        self.facing = helper.Direction.NORTH
        self.tiles = build(helper, self.head)
        self.crossed = False

    # --- reads
    def get_position(self): return self.H.Position(*self.head)
    def get_tile(self, pos): return self.tiles.get((pos.x, pos.y))
    def get_tiles(self): return list(self.tiles.values())
    def get_length(self): return 3
    def get_id(self): return 7
    def get_dir(self): return self.facing
    def get_team(self): return self.H.Team.A
    def can_split(self, n): return False

    # --- writes
    def make_move(self, direction):
        if self.get_tile(self.get_position()).get_edge(direction).is_portal():
            self.crossed = True
            return
        self.head = ((self.head[0] + direction._offset[0]) % 9,
                     (self.head[1] + direction._offset[1]) % 9)
        self.facing = direction
        self.tiles = build(self.H, self.head)

    def make_moves(self, ds): self.make_move(ds[0])


def escape_turns(bot: str, seed: int, cap: int = 200) -> int:
    """Turns until the dragon crosses the portal, or cap if it never does."""
    helper, main = load(bot)
    main.random.seed(seed)
    main.starve = getattr(main, "starve", 0) * 0
    main.ct = ct = Stub(helper)
    main.game = helper.Game(9, 9, 64)
    main.game.round_num = 450          # past SPLIT_CUTOFF, so splitting stays out of it
    for turn in range(1, cap + 1):
        main.execute_turn()
        if ct.crossed:
            return turn
    return cap


if __name__ == "__main__":
    runs = {b: [escape_turns(b, s) for s in range(20)]
            for b in ("hammerhead_kami", "hammerhead_port")}
    for bot, ts in runs.items():
        print(f"{bot:18} median {statistics.median(ts):6.1f}  worst {max(ts):4d}")
    assert max(runs["hammerhead_port"]) <= 60, "port should time out on the sealed room and go"
    assert min(runs["hammerhead_kami"]) == 200, "kami is meant to refuse the dead-end portal"
    print("ok: port leaves, kami never does")
