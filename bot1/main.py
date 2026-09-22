"""bot1: random walker. Steps onto any open, non-kelp, non-dragon neighbour tile."""
import helper as unswbc
from helper import Direction, EdgeType
import os
import random

ct: unswbc.Controller
game: unswbc.Game

random.seed(os.environ.get("BOT_SEED"))

def execute_turn() -> None:
    here_tile = ct.get_tile(ct.get_position())

    directions = Direction.get_direction_list()
    random.shuffle(directions)

    for direction in directions:
        edge = here_tile.get_edge(direction)
        if not edge.is_passable():
            continue

        ahead = ct.get_tile(ct.get_position().add_dir(direction))
        if ahead is not None and ahead.get_dragon() is not None:
            continue

        ct.make_move(direction)
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
