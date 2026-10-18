"""A simulated playthrough driven only by key presses and mouse movement.

The bot starts at the main menu, creates a character, then plays: it walks to a tree, chops it down with the wielded knife,
picks the branches up, looks for a stone hard enough to strike a spark (flint), makes a campfire from the recipe screen, places it
and lights it.
Every action goes through `main.process` as a real KeyDown / MouseMotion / TextInput event, and every frame through
`main.render`, exactly as the main loop does. The bot reads the game state only for what a player sees on screen (where
things are, what the lists say).
"""
import random
from collections import deque

import numpy as np
import pytest

import events
import main
import setup_game
from components.plant import Plant
import crafting
from crafting import Branch, Campfire
from items import Stuff
from materials import Family
from events import Key, KeyDown, Point, TextInput
from ui_helpers import SESSION

STEPS = {(0, -1): Key.UP, (0, 1): Key.DOWN, (-1, 0): Key.LEFT, (1, 0): Key.RIGHT,
         (-1, -1): Key.HOME, (-1, 1): Key.END, (1, -1): Key.PAGEUP, (1, 1): Key.PAGEDOWN}


class Bot:
    def __init__(self):
        self.handler = setup_game.MainMenu(SESSION)
        SESSION.handlers = [self.handler]
        self.events_sent = 0
        self.engine = None

    # ── input ──────────────────────────────────────────────────────────────────────
    def send(self, event) -> None:
        self.events_sent += 1
        self.handler = main.process(self.handler, event, SESSION)
        self.handler = main.render(self.handler, SESSION)

    def key(self, sym: int) -> None:
        self.send(KeyDown(sym, 0))

    def type(self, text: str) -> None:
        self.send(TextInput(text))

    def hover(self, x: int, y: int) -> None:
        """Move the mouse over map tile (x, y)."""
        sx, sy = self.engine.camera.to_screen(x, y)
        self.send(events.MouseMotion(Point(sx, sy)))

    def choose(self, label_part: str) -> None:
        """Press the letter shown beside the list entry whose text contains `label_part`."""
        lst = self.handler.list
        letter = next(k for k, i in lst.keys.items() if label_part in lst.rows[i].label.lower())
        self.key(ord(letter))

    # ── what a player sees ─────────────────────────────────────────────────────────
    @property
    def player(self):
        return self.engine.player

    @property
    def world(self):
        return self.engine.game_map

    def passable(self, x, y) -> bool:
        return self.world.in_bounds(x, y) and self.world.is_walkable(x, y) and not self.world.is_blocked(x, y)

    def path_to(self, goal, limit=60):
        p = self.player
        start = (p.x, p.y)
        previous, queue = {start: None}, deque([start])
        while queue:
            cell = queue.popleft()
            if goal(*cell):
                path = []
                while previous[cell] is not None:
                    path.append(cell)
                    cell = previous[cell]
                return path[::-1]
            for dx, dy in STEPS:
                nxt = (cell[0] + dx, cell[1] + dy)
                if nxt not in previous and abs(nxt[0] - start[0]) <= limit and abs(nxt[1] - start[1]) <= limit and self.passable(*nxt):
                    previous[nxt] = cell
                    queue.append(nxt)
        return None

    def walk_to(self, goal, limit=300) -> bool:
        """Press arrow keys, re-planning every step (animals get in the way and get hit instead)."""
        for _ in range(limit):
            p = self.player
            if goal(p.x, p.y):
                return True
            path = self.path_to(goal)
            if not path:
                return False
            self.key(STEPS[(path[0][0] - p.x, path[0][1] - p.y)])
        return False

    def branches(self):
        return [i for i in self.player.inventory.items if isinstance(i, Branch)]

    # ── the playthrough ────────────────────────────────────────────────────────────
    def start_game(self) -> None:
        self.key(Key.RETURN)           # New Game
        self.type("Q")                 # name
        for _ in range(6):             # name, people, background, sponsor, mode, start
            self.key(Key.RETURN)
        self.engine = self.handler.engine

    def fell_a_tree(self) -> None:
        """Walk to the nearest tree and bump into it (the wielded knife cuts it) until it falls."""
        trees = {(t.x, t.y): t for t in self.world.entities if isinstance(t, Plant) and t.blocks_movement and not t.dead}
        assert trees, "no trees in the loaded world"
        assert self.walk_to(lambda x, y: any(max(abs(x - tx), abs(y - ty)) <= 1 for tx, ty in trees)), "cannot reach a tree"
        p = self.player
        tree = min(trees.values(), key=lambda t: max(abs(t.x - p.x), abs(t.y - p.y)))
        for _ in range(80):
            if tree.dead:
                break
            self.key(STEPS[(tree.x - p.x, tree.y - p.y)])
        assert tree.dead, "the tree did not fall"
        self.tree = tree

    def pick_up_branches(self, want: int) -> None:
        """Stand where the branches fell and take them with G and the letter beside each."""
        spots = {(i.x, i.y) for i in self.world.entities if isinstance(i, Branch) and i.parent is self.world}
        assert spots, "no branches on the ground"
        for _ in range(12):
            if len(self.branches()) >= want:
                return
            here = [i for i in self.world.get_entities_at_location(self.player.x, self.player.y) if isinstance(i, Branch)]
            if not here:
                spots = {(i.x, i.y) for i in self.world.entities if isinstance(i, Branch) and i.parent is self.world}
                if not spots or not self.walk_to(lambda x, y: (x, y) in spots):
                    return
            self.hover(self.player.x, self.player.y)
            self.key(Key.G)             # "pick up" ...
            self.key(Key.G)             # ... what is under the cursor
            if type(self.handler).__name__ == "InventoryLootHandler":
                self.choose("branch")
                if type(self.handler).__name__ != "MainGameEventHandler":
                    self.key(Key.ESCAPE)    # close the loot window

    def has_spark(self) -> bool:
        return "firestarting" in crafting.unit_tags(self.player)

    def find_a_spark(self, tries: int = 40) -> None:
        """Pick up loose stones, nearest first, until one of them will strike a spark (flint lies about everywhere)."""
        tried = set()
        for _ in range(tries):
            if self.has_spark():
                return
            stones = {(i.x, i.y): i for i in self.world.entities
                      if isinstance(i, Stuff) and i.parent is self.world and i.substance.family is Family.STONE and (i.x, i.y) not in tried}
            if not stones or not self.walk_to(lambda x, y: (x, y) in stones, limit=400):
                return
            here = (self.player.x, self.player.y)
            tried.add(here)
            self.hover(*here)
            self.key(Key.G)
            self.key(Key.G)
            if type(self.handler).__name__ == "InventoryLootHandler":
                self.choose("")             # the first thing listed
                if type(self.handler).__name__ != "MainGameEventHandler":
                    self.key(Key.ESCAPE)

    def make_a_campfire(self) -> None:
        self.key(Key.R)
        assert type(self.handler).__name__ == "CraftingMenuHandler"
        self.choose("campfire")
        self.key(Key.RETURN)
        self.key(Key.ESCAPE)

    def place_it(self) -> None:
        self.key(Key.I)
        self.choose("campfire")
        assert type(self.handler).__name__ == "PlaceConstructableHandler"
        p = self.player
        free = next(d for d in STEPS if d in ((1, 0), (-1, 0), (0, 1), (0, -1)) and self.passable(p.x + d[0], p.y + d[1]))
        self.key(STEPS[free])           # move the cursor to a free neighbouring tile
        self.key(Key.RETURN)

    def light_it(self) -> None:
        self.key(Key.F)


@pytest.fixture(params=[7, 11, 23])
def bot(request):
    random.seed(request.param)
    np.random.seed(request.param)
    return Bot()


def test_player_builds_and_lights_a_campfire_with_key_presses_only(bot):
    bot.start_game()
    assert type(bot.handler).__name__ == "MainGameEventHandler"
    log = bot.engine.message_log

    for _ in range(3):                  # three branches for the campfire, one more to burn in it: a tree gives about three
        if len(bot.branches()) >= 4:
            break
        bot.fell_a_tree()
        bot.pick_up_branches(4)
    assert len(bot.branches()) >= 4

    bot.find_a_spark()
    assert bot.has_spark(), "no stone that strikes a spark was found"

    bot.make_a_campfire()
    assert any(isinstance(i, Campfire) for i in bot.player.inventory.items), "the campfire was not made"

    bot.place_it()
    assert type(bot.handler).__name__ == "MainGameEventHandler", "the placing cursor stays on screen after placing"
    fires = [t for t in bot.world.entities if isinstance(t, Campfire) and t.is_placed]
    assert len(fires) == 1 and not fires[0].is_lit

    bot.light_it()
    assert fires[0].is_lit and fires[0].emits_light, [m.plain_text for m in log.messages[-4:]]
    assert not any("went wrong" in m.plain_text for m in log.messages), "an error was caught during the playthrough"
    assert bot.events_sent > 20
