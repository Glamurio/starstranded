# StarStranded — Architecture Notes

Final architecture after the modernization (branch `modernize`, Phases 0–5). The Phase 0 description of the original
code is in git history (`git show 28249f2:ARCHITECTURE_NOTES.md`); DECISIONS.md explains why things are the way they are.

## Overview
A roguelike on an unbounded, chunked alien world. pygame-ce draws and reads input; tcod is used only for FOV, pathfinding,
noise and line drawing; numpy holds terrain. `src/` is a flat-import package run with cwd = `src/` (assets, `data/namegen`
and the save directory are cwd-relative).

```
main.run ──► handlers (input_handlers, setup_game) ──► actions ──► GameWorld.pass_time ──► simulation.run_turn
   │              │ on_render(canvas)                                                     └► Engine.update_fov
   │              └► Engine.render ──► World.render (camera) + panels (render_functions, message_log)
   └► display.Display (window, letterbox, events.translate) ; g (handler stack, canvas, display)
World (one floor) ──► chunks.Chunk × N (terrain + entity index) ; view.ViewWindow (stitched arrays, FOV) ; source
source = worldgen.NoiseWorldSource (generated floors) | world.FixedLandscape (bounded test maps) | worldgen.FlatWorldSource
savegame: chunk (de)serialisation (also used for unloading) and the save directory
```

## Modules
| Module | Responsibility |
|---|---|
| `main.py` | `run()` loop: poll events, redraw only after events, 60 FPS cap, save on exit/crash. |
| `g.py` | Handler stack `g.handlers`, `g.display`, `g.canvas`, `g.init()`, `g.draw()`, `g.render()`. (Kept small; not extended.) |
| `display.py` / `events.py` | Window, 1920x1080 logical surface, integer/fractional scaling with letterbox, pixel → cell; internal events, `Key/Mod/MouseButton`, `EventDispatch`. |
| `atlas.py` / `ui.py` | `SpriteAtlas` (Urizen sheet as white alpha mask, cached tinted/flipped variants); CP437 `Font` and `Canvas` (cell-grid text, frames, bars, sprites, highlights, dimming, badges). |
| `input_handlers.py`, `setup_game.py` | All screens (main game, menus, inventory/loot, targeting, look, history, level-up, popups, crafting, placement, game over); `new_game`, `load_game`. Screen cells ↔ world tiles via `Engine.camera`. |
| `actions.py` | Player/AI actions; every action that passes time calls `GameWorld.pass_time`. |
| `engine.py` | `Engine`: player, current `game_map` (the floor's World), `game_world`, message log, config, `camera`; FOV (`update_fov`), pathfinding (`get_path_to`), LOS, `can_move`, `render`. |
| `world.py` | `World` (entity container + chunk management + terrain queries + rendering), `GameMap` (bounded single-chunk World with array views), `FixedLandscape`, `GameWorld` (seed, floors, clock). |
| `chunks.py` | `CHUNK_W/CHUNK_H = 70/40`, `chunk_key/local/chunk_origin/keys_around/chebyshev`, `Chunk`. |
| `view.py` | `ViewWindow` (stitched `transparent/walkable/in_bounds` + `visible`), `Camera`. |
| `worldgen.py` | `mix_seed`, `seeded_rng`, `TerrainNoise`, `base_terrain`, `generate_terrain`, `NoiseWorldSource`, `FlatWorldSource`. |
| `procgen.py` | Spawn tables, `place_entities(world, floor, area)`, `neighbour_masks/dilate/replace_variations`. |
| `simulation.py` | Tiers, `run_turn`, `upkeep` (exact / analytic catch-up), `near_step` (simplified AI). |
| `savegame.py` | `SAVE_VERSION = 4`, `serialize_chunk/restore_chunk`, `save_game/load_game` (directory format). |
| `species.py`, `entity.py`, `components/*` | Frozen definitions (`UnitSpecies`, `PlantSpecies`, `ItemKind`) and instances (`Unit`, `Plant`, `Item`…) with components (AI, inventory, equipment, level, consumables). |
| `tile_types.py`, `render_order.py`, `config.py` | Tile dtype and terrain kinds (`VOID`, `SHROUD`, floor, water, wall, roots, stairs); draw layers; `GameConfig`. |

## Coordinates and conventions
- World tiles `(x, y)` are unbounded ints (negative allowed); every entity stores world coordinates.
- Chunk `(cx, cy) = (x // 70, y // 40)`, local `(x % 70, y % 40)`. All arrays are indexed `[x, y]` (width first), order F.
- Noise: `tcod.noise.grid(shape=(h, w), scale, offset=(y0, x0))` returns `(w, h)`; `offset` is in sample units and follows
  `shape` order. Asserted in `TerrainNoise.sample` and tested (`test_noise_axes.py`).
- View window: chunks within `near_radius` of the player's chunk (3x3 = 210x120 by default), origin `((pcx-1)*70, (pcy-1)*40)`.
- Screen: map viewport = top-left 70x40 cells; `Camera.follow` centres on the player (`(px-35, py-20)`), clamped for bounded maps;
  `Engine.mouse_location` is in world tiles.
- Tile record: `walkable`, `transparent`, `light` and `dark` graphics `(sprite, flip, fg, bg)`; `light` when visible, `dark` when
  explored, nothing otherwise.

## World, chunks and entities
- `Entity.parent` is the World (or an `Inventory`). The World owns `_by_pos` for loaded entities and routes the per-chunk index
  (`Chunk.entities`, `by_category`, `actors`, `buckets` per render layer, `blocked`) by position. `x/y`, `blocks_movement`,
  `render_order` and `ai` are properties that notify the container (`SpatialContainer`). Crossing a border re-indexes the same
  object in the other chunk; a player crossing triggers `World.update_tiers()`.
- Only loaded chunks exist for queries (`in_bounds`), so nothing steps into unloaded terrain. Terrain edits go through
  `World.modify_tile/set_tile` (bump `Chunk.terrain_version`, which invalidates the view window).
- Queries: `get_entities_at_location`, `get_unit_at_location` (living first), `stack_at` (top layer first), `entities_on_ring`,
  `is_walkable/is_transparent/is_explored/is_visible/is_blocked`, `tile_at`, `region(field, rect)`; collections `entities`,
  `units`, `plants`, `items`, `actors` are live views over loaded chunks.
- `GameMap(engine, landscape, entities)` = bounded world (landscape at (0, 0) in chunk (0, 0)) with `tiles/explored/visible/blocked`
  array views and `width/height`; used by tests, the screenshot script and the benchmark scenario.

## Simulation
- `GameWorld.pass_time` (player turns): advance the clock, player hunger/thirst, `simulation.run_turn`, `update_fov`.
- ACTIVE (`active_radius`, default the player's chunk): full AI each turn. NEAR (`near_radius`, default the 8 neighbours): every
  `near_interval` (2) turns `near_step` (upkeep + flee / approach / eat adjacent / random step; no pathfinding, no messages).
  Loaded chunks beyond `near_radius` (the `unload_radius` hysteresis band) are frozen; beyond `unload_radius` they are unloaded.
- `upkeep(entity, now)` per entity (`last_upkeep`): one turn = the original code; longer = analytic (hunger/thirst steps and
  starvation damage, foraging floor at half when the chunk has food and the absence is long, plant growth cycles).
- Pathfinding: tcod `Pathfinder` on the window crop of `path_radius` (40) around the origin; cost = in-bounds & (walkable or
  unexplored), +10 per blocker. FOV: `compute_fov` on the window (`fov_radius` 41) + lit campfires; `explored` is written back.

## Rendering and input
- `World.render(canvas, camera)`: terrain for the camera rectangle from chunk `light/dark` + window `visible`, grouped by distinct
  graphic and drawn with one `Surface.blits`; entities from the chunks under the camera layer by layer (CORPSE < ITEM < SHRUB < UNIT
  < TREE), each with its own tint and mirror flag; clutter safeguard (top 2 ground objects + "+" badge).
- `Engine.render`: map + bars (rows 40/42/44), names under the cursor (top-first), message log, side panel (floor, position).
- Handlers get cell-based events; world positions go through `Engine.camera` (`screen_to_world`, `highlight_world`).

## Generation
- Seeds: `GameWorld.seed` → `floor_seed = mix_seed(seed, floor)` → `chunk_seed = mix_seed(floor_seed, cx, cy)` (blake2b).
- `generate_terrain` works on a 2-tile padded region (lake dilation + edge variations see the true neighbours) and keeps the interior;
  all chunk randomness runs inside `seeded_rng(chunk_seed)` (restores the global RNG state afterwards).
- Per floor: one tree and one shrub species. Per chunk: plants on roots, `place_entities` (old per-map rules). Chunk (0, 0): start
  tile closest to the centre, walkable down staircase 8–20 tiles away.

## Saves
- `savegame/manifest.lzma` (`{"version": 4, "world_class", "body"}`) + `savegame/floor<N>/chunk_<cx>_<cy>.<gen>.lzma`.
  Manifest body: floor, seeds, source (with species), clock, player, message log, config, stairs, loaded set, chunk file table,
  next uid. Chunk files: tiles, explored, entities (persistent ids for World/Engine/player/procedural definitions).
- Writes: changed chunks under a new generation, then the manifest (atomic replace), then unreferenced files are deleted.
- Loading reads the manifest and the visited chunks' bytes, restores the loaded set, re-adds the player, applies catch-up.

## Floors
Each floor is its own World (own seed and chunk grid). `TakeStairsAction` on the staircase → `GameWorld.generate_floor()`; the
previous floor is dropped (no way back up).

## Testing and tools
- `tests/` (pytest, headless via `SDL_VIDEODRIVER=dummy`, `conftest.g.init(headless=True)`): `small_world` (bounded GameMap) and
  `new_engine` (generated floor) fixtures, `index_helpers.assert_index_consistent`, `render_helpers` (pixel checks),
  `test_chunked_world.py` (Phase 5 acceptance), `test_screens.py` (every handler), `test_main_loop.py`.
- `scripts/benchmark.py` (fixed scenario + chunked-world sections), `scripts/screenshots.py`, `scripts/debug_plot_terrain.py`.

## Differences from the brief (verified at Phase 0)
| Brief said | Code said |
|---|---|
| tcod 16.2.1 | `pyproject.toml`: `tcod>=21.0.0`; tested with **21.2.1** |
| Python >= 3.11 | `requires-python >= 3.13` (uses `match`); tested on 3.13 |
| Selenite is an enemy | Defined but never spawned (still true) |
| stairs mechanic | the noise generator never placed stairs (fixed in Phase 5) |
| deps: tcod, numpy | `matplotlib` was imported by `procgen` (removed in Phase 1) |
| noise seeded by `random` | it was not (fixed in Phase 2; per-chunk seeds since Phase 5) |
