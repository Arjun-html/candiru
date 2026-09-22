"""Drop-in debug dump for any bot: an ASCII picture of the 7x7 window plus every dragon part
(with ids) and the bot's own head trail, appended to a file next to this module.

Copy this file into the bot folder (bot.toml includes *.py) and call:

    import botdebug
    botdebug.dump(ct, game, "no legal step")            # anywhere a decision looks fatal
    botdebug.dump(ct, game, "doomed", trail=my_trail)   # trail: list of own head positions

Env vars do not reach bot processes, so gate calls with a constant in your bot, not os.environ.
The file lands in <bot>/.unswbc-build/bot_dump.txt (unswbc runs the built copy).

Legend:  H/# you (head/body)   F/f friend   E/e enemy   o pearl   . empty   ? outside window
         | kelp on a tile's east edge      - (line below) kelp on its south edge
"""
import os

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_dump.txt")


def dump(ct, game, why, trail=None):
    from helper import Direction, Position
    here = ct.get_position()
    me, team = ct.get_id(), ct.get_team()
    tiles = {}
    for t in ct.get_tiles():
        p = t.get_position()
        tiles[p.x, p.y] = t
    rows = []
    for dy in range(-3, 4):
        row, under = "", ""
        for dx in range(-3, 4):
            pos = Position((here.x + dx) % game.width, (here.y + dy) % game.height)
            t = tiles.get((pos.x, pos.y))
            if t is None:
                row += "? "
                under += "  "
                continue
            part = t.get_dragon()
            if part is None:
                c = "o" if t.has_pearl() else "."
            elif part.get_id() == me:
                c = "H" if part.is_head() else "#"
            elif part.get_team() == team:
                c = "F" if part.is_head() else "f"
            else:
                c = "E" if part.is_head() else "e"
            row += c + ("|" if not t.get_edge(Direction.EAST).is_passable() else " ")
            under += ("-" if not t.get_edge(Direction.SOUTH).is_passable() else " ") + " "
        rows.append(row)
        rows.append(under)
    parts = sorted((p.get_id(), p.get_position().x, p.get_position().y, p.is_head())
                   for t in tiles.values() if (p := t.get_dragon()) is not None)
    with open(_PATH, "a") as f:
        f.write(f"round {game.get_round_num()} id {me} len {ct.get_length()} "
                f"facing {ct.get_dir().value} at ({here.x},{here.y}): {why}\n")
        f.write("\n".join(rows) + "\n")
        f.write(f"parts (id,x,y,is_head): {parts}\n")
        if trail is not None:
            body = trail[-ct.get_length():]
            f.write(f"trail tail..head: {[(q.x, q.y) for q in body]}\n")
        f.write("\n")
