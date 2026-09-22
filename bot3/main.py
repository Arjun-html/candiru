"""bot3: right-hand wall follower. Classic maze rule: keep kelp on your right hand."""
import helper as unswbc
from helper import Direction

ct: unswbc.Controller
game: unswbc.Game

def is_safe(direction: Direction) -> bool:
    here_tile = ct.get_tile(ct.get_position())
    if not here_tile.get_edge(direction).is_passable():
        return False
    ahead = ct.get_tile(ct.get_position().add_dir(direction))
    return ahead is None or ahead.get_dragon() is None

def execute_turn() -> None:
    facing = ct.get_dir()
    # try right, then straight, then left, then back
    candidates = [facing.get_right(), facing, facing.get_left(), facing.get_opposite()]

    for direction in candidates:
        if is_safe(direction):
            ct.make_move(direction)
            return

    ct.make_move(facing)

def main() -> None:
    global ct, game
    ct, game = unswbc.init()

    while unswbc.update(ct, game):
        execute_turn()
        unswbc.end_turn()

if __name__ == "__main__":
    main()
