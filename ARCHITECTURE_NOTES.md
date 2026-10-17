# StarStranded — Architecture Notes (Phase 0 baseline, written from the full code)

Status: **baseline of the untouched code** (branch `modernize`, forked from `crafting` @ e01d7a4 + owner WIP
commit). Phase 5 rewrites this file to describe the final architecture.
Where this differs from the original task description, the code wins (see "Differences from the brief").

## Differences from the brief (verified)
| Brief said | Code says |
|---|---|
| tcod 16.2.1 | `pyproject.toml`: `tcod>=21.0.0`; `requirements.txt`: `tcod==20.1.0` (conflict); tested here with **21.2.1** |
| Python >= 3.11 | `pyproject.toml`: `requires-python >= 3.13` (uses `match`); tested on 3.13 |
| `map_codepoints` index scheme | as described; urizen sheet is loaded as 50x50 grid of **24x24 px** tiles (`tile_width == 24`) |
| Selenite is an enemy | Defined but **never spawned** (`enemy_chances` only has `Animal`) |
| stairs mechanic | `generate_noise` never places stairs; `downstairs_location` stays `(0, 0)`; `L` only works if the player stands on (0,0) |
| deps: tcod, numpy | `matplotlib` is also imported unconditionally by `procgen` (and listed in pyproject) |
| `copy.deepcopy` spawning | `Entity.spawn` and `Plant.spawn` deepcopy; `place_entities` also *constructs* every entity first (`[e() for e in chosen]`) then spawns a deepcopy |
| noise is seeded by `random`/`numpy` seeds | **No**: `tcod.noise.Noise()` takes its own random seed. Map generation is only partly deterministic under `random.seed`/`np.random.seed` (tree map and entity placement are; terrain heights are not) |

## Repo layout
- `src/` flat-import package (`import g`, `import engine`, …); must be run with cwd = `src` (assets and `data/namegen` are cwd-relative).
- Assets (do not modify): `urizen_nogrid_white.png` (sprites, 50x50 grid of 24px), `Zesty_curses_24x24.png` (CP437 text, 16x16 grid), `menu_background.png`; unused: `urizen_nogrid.png`, `dejavu10x10_gs_tc.png`, `figure.jpg`.
- `tests/` (pytest, 60 characterization tests), `scripts/benchmark.py`, `scripts/screenshot_baseline.py`, `docs/baseline/*.png`.

## Module map (who imports whom; ▲ = tcod rendering/IO, ◆ = tcod utility)
```
main ▲(tcod.event loop, tileset merge)  ─► setup_game ▲(console, tcod.image, libtcodpy blend/alignment, g.sdl_window)
   │                                         ├► input_handlers ▲(tcod.event.EventDispatch, console draw_frame/print/rgb)
   └► g ▲(tileset load, Console, SDL window+renderer, SDLConsoleRender; OPENS A WINDOW AT IMPORT)
engine ◆(compute_fov, path.SimpleGraph/Pathfinder, los.bresenham) ▲(Engine.render uses console)
world: GameMap (▲ render(console)), GameWorld (pass_time, generate_floor)
procgen ◆(tcod.noise, los) + matplotlib(dead)  ─► components.unit/plant/consumable, world, tile_types, g
tile_types: numpy structured dtype; builds Tile objects at import using utilities.map_codepoints (needs g tileset)
utilities ◆(namegen via implicit libtcodpy alias) ▲(event types) + g (tileset remap): colour helpers, map_codepoints, generate_name
entity (Entity/Item/Constructable) ─► render_order ; components/* ─► utilities.map_codepoints (every entity constructor touches g.global_tileset)
components: unit, plant, ai, inventory, equipment, equippable, level, consumable, names, base_component ; crafting.py (Branch, Spear, Campfire, recipes)
actions (pure game logic, no tcod) ; message_log ▲(console) ; render_functions ▲(console)
```
### tcod usage, split
- **Rendering/IO (to be replaced in Phase 3):** `g.py` (all of it), `main.py` (loop, `convert_coords`, `merge_tileset`), `input_handlers.py` (EventDispatch, KeySym, Modifier, MouseButton, console), `setup_game.py` (MainMenu, CharacterCreation, `tcod.image`), `world.GameMap.render`, `engine.Engine.render` + `mouse_location` (a `tcod.event.Point`), `message_log.render*`, `render_functions.*`, `utilities.is_mouse_in_rectangle`/`text_input`.
- **Utilities (stay):** `tcod.map.compute_fov` (symmetric shadowcast, `engine.update_fov`), `tcod.path.SimpleGraph/Pathfinder` (`engine.get_path_to`), `tcod.noise` (`procgen`), `tcod.los.bresenham` (`engine.can_see`, dead tunnel code), namegen (`utilities.generate_name`, replace in Phase 1). Also `tcod.event.Point` is abused as a plain point in engine/utilities/handlers.

### Import cycles (order matters; `import setup_game` first works)
`consumable → input_handlers → entity/actions`; `crafting → consumable/equippable/inventory`; `plant → crafting`; `inventory → world(GameMap)`; `Constructable.activate` lazily imports `input_handlers`; `engine.update_fov` lazily imports `crafting`.

## Data model (current)
- `Entity` (x, y, name, species(str), `object_type`, sprite_pos tuples, `char/char_left/char_right/char_corpse` = **PUA codepoints** or sometimes plain strings, colour, shade, `mirrored`, flags `blocks_movement/blocks_sight`, `render_order`).
  - `Unit(Entity)`: hp/max_hp, hunger/thirst, base_power/defense, `radius`, `inventory`, `equipment`, `level`, `ai`, `is_alive`. Subclasses `Player`, `Selenite`, `Animal` (always species "Rabbit", random colour).
  - `Plant(Entity)`: growth, `growth_cycle`, `avg_cycle` (gaussian), `inventory`, `fruit` class + `fruit_factory` dict, `PlantAI`; `Tree`, `Shrub` pick a random sprite/name at construction.
  - `Item(Entity)`: `material`; `Consumable` → `HealingConsumable`/`FoodConsumable`(`Meat`, `Fruit`)/`CraftingConsumable`(`Branch`); `Equippable` (`Dagger`, `LeatherArmor`, `WoodenSpear`, unused `Sword`, `ChainMail`); `Constructable` → `Campfire`.
  - Type discrimination is by **duck typing**: `hasattr(e, "is_alive")` (units, includes corpses), `hasattr(e, "growth")` (plants), `hasattr(item, "material")` (== "is an Item"), `hasattr(e, "inventory")` (units AND plants), `hasattr(item, "equipped")`, `hasattr(enemy, "growth_cycle")`, `hasattr(item, "hunger_amount")`.
- `GameMap`: `tiles` ndarray `(w,h)` of `tile_dt` (walkable, transparent, dark(ch,fg,bg), light(ch,fg,bg)); `visible`, `explored` bool `(w,h)` (order F); `entities: set[Entity]` (the **only** store; every lookup is a linear scan); `downstairs_location`; back-refs `engine`, `world`.
- `GameWorld`: dims, `current_floor`, **`current_time` (minutes)**, `generate_floor()` (always `generate_noise`), `pass_time()`.
- `Engine`: `player`, `game_map`, `game_world`, `message_log`, `mouse_location`; owns FOV, pathfinding, LOS, save.
- Save = `lzma(pickle(Engine))` to `savegame.sav` in cwd (typically ~5 KiB compressed).

## Back-references (what makes pickles circular and the refactor subtle)
- `Entity.parent` → `GameMap` **or** `Inventory`; `Entity.game_map`/`.engine` walk the parent chain (`Inventory.parent` → owning Entity → …). An item in an NPC's inventory reaches the engine via NPC → map → engine.
- `GameMap.engine`, `GameMap.world`, `GameWorld.engine`, `Engine.game_map/game_world/player`.
- `BaseComponent.parent` (Inventory, Equipment, Level → owning Entity). `Action.entity`; **AIs are `Action` subclasses** holding `entity`, so `Unit.ai.entity is unit`.
- Global mutable state in `g`: `handlers` (the handler stack), `char_dict`/`mapped_chars` (codepoint registry), `global_tileset` (mutated at runtime by `map_codepoints`), `root_console`, SDL window/renderer. Handlers hold `engine`.
- Because `Engine` is pickled whole, the entire object graph (all entities, inventories, items, AI) is in the save.

## Turn flow
`main` loop: `g.render(handler)` → `tcod.event.get()` → (mouse coords converted pixel→tile by `main.convert_coords`) → `handler.handle_events` → `EventDispatch` → returns Action or next handler → `EventHandler.handle_action` → `action.perform()` (repeating while it returns True, re-rendering) → `Action.perform` ⇒ `GameWorld.pass_time(unit, 1)` — **time only advances when the acting unit is the player**: hunger −1 every 4 min, thirst −1 every 2 min, then `Engine.handle_enemy_turns()` (every non-player entity with an `ai` attribute performs once), then `update_fov()`. NPC hunger/thirst tick inside `BaseAI.perform` using the same `current_time % n`. `PlantAI.perform` (growth every 2nd minute) does not call `super().perform()`. Free actions (no time): Pickup, MassPickup, Equip. Exceptions: `Impossible` → red message, no turn.

## Conventions verified
- **Axes:** tiles/visible/explored are indexed `[x, y]` (width first), numpy order F. `tcod.noise.grid(shape=(map_height, map_width), …)` returns an array shaped `(map_width, map_height)` in tcod 21.2.1 (asserted by `test_axis_convention_noise_grid_shape`), so noise samples already come out `[x, y]`: **consistent, but only by virtue of tcod's grid axis order — fragile across tcod versions** (requirements.txt pins 20.1.0). Phase 5 must state the axis order explicitly when sampling with `origin=`.
- Console is order F, 80x45; the map occupies columns 0–69, rows 0–39 (screen 80x45 minus offsets 10/5). UI: bars at rows 40/42/44, names at row 42 (collides with the Hunger bar), message log at row 49 and "Dungeon level" at row 47 — **both off-screen** (console has 45 rows), so they are never visible today.
- Tile colours for water/walls are `get_random_color()` at import time → differ per process and are not covered by any seed.

## Dead / suspicious code (listed, NOT deleted)
- `procgen`: `generate_map`, `RectangularRoom`, `tunnel_between`, `plant_trees_old`, `construct_old`, `max_*_by_floor` partly; `matplotlib` import & commented plot. `tile_types.down_stairs` only used by `generate_map`.
- `entity_factories.py` (entirely commented), `utilities.text_input` (unused; references nonexistent `tcod.eventKeySym`), `utilities.get_data`, `utilities.SHADES`, `color.colors`.
- `Plant.die` is never called (plants cannot be attacked: `target_unit` only finds units). `Selenite`, `Sword`, `ChainMail`, `ConfusionConsumable`, `FireballDamageConsumable`, `LightningDamageConsumable` (uses nonexistent `take_damage`) are never instantiated. `MainGameEventHandler.get_action_or_event` unused. `world.distance` (module fn) unused. `Unit.has_ai`. `Entity.spawn(new=True)` branch. `g.text_tileset*`, `g.CHARMAP_URIZEN` partially. `max_rooms/room_*_size` plumbed through `GameWorld` but unused by noise generation.
- `Engine.distance(diag=False, euclidean=False)` manhattan branch compares `p1[0]-p1[0]` (always 0) — unused path.
- `Unit.__init__` builds Inventory/Equipment/Level, subclasses build them again.

## Known-behavior catalogue (characterized in `tests/`; fixes tracked in DECISIONS.md)
See DECISIONS.md → "Phase 1 verification" for the verdict on every listed bug plus newly found ones.

## Performance hot spots (baseline numbers in BENCHMARKS.md)
`get_path_to` rebuilds cost array + graph for every call and loops over **all** entities; hostile AIs path every turn when visible. `get_entities_at_location`/`get_unit_at_location`/`render_functions.get_names_at_location` linear scans. `GameMap.render` sorts all entities each frame. `update_fov(radius=100)`. `generate_noise`: Python double loop for lake dilation and per-cell `replace_variations`; per-cell `spawn_vegetation`; deepcopy per tree. `generate_name` re-parses 13 cfg files per call (also makes spawning named units very slow).
