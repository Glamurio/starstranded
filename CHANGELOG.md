# Changelog

Behavior changes made by the modernization project (branch `modernize`). Pure refactors are not listed.

## Creature behaviour: hunger-driven hunting
- Every creature now runs the same routine: flee from what hunts it, (hostile ones) chase the player, otherwise when hungry or
  thirsty eat what it carries, else find food, walk to it, eat it or attack it.
- **Diets:** rabbits are herbivores (fruit), Selenites carnivores (meat), the player an omnivore. Meat eaters hunt living herbivores
  (so rabbits now flee from the player at 4 tiles, and Selenites hunt rabbits); rabbits do not eat meat, Selenites do not eat
  fruit. Meat now also quenches 15 thirst (there is no water to drink yet).
- Hungry animals walk to food that is not right next to them (they used to wander aimlessly) and no longer re-pick their wander
  target every turn.
- Creatures in the nearby (not fully simulated) chunks follow the same rules with simpler movement, so hunts and meals happen off
  screen too. Fights and deaths the player cannot see are not logged; creatures killing each other no longer print "You gain
  experience".
- Selenites now spawn (about 8 % of the creatures).

## Combat: damage types, destructible plants
- Attacks have a damage type (blunt, sharp, pierce; elemental types can be added in `damage.py`). Fists/natural attacks are
  blunt (Selenites claw: sharp), the dagger and the new axe are sharp, the spear pierces. Targets scale damage per type
  (`resistances`); trees barely notice blunt/pierce hits.
- Bump into a tree or shrub while wielding a weapon to cut it down (trees: 30 HP, an axe needs ~5 hits, the starting dagger ~8).
  A felled plant opens its tile and drops its fruit plus two branches. Bare hands still just bump.
- New craftable **Axe** (3 branches; placeholder recipe until stone/metal exist).
- Any unit can die at 0 HP now (before, only units with an AI could).

## `g.py` removed
- The module of UI globals is replaced by an explicit `Session` object (`session.py`) reachable as `engine.session`; layout
  constants moved to `layout.py`. `main.run(handler, session)`, `setup_game.MainMenu(session)`, `new_game(player, session)`
  and `load_game(path, session)` take it. Not user-visible.

## Demo leftovers removed
- Health potion, sword, chain mail and the confusion/fireball/lightning scrolls are gone (items, species entries, the
  confusion AI, the tutorial-era `entity_factories.py`). Worlds no longer scatter any ground items; the Selenite, dagger,
  leather armor, wooden spear, meat, fruit, branch and campfire stay. The targeting handlers (`SingleRangedAttackHandler`,
  `AreaRangedAttackHandler`) stay as generic UI for future ranged items.

## Performance pass 1
- Animals walk to their chosen wander spot instead of picking a new one every turn (hungry rabbits used to jitter).
- Plants grow and drop fruit in every loaded chunk (not just the nearby ones), and at the same pace as before; trees no longer
  all fruit on the same turn (staggered start). A full plant whose neighbours are all blocked no longer loses its harvest.
- Chunk files are zlib-compressed; the save format is version 5, so earlier saves do not load (fresh start, as agreed).
- Startup: `main.py` works from any directory and says to install pygame-ce when `pygame` is missing.

## Phase 5 — chunked world
- **The world is endless:** each floor is made of 70x40 chunks generated as you walk; the view follows the player and
  scrolls across chunk borders seamlessly. The side panel shows your position.
- **Creatures off-screen keep living:** the chunk you are in is fully simulated, the 8 around it move every other turn with
  simpler behaviour (they still wander, flee and approach), far chunks are stored and caught up when you return (hunger, thirst,
  plant growth; animals with food nearby are assumed to have foraged).
- **Each floor has a down staircase** a short walk from the start (press `L` on it); it used to be missing. Going down creates a
  new world; there is no way back up.
- Vision radius is 41 tiles (the screen around you) instead of the whole map.
- Wandering and fleeing animals pick destinations near themselves (before: anywhere on the map). Pathfinding searches at most
  40 tiles around the walker.
- **Saves are a folder** (`savegame/` next to the game files) with one file per visited chunk; saving is atomic. Saves from
  earlier versions no longer load. Only visited chunks are stored.
- Plants dropping fruit no longer print "You dropped ..." messages; deaths in chunks far away are silent.

## Phase 4 — sprite layering
- **Everything on a tile is drawn in a fixed stack:** corpses, then items, then shrubs, then creatures, then trees, each with its own colour and facing.
  You can now see the corpse and item you are standing on, or that an animal stands on.
- **Piles are capped:** with more than two corpses/items on one tile only the top two are drawn and a small "+" shows there are more
  (`GameConfig.clutter_safeguard`, on by default; creatures are never hidden).
- Looking at a tile (names under the cursor) and the pick-up list now show the stack **topmost first**; long lists are cut with "...".

## Phase 3 — pygame-ce rendering and input
- **The game window is now drawn with pygame-ce** (tcod is only used for FOV, pathfinding, noise and line drawing). Install
  `pygame-ce` (`pip install -r requirements.txt`). The sprite sheet and font are unchanged.
- **Resizable window with a fixed 1920x1080 logical screen:** scaled by whole-number factors when it fits, smoothly when the window
  is smaller, with black bars; mouse clicks line up with tiles at any size.
- **The status bars, names under the cursor and the message log are now visible** (the log and dungeon level used to sit off
  screen). The level is shown as "Floor: N" in the side panel.
- Potion, sword, chain mail and scroll items now use sprites instead of text characters.
- Hover/target highlights are a translucent wash instead of inverted colours; popups dim the screen behind them.
- **Typing `q` while entering a name no longer returns to the main menu.**
- The game redraws only when something happens and idles at 60 FPS.
- **Saves from earlier versions no longer load** (save format version 3).

## Phase 2 — data/instance split, spatial index, performance
- **Saves from earlier versions no longer load** (save format version 2). The main menu reports "Failed to load save".
- **Monsters and items no longer spawn inside walls or water** (placement now requires a walkable, unoccupied tile).
- **Attacks and lookups target the living unit** when a creature stands on a corpse (it could hit the corpse before);
  rabbits no longer flee from corpses.
- **Each plant has its own growth period** (gaussian around its species' cycle); previously all plants on a floor were
  copies of one prototype and shared it. Plants without fruit no longer run an (empty) AI each turn.
- A fresh player is created for every New Game (a name typed, abandoned and retyped no longer carries over).
- Fleeing animals give up after a bounded number of tries instead of potentially looping forever.
- Ties between equally close food items are resolved in ring order around the animal (previously set order).
- Same `random`/`numpy` seed now generates the same floor (terrain noise used to ignore it). New games still differ.
- FOV radius is configurable (`GameConfig.fov_radius`, default 80 = whole map, unchanged behaviour).
- Faster floor generation (~2.4x), spawning (~4x) and AI turns (1.1–2.5x); see BENCHMARKS.md.

## Phase 1 — bug fixes
- **Starvation and dehydration now work.** At 0 hunger/thirst any unit loses 1 HP per tick (previously nobody did, and the
  player never saw the messages). The player gets one "is starving!" / "is severely dehydrated!" message when the stat first hits 0.
- **HP can no longer exceed max HP** through `handle_health` (it was clamped to `max_hunger`).
- **Level-up no longer crashes**; it now changes the player's stats (+20 max HP / +1 power / +1 defense as the menu says).
- **Opening the inventory with a Health Potion no longer crashes.**
- **Area-targeting frame** is now the correct size and centred on the cursor.
- `Engine.get_path_to` returns `[]` instead of `None` for out-of-bounds destinations.
- `setup_game` uses the game's `exceptions` module (was `asyncio.exceptions`).
- Menus/AIs no longer share mutable class-level state (`buttons`, `inventory_entries`, `BaseAI.path`).
- Name generation is cached and pure Python (`namegen.py`); output format unchanged, but exact names for a given seed differ
  from libtcod's generator.
- `matplotlib` is no longer a dependency; `utilities.text_input` (broken, unused) was deleted.

## Phase 0
- No behavior changes. Added tests, benchmark and notes only.
