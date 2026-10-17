# Changelog

Behavior changes made by the modernization project (branch `modernize`). Pure refactors are not listed.

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
