"""hammerhead_port: hammerhead_kami plus one thing -- use portals when starving.

THE CHANGE. kami never crosses a portal on purpose: bfs_first_step refuses to path
through one, and is_safe/has_escape judge a portal step by the tile add_dir() points at,
which is NOT where the portal lands you -- so a portal step was accepted or rejected on
a tile we never visit. On a map where our spawn pocket only opens through a portal that
means we circle at home for 500 rounds and score whatever length we started with.

Now: a portal edge is safe by definition (it is an exit; pocket_size already treats it as
one), and when a portal is the ONLY way out of the space we are standing in and there is
no pearl left to reach in it, we BFS to that portal and cross it. PORTAL_COOLDOWN turns of
not looking for another one stops the dragon bouncing back through the same pair.

The first version triggered on hunger instead -- 6 turns with no reachable pearl -- which
fires all the time in open play. The whole swarm converged on the nearest portal mouth and
rammed each other there: 22 extra friendly head-to-heads on `default`, 4 dragons left
against kami's 32, and 0-6 on that map. Overall it was 25-29 against kami over 54 games.
Entrapment is the real condition, and it has two halves: a pocket small enough to
flood-fill inside the window (boxed_in), and a sealed room bigger than the window, which
one 7x7 snapshot cannot distinguish from open map at all -- only a long run of turns with
nothing reachable is evidence of that (starved_out), offset per dragon id so the swarm
does not arrive at one portal mouth together.

Everything below is kami unchanged.

ORIGINAL kami NOTES
-------------------
hammerhead_kami: hammerhead plus one thing -- take the favourable head-to-head.

A polish of the same engine, not a new one. This file IS hammerhead with a single function
added, and that function is the whole difference.

THE CHANGE. A head-to-head kills BOTH dragons, so it is a straight swap of whatever length
each side is carrying. We field more and shorter dragons than our opponents -- 26 to their 16
across tiger_shark's 74 ladder games, ours length 2-4 against their 6 -- which makes the trade
good for us nearly every time. We were already taking it constantly BY ACCIDENT: head-to-head
is 43% of our opponents' deaths and only 11.3% of ours. This just makes it deliberate, gated
on their visible length clearing ours (a lower bound -- we only trade when we can SEE they are
bigger).

MEASURED: 62-28 (68.9%) against hammerhead, z = +3.58, over 90 games (9 maps x both colours x
5 seeds). No map where it loses; worst case is a coin flip. Strongly map-dependent, which the
economics predict -- a length-30 corpse is 9.5 rounds of Default's whole output but only 1.4
of Big Empty's:

    arena 90% | Colosseum 80% | default 80% | trophy 80% | schooltime 70%
    help 60% | queen_of_spades 60% | big_empty 50% | default_small 50%

WHAT WAS TRIED AND REJECTED (all at 90 games vs this bot):

1. Pricing every decision off one measured quantity instead of three tuned constants --
   worth = rho * R, this dragon's realised pearls per turn times rounds remaining. Split while
   a child returns more than the 2 segments it costs; the cutoff then falls out on its own as
   R shrinks, and it is self-correcting where a fixed round cannot be (population collapses ->
   self-competition falls -> rho rises -> splitting resumes).
   LOST 36-54 (40%). It won the sparse maps and lost the cramped ones, because the fixed
   cutoff turns out to be doing a second job nobody designed: thinning the swarm late so it
   does not collide with itself on a small board. It also needed two rescue patches to be
   playable at all -- on Default it measured rho near zero, never split, and was eliminated at
   round 376 holding one dragon while hammerhead held 62.

2. Moving the cutoff 400 -> 460 and holding long dragons back from splitting after round 350,
   to fix the real collapse (on the ladder hammerhead goes from 63 dragons and 251 total
   length at round 400 to 13 and 117 by 499, while the opponent's total RISES).
   WASH: 48-42 (53.3%), z = +0.63.

3. The same, with the cutoff gated on tiles per team -- 460 on open boards, 400 on cramped --
   since space per team predicts elimination rate at r = -0.976 and explains the map split in
   every other measurement here.
   WASH: 47-43 (52.2%), z = +0.42.

The per-map differences that motivated (3) were NOISE. Comparing runs (2) and (3), the six
maps the gate never touched swung by an average of 18pp between runs -- larger than the swings
attributed to the change itself. A 10-game cell has SE 15.8pp, so its 95% band is +/-31pp.
Per-map tuning is not possible at that sample size; only the 90-game aggregate means anything.

The population collapse in (2) is still a real, measured defect. It is not fixed here, and
nothing tried so far fixes it without costing more elsewhere.
"""
import helper as unswbc
from helper import Direction, Position
import os
import random
from collections import deque

SPLIT_CUTOFF = 400
ESCAPE_CAP = 12          # stop the flood fill once the pocket is clearly big enough
PORTAL_COOLDOWN = 25     # turns after crossing before we go looking for another portal
STARVE_BASE = 30         # turns with nothing reachable before we call the room a dead end
STARVE_JITTER = 16       # spread per dragon, so the swarm does not arrive at one mouth

portal_wait = 0
starve = 0

ct: unswbc.Controller
game: unswbc.Game

random.seed(os.environ.get("BOT_SEED"))


def is_safe(direction: Direction) -> bool:
    here_tile = ct.get_tile(ct.get_position())
    edge = here_tile.get_edge(direction)
    if not edge.is_passable():
        return False
    if edge.is_portal():
        return True          # lands out of vision; add_dir() is the wrong tile to check
    ahead = ct.get_tile(ct.get_position().add_dir(direction))
    return ahead is None or ahead.get_dragon() is None


def pocket_size(start: Position, portals_escape: bool = True) -> int:
    """Free tiles reachable from start inside the window, capped at ESCAPE_CAP.

    A tile outside the window counts as escape: if the flood fill walks off the
    edge of vision the dragon is not trapped, so return the cap immediately.

    With portals_escape off, a portal is a wall rather than a way out -- that is
    the measurement of whether a portal is the ONLY way out.
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
                if portals_escape:
                    return ESCAPE_CAP      # a portal is always a way out
                continue                   # ...but we are asking if it is the only one
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


def boxed_in() -> bool:
    """Whether a portal is the only way out of the space we are standing in.

    v1 hunted portals on hunger -- after 6 turns with no reachable pearl -- which fires
    constantly in normal play, every time a dragon clears the pearls around it. The whole
    swarm then BFS'd to the same nearest portal and piled onto its mouth: on `default` that
    cost 22 extra friendly head-to-heads and collapsed us to 4 dragons against kami's 32,
    losing all 6 games. Entrapment is the condition we actually meant.
    """
    return pocket_size(ct.get_position(), portals_escape=False) < min(ct.get_length() + 1,
                                                                     ESCAPE_CAP)


def starved_out() -> bool:
    """Whether we have gone long enough with nothing to reach that the room is a dead end.

    boxed_in() only catches a pocket small enough to flood-fill inside one 7x7 window. A
    sealed ROOM bigger than the window is indistinguishable from open map in a single
    snapshot, and that is exactly the case that loses games on the ladder -- a spawn area
    walled off except through a portal. Time is the only evidence we have for it.

    The threshold is offset by dragon id so that a swarm that starves together does not
    converge on the same portal mouth on the same turn, which is what v1 did.
    """
    return starve >= STARVE_BASE + ct.get_id() % STARVE_JITTER


def has_escape(direction: Direction) -> bool:
    if ct.get_tile(ct.get_position()).get_edge(direction).is_portal():
        return True
    need = min(ct.get_length() + 1, ESCAPE_CAP)
    return pocket_size(ct.get_position().add_dir(direction)) >= need


def bfs_first_step(seek_portal: bool = False) -> Direction | None:
    """First step of a shortest path through the window to the nearest pearl.

    With seek_portal, the target is the nearest portal edge instead: a way out of a
    pocket the pearls have run out in. We still never path THROUGH a portal, because
    we cannot see where it lands -- crossing one is always the last step.
    """
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
            # so never path through one -- only finish on one.
            if not edge.is_passable():
                continue
            if edge.is_portal():
                if seek_portal:
                    return direction if first is None else first
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


def enemy_head_trade() -> Direction | None:
    """A step into an adjacent enemy head, when the trade is in our favour.

    A head-to-head kills BOTH dragons, so it is a straight swap of whatever
    length each side is carrying. We field more and shorter dragons than our
    opponents -- 26 to their 16 on the ladder, ours length 2-4 against their
    6 -- so trading our length-2 for their length-6 is a good deal every time.
    We were previously only taking it by accident: head-to-head is 43% of our
    opponents' deaths and 11.3% of ours.

    Their length is counted from segments visible in our 7x7, so it is a lower
    bound -- we take the trade only when we can SEE they are bigger.
    """
    here = ct.get_position()
    tile = ct.get_tile(here)
    if tile is None:
        return None
    mine = ct.get_length()
    my_team = ct.get_team()

    seen_len = {}
    for vis in ct.get_tiles():
        part = vis.get_dragon()
        if part is not None and part.get_team() != my_team:
            seen_len[part.get_id()] = seen_len.get(part.get_id(), 0) + 1

    best, best_len = None, None
    for direction in Direction.get_direction_list():
        if not tile.get_edge(direction).is_passable():
            continue
        ahead = ct.get_tile(here.add_dir(direction))
        if ahead is None:
            continue
        part = ahead.get_dragon()
        if part is None or not part.is_head() or part.get_team() == my_team:
            continue
        theirs = seen_len.get(part.get_id(), 1)
        if theirs <= mine:
            continue                      # not worth our dragon
        if best_len is None or theirs > best_len:
            best, best_len = direction, theirs
    return best


def execute_turn() -> None:
    # Aggression first: a favourable head-to-head is worth more than a pearl.
    ram = enemy_head_trade()
    if ram is not None:
        ct.make_move(ram)
        return

    if game.get_round_num() < SPLIT_CUTOFF and ct.can_split(2):
        ct.do_split(2)
        return

    step = bfs_first_step()
    global portal_wait, starve
    portal_wait = max(0, portal_wait - 1)
    starve = 0 if step is not None else starve + 1
    if step is None and portal_wait == 0 and (boxed_in() or starved_out()):
        hop = bfs_first_step(seek_portal=True)
        if hop is not None:
            step = hop
            if ct.get_tile(ct.get_position()).get_edge(hop).is_portal():
                portal_wait, starve = PORTAL_COOLDOWN, 0

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
