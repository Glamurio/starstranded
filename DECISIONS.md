# Decisions

## Repository / process decisions
- **Branch:** all work is on `modernize`, forked from `crafting` (the checked-out branch, e01d7a4).
- **Owner WIP:** `src/components/ai.py` had an uncommitted `PassiveAI` change (`seeking` reset: dropped `not self.seeking and`
  from the hunger check and added `self.seeking = False`). Per owner choice it is committed unchanged as the first commit on
  `modernize`. Behavior from here on includes it.
- **Line endings:** the repo stores LF; the owner's Windows checkout is CRLF. Commits from the dev VM use
  `git -c core.autocrlf=input` so blobs stay LF and diffs stay minimal. Edits to existing files preserve CRLF.
- **Commit identity:** Phases 0–1 committed as `Pascal <p.kammer@satzweiss.com>`; from Phase 2 on, per owner instruction, `Ryou Takeshi <ryou.takeshi@gmail.com>` (author and committer) via env vars. No git config changed, history not rewritten.
- **Python/tcod:** developing and testing on Python 3.13 + tcod 21.2.1 (matches `pyproject.toml`; `requirements.txt` still says
  `tcod==20.1.0` — see Needs owner decision).
- **Tests run from `src/`** (flat imports, cwd-relative assets); `tests/conftest.py` handles path/cwd/SDL dummy driver.
- **Characterization convention:** tests that pin a known-buggy behavior are named `test_current_*`; the Phase 1 fix commit
  inverts them.

## Phase 1 verification (verdict and outcome per item)
| # | Item | Verified against code? | Outcome |
|---|---|---|---|
| 1 | `handle_hunger/thirst` condition `not self.engine.player` | Yes: always False ⇒ no starvation/dehydration damage or message for anyone | **Fixed.** Semantics chosen: at 0 hunger/thirst *any* unit loses 1 HP per tick; the message goes to the player only, once, when the stat first reaches 0; starvation deaths have no killer (no XP). |
| 2 | `handle_health` clamps to `max_hunger` | Yes: HP could reach 100 with `max_hp` 30 | **Fixed** (clamp to `max_hp`). |
| 3 | Mutable defaults / class-level mutables | Yes. Latent defaults: `map_codepoints`, `Tile`, `MovementAction`, `Fruit`, `InventoryLootHandler`. Live shared state: `InventoryEventHandler.buttons/inventory_entries`, `MainMenu.buttons`, `BaseAI.path` | **Fixed**, plus a guard test that scans every module for mutable defaults. `CharacterCreation.PLAYER` (shared Player built at import) left as is → Needs owner decision #8. `g.handlers` is an intentional module global (to be reduced in Phase 3). |
| 4 | `get_entities_at_location` annotation | Yes (returns `list`) | **Fixed** (`List[Entity]`). |
| 5 | `get_path_to` returns `None` out of bounds | Yes; the hover-path preview iterates it | **Fixed** (returns `[]`); regression test renders the main handler with the cursor out of bounds. |
| 6 | `AreaRangedAttackHandler.on_render` frame | Yes: `width=radius**2`, origin `x-radius-1` | **Fixed.** The affected area is `2r+1` wide; the frame encloses it on the ring outside, so `2r+3` wide, centred on the cursor (`area_frame_rect`). Note the fireball uses a Euclidean disc, so the square is its bounding box. |
| 7 | `matplotlib` import in `procgen` | Yes | **Fixed.** Removed from code and `pyproject.toml`; plotting is `scripts/debug_plot_terrain.py` (lazy import). Subprocess test guards it. |
| 8 | `utilities.text_input` | Broken (`tcod.eventKeySym` does not exist in 21.2.1) **and unused** | **Deleted.** |
| 9 | `generate_name` re-parses cfgs per call | Yes. `tcod.namegen_*` still works but only via the deprecated implicit `libtcodpy` alias (FutureWarning "Soon the 'tcod' module will no longer be an implicit reference to 'libtcodpy'") | **Replaced** by `src/namegen.py`: same cfg files, parsed once (`lru_cache`), pure Python, supports the documented syntax; `utilities.generate_name` re-exports it. |
| 10 | `map_codepoints` index scheme | Noted, **not fixed** (deleted in Phase 3). Overflow only for sprites in rows ≥ 28 that also use mirror/corpse; variation index `1 + i + …` can collide with neighbouring sprites | n/a |
| 11 | Noise axes | Consistent **only because** tcod 21.2.1's `grid(shape=(h, w))` returns `(w, h)`; `requirements.txt` pins 20.1.0, which may differ | **Documented**; `generate_noise` now asserts the shape and tests cover non-square maps (70x40, 33x17, 17x33). |
| 12 | `Plant.die` swaps in a blocking, opaque roots tile | Yes. Also **unreachable today** (nothing can attack a plant) | **Flagged, not changed** (decision #3). |

### Additional defects found while reading (not in the brief)
| Item | Evidence | Plan |
|---|---|---|
| Level-up crashes: `Level.increase_max_hp/power/defense` touch `self.max_hp/hp/base_power/base_defense` on the Level component | `tests/test_level_up.py` | **Fixed** (separate commit; changes `self.parent`) |
| Opening the inventory with a Health Potion crashes: `chr(entity.char)` with `char == "!"` | `tests/test_inventory_render.py` | **Fixed** minimally (`entity_glyph`); the whole `char` mechanism is deleted in Phase 3 |
| `get_unit_at_location` can return a *corpse* when a living unit shares the tile (`units` includes dead units) ⇒ melee/bump can target the corpse | `test_current_get_unit_at_location_may_return_a_corpse` | gameplay semantics ⇒ **Needs owner decision** (proposal below) |
| `setup_game` does `from asyncio import exceptions` | `test_setup_game_uses_the_game_exceptions_module` | **Fixed** |
| `Engine.distance` manhattan branch always 0 | `test_distance_helpers` | flag only (unused branch) |
| `BaseAI.flee` / `get_random_tile` `while True` loops can spin forever with no valid tile | read | flag; revisit in Phase 2 |
| PassiveAI flees from *corpses* of other species (`units` includes dead) | read | **Needs owner decision** (same root cause as above) |
| UI rows off-screen: message log (row 49) and "Dungeon level" (row 47) on a 45-row console; names row collides with the Hunger bar | `docs/baseline/in_game.png` | Phase 3 UI work (will place them sensibly) |

## Owner decisions (delegated to Claude on 2026-10-17: "I'll leave the decisions to you … we can revisit them later")
Each item below is **decided by Claude, revisit later**. Gameplay-tuning questions that a refactor phase should not silently
change stay listed under "Open gameplay questions".
1. **Hunger/thirst semantics:** as implemented in Phase 1 (1 HP per tick at 0 for any unit; one message for the player).
2. **Corpse vs living unit on one tile:** *fixed in Phase 2.* "The unit at x,y" prefers a living unit (corpse as fallback); PassiveAI
   no longer flees from corpses. Corpses stay visible and lootable.
3. **`Plant.die` tile swap:** keep as is (opaque, unwalkable roots). Unreachable until plants can be attacked; revisit then.
4. **Stairs:** no stairs in noise terrain for now; Phase 5 uses its default (each floor its own World).
5. **`requirements.txt`:** aligned with `pyproject.toml` in Phase 2.
6. **Free actions** (pickup, mass pickup, equip): kept free.
7. **Unspawned content** (`Selenite`, `Sword`, `ChainMail`, confusion/fireball/lightning): kept and ported to the new data model,
   not spawned. The three scroll-like consumables call a non-existent `take_damage`; left broken-but-unreachable and noted.
8. **`CharacterCreation.PLAYER`:** a fresh Player per New Game (Phase 2).

## Open gameplay questions (flagged, deliberately not changed)
- `PassiveAI.seek_food` never walks toward food that is not adjacent: `if not closest_plant or not closest_food: wander()` is true
  whenever only one of the two was found (always, since the search stops at the first hit). Rabbits only eat by chance.
- Hungry rabbits pick a brand-new random wander target every turn (jittery movement, one pathfind per turn each).
- A unit whose `ai` is falsy cannot die (`handle_health` requires `self.ai`); the player keeps a dummy `HostileAI` for that reason.
- The Player's `HostileAI` exists only so it "can die" and for legacy pathfinding calls.


# Phase 2 design plan (written before implementation)

## Goals recap
(a) immutable shared definitions instead of `deepcopy` spawning; (b) O(1) position lookups owned by `GameMap`;
(c) remove avoidable per-call/per-frame work; keep tcod rendering working; tests stay green.

## New modules
- `config.py`: `GameConfig` (frozen dataclass) with tunables: `fov_radius`, `ai_path_margin`, etc. One instance lives on
  `Engine.config`. Not a global-module pattern: it is passed/owned explicitly.
- `species.py`: frozen, hashable dataclasses + registries:
  - `UnitSpecies(key, name, sprite, corpse_sprite, mirror, color | None (=random per instance), shade_sigma | None,
    max_hp, power, defense, radius, max_hunger, max_thirst, inventory_capacity, level_up_base, xp_given, ai: AIKind,
    name_origin | None)` — registry `UNIT_SPECIES` (`human`, `selenite`, `rabbit`).
  - `PlantSpecies(key, name, category TREE|SHRUB, sprite, corpse_sprite, color, max_hp, growth_cycle, blocks_movement,
    blocks_sight, render_order, fruit: ItemKind | None)` — **procedural**: `make_tree_species(rng)` / `make_shrub_species(rng)`
    reproduce today's constructor randomness exactly (sprite/shape names, colour group naming, 80 % fruit chance, fruit name).
  - `ItemKind(key, object_type, species, sprite | glyph, color, shade_sigma, material, render_order, food/heal amounts,
    equipment_type/bonuses, light_radius, …)` — registry `ITEM_KINDS` (`health_potion`, `meat`, `branch`, `dagger`,
    `leather_armor`, `sword`, `chain_mail`, `wooden_spear`, `campfire`, and the dead scroll consumables). Fruit kinds are procedural
    and owned by their `PlantSpecies`.
- Glyph lookup (`glyphs(kind)`) is a cached function mapping a definition to its PUA codepoints via the existing
  `map_codepoints`; that whole layer disappears in Phase 3, so nothing else depends on codepoints.

## Instances (what an entity stores)
`Entity`: `kind` (the definition object), `_x`, `_y`, `parent` (container: `GameMap` or `Inventory`), `name`, `attributes`,
`color` (per-instance tint where the kind says "random"/derived), `shade`, `mirrored`, plus subtype state:
- `Unit`: hp/max_hp (max can grow on level-up), base_power/defense, hunger/thirst, `inventory`, `equipment`, `level`, `ai`, `is_alive`.
- `Plant`: hp, growth, `avg_cycle` (gaussian per instance), `inventory`, `ai`, `dead`.
- `Item` subclasses: `equipped`, `is_placed`/`is_lit`, `material` override (Meat/Branch record their source).
Static data is read through properties (`species`, `object_type`, `power_bonus`, …) so call sites keep working.
Subclasses stay where they carry **behaviour** (`Meat`, `Fruit`, `HealthPotion`, `Dagger`, `Campfire`, `Tree`, `Animal`…);
they are thin constructors that pick a definition. No `deepcopy` anywhere: spawning = construct + `GameMap.add_entity`.
Per-instance randomness (tint, mirroring, plant `avg_cycle`) is rolled in `__init__`.

Behaviour note: today all trees/shrubs on a floor are deepcopies of *one* `Tree()`/`Shrub()` prototype, so they already share
species, sprite, fruit and **also `avg_cycle`**. New code: one tree species and one shrub species per floor (same as today),
but `avg_cycle` is rolled per plant as the constructor clearly intended. Logged in CHANGELOG.

## Type checks
`hasattr` duck typing is replaced by `isinstance` (`Unit`, `Plant`, `Item`, `FoodConsumable`, `Equippable`) and a small
`Entity.has_inventory` property. `GameMap.units/plants/items/actors` are maintained collections, not scans.

## Spatial index & ownership (`GameMap` is the only mutator)
- `GameMap._entities: dict[Entity, None]` (insertion-ordered ⇒ deterministic iteration, unlike the old `set` hashed by `id`),
  `_by_pos: dict[(x, y), list[Entity]]`, per-kind dicts (`units`, `plants`, `items`), `actors` (entities with an AI),
  render buckets per `RenderOrder`, and `_blocked: np.int16[w, h]` counting movement-blocking entities per tile.
- API: `add_entity(e, x, y)` (detaches from any previous container), `remove_entity(e)`, `move_entity(e, x, y)`.
  `Entity.x/y` are properties; assigning them while on a map routes through `move_entity`, so the index cannot go stale.
  `blocks_movement`, `render_order` and `ai` are properties that notify the map so buckets/blocked counts/actor set stay right.
- `entities` becomes a read-only live view (`dict.keys()`); code that mutates while iterating must copy (handled at call sites).
- Lookups: `get_entities_at_location`, `get_unit_at_location` (living first), `can_move`, names-at-mouse, pickup/drop, plant
  dropping, food search (ring scan over `_by_pos`) all use the index.

## Back-references: what is removed, what remains (documented)
Removed/reduced: `GameMap.world` (unused), `Entity.spawn`, per-entity codepoint fields, class-level shared state, AI-specific
`ai` argument to pathfinding (`get_path_to(origin_entity, …)`). Remaining, by design for this phase:
`Entity.parent` (the container that owns it), `Component.parent` (owning entity), `AI.entity`, `GameMap.engine`,
`GameWorld.engine`. `entity.game_map`/`entity.engine` stay *derived* properties (no stored pointer). Removing `GameMap.engine`
would mean threading the engine through every action/component call; Phase 5 replaces `GameMap` with a World/view anyway, so
doing it twice is wasteful. Pickles stay circular but compact (pickle memoizes shared objects).

## Pickling, identity, save format
- Static definitions pickle **by registry key** (`__reduce__` → registry lookup), so a loaded game's Rabbits share the
  process-wide `UnitSpecies("rabbit")` object. Procedural definitions (plant species, fruit kinds) pickle by value; pickle's memo
  keeps one shared object per save.
- Save payload: `{"version": SAVE_VERSION (=2), "engine": engine}`; `load_game` rejects anything else with a clear message.
  Old saves do not load (CHANGELOG says so).
- Entity identity: unchanged — the same Python object is moved, never copied. Each entity also gets a process-unique `uid`
  (monotonic counter, persisted) for Phase 5 chunk transfers/deltas.

## Performance work
- Pathfinding: per-map cached base cost (`walkable | ~explored`), invalidated only when tiles change or exploration grows;
  per call `cost = base + 10 * blocked` masked to passable tiles (vectorised, no entity loop).
  *Outcome (measured):* the search window was **dropped** — tcod's Pathfinder was slower on a cropped 14x18 grid (124 µs) than on
  the whole 70x40 map (88 µs), so cropping buys nothing at this map size (revisit for Phase 5's stitched window, where a cap
  is a hard requirement). Legacy `tcod.path.AStar` was 5x faster (17 µs) but returned a costlier route in 12 of 1,602 random
  queries, so the exact `Pathfinder` stays. Paths are *identical* to the old implementation (tested against a copy of it).
  The gain is modest: 1.0x–1.26x per query depending on entity count (150 → 394 entities) and 1.05x in the fixed-scenario
  benchmark, because tcod's search dominates. (An earlier single-route figure of 197 → 134 µs overstated it.)
- FOV: `config.fov_radius`, default **80** = ceil(sqrt(69² + 39²)), i.e. the whole 70x40 map remains visible from anywhere
  (unchanged behaviour while the camera is fixed). Phase 5 (camera centred on the player) should lower it to ~41 (half-diagonal of the view).
- Render: iterate render buckets in order (no per-frame sort).
- Procgen: lake dilation via array shifts; `replace_variations` vectorised (neighbour masks → 16-case lookup); vegetation via
  `np.argwhere`. Old implementations kept in tests as reference to prove identical output.
- AI: only `actors` are iterated per turn; food search is a ring scan over the index; `flee` gets a bounded number of tries.


# Phase 2 outcome (what was actually done; supersedes the plan where they differ)
- **Definitions:** `species.py` holds frozen `UnitSpecies`/`PlantSpecies`/`ItemKind` plus registries; `entity.kind` points at one.
  Static ones pickle by key (identity preserved on load); procedural plant/fruit kinds pickle by value. Subclasses
  (`Player`, `Animal`, `Tree`, `Meat`, `Dagger`, `Campfire`, …) remain as thin behaviour carriers that pick a definition.
- **No deepcopy:** `Entity.spawn`/`Plant.spawn` removed; spawning = constructor + `GameMap.add_entity`. `place_entities` picks
  factories and constructs one instance per placement.
- **Type checks:** every `hasattr` replaced by `isinstance`, `EntityCategory` (class attribute) or `has_inventory`.
- **Spatial index:** as planned (`_by_pos`, categories, actors, render buckets, `blocked` counts); `x/y`, `blocks_movement`,
  `render_order`, `ai` are notifying properties. Index invariants are checked by `tests/index_helpers.assert_index_consistent`
  (incl. a 600-step random soak test).
- **Back-references remaining (by design, see plan):** `Entity.parent` (container), `Component.parent`, `AI.entity`,
  `GameMap.engine`, `GameWorld.engine`; `entity.game_map`/`entity.engine` are derived. Removed: `GameMap.world`, the
  `ai` argument of `get_path_to`, all per-entity codepoint fields, the shared class-level state.
- **Save format v2** (`{"version": 2, "engine": …}`), atomic write, uid counter bumped past loaded entities; v1 saves rejected.
- **Determinism:** seeding `random`+`numpy` now reproduces a whole floor (noise seeds drawn from `random`; tile palette uses a
  private RNG). Needed for comparable benchmarks and for Phase 5 chunk regeneration.
- **Benchmarks** rebuilt on a fixed scenario; the Phase 0 table was on unseeded terrain and is not comparable (see BENCHMARKS.md).
- **Decided along the way (owner-delegated):** living units preferred over corpses (#2), fresh player per New Game (#8),
  requirements.txt aligned (#5); plus a spawn-placement bug fix (monsters/items could spawn in walls/water).
- **Process note:** one commit (42ab790) was made with a failing test and fixed in the next commit (20fcbca); the commit helper
  now runs the test suite and refuses to commit on failure. 22 `tests/__pycache__` files were committed by mistake in Phases
  0–2 and untracked in f6e2376 (history not rewritten).
- **Commit messages** up to and including 2f0fa2f carry AI attribution trailers; per the project instructions ("never mention
  Claude in any commit") later commits do not. History is not rewritten.

# Phase 3 outcome (pygame-ce migration)

| Decision | Why | Alternative considered |
|---|---|---|
| **Hybrid: pygame-ce draws and reads input; tcod stays for FOV (`compute_fov`), pathfinding (`tcod.path`), noise and `tcod.los.bresenham`.** A test (`test_no_tcod_rendering`) fails if `tcod.console/event/tileset/render/sdl/image` or the old codepoint layer reappears. | The brief asks for exactly this split; tcod's algorithms are the part worth keeping. | Replace FOV/pathfinding too: out of scope, and the Phase 2 benchmarks depend on tcod's search. |
| **`SpriteAtlas`** (`atlas.py`): the Urizen sheet is loaded once. The sheet is an 8-bit image where near-white = sprite, near-black = background, so it is converted to a *white RGBA mask*; tinting is one `BLEND_RGBA_MULT` fill. Sprite id = `row*50+column`; variants cached by `(sprite, flipped, tint)` and `(…, bg)` for terrain, bounded at 6000 entries (cleared wholesale) because every tree has its own gaussian tint. | One load, one cache, no per-frame surface creation; the white mask makes tint/mirroring trivial. | Per-entity pre-tinted surfaces (unbounded memory); keeping the PUA remap (needs a tcod tileset). |
| **Tile layout:** `graphic_dt = (sprite:int32, flip:bool, fg:3B, bg:3B)`; `SHROUD` has `NO_SPRITE`; `Tile(sprite=(col,row), variations=[(col,row,name)])` gives `.sprite` and `.variation_ids`. Visible = `light`, explored = `dark`, else nothing is drawn. `Plant.on_added_to_map` writes the plant sprite + flip into `tile['dark']` (remembered view, as before). | Sprite ids are what the atlas needs; `flip` makes mirroring a render-time flag (no per-direction duplicate glyphs). | Storing only terrain in tiles and drawing remembered plants from the entity list each frame (slower, needs iterating plants). |
| **Terrain batch:** `GameMap.render(canvas, origin)` builds one packed int key per shown tile (`sprite|flip|fg|bg`), `np.unique` groups them, each group is one cached surface from `atlas.get_on`, and a single `Surface.blits` draws all tiles. Entities follow in render order, each tinted by its `shade`, in a second `blits`. `origin` already supports a camera offset for Phase 5. | Python work scales with visible tiles only for list building; surfaces come from cache. ~3.5 ms per frame (BENCHMARKS.md). | Per-tile `blit` calls; caching a whole-map surface (FOV changes nearly every turn). |
| **Fixed logical screen 80x45 cells x 24 px = 1920x1080**, drawn on `Display.surface`, presented by the largest *integer* scale that fits the window (nearest neighbour) or, when the window is smaller than 1920x1080, a fractional smooth scale; centred with black letterbox bars. Mouse pixels are mapped back through the same transform (`Display.to_cell`; clicks in the bars are ignored). Initial window = logical size shrunk to 90 % of the desktop. | Crisp pixel art at any window size; handlers only ever see cell coordinates. | `pygame.SCALED` (cannot go below 1x, picks its own window size, hides the transform from tests). |
| **Internal events** (`events.py`): `Quit`, `KeyDown(sym, mod)`, `TextInput`, `MouseMotion/ButtonDown(position in cells)`, `WindowChanged`, plus `Key`/`Mod`/`MouseButton` constants (pygame keycodes) and an `EventDispatch` that calls `ev_<type>`. `input_handlers`/`setup_game` no longer import pygame or tcod. | Handlers become testable with synthetic events (`tests/test_screens.py` drives every screen) and independent of the windowing library. | Passing pygame events to handlers. |
| **Text/UI** (`ui.py`): `Canvas` works in *cell* coordinates and mirrors the small subset of `tcod.Console` the screens used (`print` with alignment/bg, `draw_frame`, `draw_rect/fill`) plus `draw_bar`, `sprite`, `highlight`, `dim`, `blit_image`. The font is the existing **CP437 "Zesty curses" 24x24 sheet** (converted to a white alpha mask, glyph colour = tint). | Keeps the exact look and the 80x45 layout; no new asset. | TTF via `pygame.font` (new asset, sub-cell layout work, different look). |
| **Highlights** (path preview, pickup target, placement tiles) are a translucent white wash over the cell, not the old inverted fg/bg. Popups dim the whole screen behind them. | Sprites have no meaningful "inverse"; a wash keeps the sprite visible. | Drawing an outline only. |
| **Item sprites for the former text-glyph items:** potion (29,19), sword (29,21), chain mail (32,23), scroll consumables (33,24), picked from the sheet by eye. Items drawn on the map keep their old shade rule (white unless `shade_sigma`), menus tint with `entity.color`. | Everything is a sprite now; the text-glyph path is gone. Scrolls and sword/chain mail are still unspawned. | Keeping a text-glyph draw path. |
| **Main loop** redraws only after input/window events and ticks at 60 FPS; exceptions in handlers go to the message log; `SystemExit` and any other exception still save before exiting. | Idle game costs no CPU; per spec. | Redrawing every frame. |
| **Layout fix:** status bars rows 40/42/44, names under the cursor at (21,40), message log rows 41-44 (x 21..79), "Floor: N" in the side panel at (map width+1, 1). | The log (row 49) and level (row 47) were off the 45-row console and never visible. | Enlarging the console. |
| **Save version 3** (tile dtype changed). Version 2 saves are rejected with the usual message. | Old maps hold codepoints. | Migrating (no real saves to preserve). |
| **Name entry:** only Escape leaves the prompt; typing `q` no longer returns to the menu (it did, because `Q` was also a key binding while text input was active). | Obvious bug exposed while porting `ev_keydown`; trivial fix. | Leaving it. |
| **Benchmark scenario** exists in both tile layouts (`scenario_landscape_tcod.npy` for old checkouts). | Keeps `--src` A/B runs working. | – |

Not done on purpose: dirty-rect/terrain-layer caching and any other render optimisation (frame ≈ 3.8 ms; owner postponed the
performance overhaul), fullscreen toggle, key rebinding, sound. `utilities.get_data` (dead, pointed at a libtcod folder) was deleted.

# Phase 4 outcome (sprite layering)

| Decision | Why | Alternative considered |
|---|---|---|
| **Layer stack = `RenderOrder`**: terrain < CORPSE < ITEM < SHRUB < UNIT < TREE (`render_order.LAYERS`; the enum value is the position). Every entity on a visible tile is drawn as its own sprite with its own `shade` tint and `flipped` flag; sprites are transparent between strokes, so lower layers show through. Corpses switch layer when a unit or plant dies (as before). | The buckets introduced in Phase 2 already iterate in this order; making it explicit and tested was all that was needed. | A per-tile "top entity only" renderer (loses the corpse/item under a unit, which the brief wants visible). |
| **Clutter safeguard** is one flag, `GameConfig.clutter_safeguard` (default **on**), with the cap in `render_order.MAX_GROUND_OBJECTS_PER_TILE = 2`. Per visible tile only the top two *ground* objects (corpses, items; items sit above corpses, newer above older) are drawn and a small "+" marker (`Canvas.badge`, top-right quarter of the cell) shows that more are hidden. Units, shrubs and trees are never hidden, so a unit standing on a big pile is drawn normally on top of the two visible objects. Off: draw everything. | A pile of five transparent sprites is an unreadable blob; the cap keeps the top of the pile readable without hiding creatures. | Hiding the pile whenever a unit stands on it (the unit's own tile is exactly where you want to see what you are standing on); shrinking sprites; a count badge (one more thing to read). |
| **Hidden objects stay discoverable:** `GameMap.stack_at(x, y)` returns the whole tile top-first (layer descending, newest first within a layer). The names under the cursor / look use it (cut with "..." if wider than the panel) and so does the pickup window (`PickupHandler` → loot list), which now lists the topmost object first. | What you see first is what you read first; nothing hidden is lost. | Keeping insertion order (bottom first: the corpse before the item on top). |
| **Per-layer mirror/tint:** unchanged semantic, now covered by tests: units mirror with their facing, corpses and items are never mirrored, each entity keeps its own shade. | – | – |
| **Verification:** `tests/test_layering.py` composites the expected tile by hand (floor tile + each sprite in order) and compares pixels exactly, for a corpse+item under the player, under an animal, a full 5-layer stack, the capped pile (left half exact, marker present), the uncapped pile, and units on piles. `scripts/screenshots.py` writes zoomed crops to `docs/phase4/`. | Pixel equality is stricter than "something is drawn". | Eyeballing screenshots. |

Not done on purpose: dimming/greying corpses (they keep their entity's tint), a scrollable "what is here" window beyond the names line and the
pickup list, per-pile marker counts.

# Phase 5 design plan: chunked world (written before implementation)

Goal (brief): an unbounded world of 70x40 chunks, generated deterministically per chunk, simulated in tiers, seen and
pathfound through a stitched window, saved as per-chunk files plus a manifest. This plan is meant to be implementable
by another session; "Phase 5 outcome" (written at the end) records where the implementation differs.

## Coordinates and conventions
- **World tile coordinates** `(x, y)`: plain ints, unbounded, negative allowed. Every entity stores world coordinates.
- **Chunk key** `(cx, cy) = (x // 70, y // 40)` (floor division); **local** `(lx, ly) = (x % 70, y % 40)` (Python `%` is
  non-negative). Chunk arrays are `[lx, ly]`, shape `(70, 40)`, numpy order F, exactly like the old map arrays.
- **Window coordinates**: a stitched window covers the chunks `cx-r..cx+r`, `cy-r..cy+r` around the player's chunk
  (`r = GameConfig.near_radius`, default 1, so 210x120 tiles). Window origin `(ox, oy) = ((pcx-r)*70, (pcy-r)*40)`;
  window index `[x-ox, y-oy]`.
- **Screen**: the map viewport is the top-left 70x40 cells. Camera origin `(camx, camy) = (px-35, py-20)`, screen cell
  `(sx, sy)` <-> world `(camx+sx, camy+sy)`. For bounded test maps the camera is clamped to the map bounds (a map no
  larger than the viewport is drawn at (0, 0), as before). `Engine.mouse_location` holds **world** coordinates.
- Noise is sampled in world coordinates: `tcod.noise.grid(shape=(h, w), scale=s, offset=(y0, x0))` (verified: equals the
  matching slice of one big grid exactly; `offset` follows `shape` order (rows, cols) and is scaled by `scale`).

## Modules
- `chunks.py`: constants `CHUNK_W/CHUNK_H`, `chunk_key()`, `local()`, `Chunk` (terrain `tiles`, `explored`, `blocked`, the
  per-chunk entity index that `GameMap` had: `_by_pos`, categories, actors, render buckets; `terrain_version`;
  `generated_at` time).
- `world.py`: `World` (one floor): the `SpatialContainer` every map entity has as `parent`. Routes `add/remove/move_entity`
  and queries by world position to the owning chunk; owns the loaded-chunk dict, the `ViewWindow`, the chunk source and
  the in-memory store of unloaded chunks. `GameMap(engine, landscape)` = a **bounded** World made from a fixed landscape
  that fits chunk (0, 0) (tests, benchmark scenario); it keeps the old array properties (`tiles`, `explored`,
  `visible`, `width`, `height`) as live views. `GameWorld` stays the floor/time manager.
- `worldgen.py`: deterministic chunk generation (terrain + plants + spawns) from `(floor_seed, cx, cy)`; replaces
  `procgen.generate_noise` (spawn tables and helpers stay in `procgen.py`; dead `generate_map`/rooms code goes).
- `view.py`: `ViewWindow` (stitched arrays + FOV result) and `Camera`.
- `simulation.py`: tiers, per-turn scheduling, `upkeep()` (exact and analytic catch-up), simplified NEAR AI.
- `savegame.py`: directory save format (manifest + chunk files), persistent-id pickling, load.

## Entities and chunk membership
- An entity on the map has `parent = World`; the World indexes it in the chunk containing its position. `World.move_entity`
  re-indexes it in another chunk when it crosses a border: the same object moves between the chunks' sets (identity,
  hp, hunger, inventory, AI untouched). `uid` stays the identity key for saves.
- Plants never move (no code path moves them). Units and items move/are dropped like any entity.
- Entities can only be added to / move into **loaded** chunks. `in_bounds(x, y)` = "tile belongs to a loaded chunk"
  (and to the landscape for bounded maps), so `can_move` refuses steps into unloaded chunks; NEAR units therefore stay
  inside the loaded ring.
- Terrain edits (plants writing `walkable/transparent/dark` on their tile, stairs) go through `World.modify_tile()`,
  which writes the chunk array and bumps that chunk's `terrain_version`.

## Simulation tiers (all configurable in `GameConfig`)
- **ACTIVE** = the player's chunk (`active_radius`, default 0): full AI every turn, exactly the old per-turn behaviour.
- **NEAR** = chunks within `near_radius` (default 1, the 8 neighbours): every `near_interval` turns (default 2) each actor
  gets upkeep and one **simplified step**: hostile -> greedy step towards the player when within 15 tiles; passive ->
  greedy step away from a non-own-species unit within 3, eat adjacent food when hungry, otherwise a random step half of
  the time; plants only grow. No pathfinding, no messages. Enough for animals to walk onto the screen.
- **FAR** = everything else: **not loaded**. Chunks beyond `unload_radius` (default `near_radius + 1`; the band between
  is loaded but frozen = hysteresis so walking back and forth over a border does not thrash) are serialised
  (pickle + lzma) into an in-memory store and dropped; the same bytes are written at save time.
- **Catch-up is per entity**, not per chunk: every Unit/Plant stores `last_upkeep` (game time). `upkeep(entity, now)`
  applies every hunger/thirst/growth step in `(last_upkeep, now]` and sets `last_upkeep = now`. For one elapsed turn it
  calls the original per-turn code (so ACTIVE behaviour is unchanged); for more it is analytic: `k` hunger steps =
  multiples of 4 in the interval, thirst = multiples of 2, damage `max(0, k - max(h - 1, 0))` (exactly what `k` calls of
  `handle_hunger(-1)` do), death if hp hits 0 (quietly, no message); plants: growth steps = even times in the interval,
  `cycles` full cycles each add a branch + fruit while the inventory has room (the per-turn "drop onto a neighbour tile
  when full" is not modelled). Units entering from FAR are assumed to have **foraged** if their chunk has food: hunger and
  thirst are not taken below half their maximum (otherwise every animal left behind for ~400 turns would starve, which
  the full simulation does not do). Because it is per entity, a unit that crossed from a lagging NEAR chunk into the
  ACTIVE chunk is never charged twice. Reloaded chunks get `upkeep(..., now)` for all their entities at load time.
- `GameWorld.pass_time` (player turns only, as before) calls `simulation.run_turn(engine)`: ACTIVE actors every turn,
  NEAR chunks on their interval; it never iterates FAR or frozen entities. After the player moves, `World.update_tiers()`
  loads/generates/unloads chunks around the player's chunk.

## Stitched view window
- `ViewWindow` holds, for the window rectangle: `transparent`, `walkable` (copies stitched from the chunk arrays; unloaded
  chunks = opaque/unwalkable), the `visible` FOV result and window-sized scratch for pathfinding.
- **Invalidation**: the cache key is `(window origin, tuple((key, id(chunk), chunk.terrain_version) for the 9 chunks))`.
  It is rebuilt when the player's chunk changes, a chunk in it is loaded/unloaded, or a chunk's terrain changes.
  `blocked` (changes every move) is never cached: it is stitched on demand for the pathfinding crop.
- **FOV**: `compute_fov` on the window `transparent` (radius `fov_radius`, now default 41 = half-diagonal of the 70x40 view
  plus one); campfire light likewise; `explored |= visible` is written back into each chunk's `explored`.
- **Rendering**: terrain for the camera rectangle is assembled from the chunks' `light`/`dark` arrays with `visible` from
  the window and drawn with the Phase 3 batch; entities come from the (at most 4) chunks intersecting the camera, layer by
  layer across chunks, culled to the camera and to `visible`; clutter safeguard per tile as before.
- **Pathfinding**: `Engine.get_path_to` crops the window to `path_radius` (default 40) around the origin; destination
  outside the crop (or window) -> `[]`. Cost = walkable-or-unexplored, `+10 * blocked`, as before.

## Generation (deterministic per chunk)
- Seeds: `GameWorld.seed` (from `random`, so a seeded game is reproducible) -> `floor_seed = mix(seed, floor)` ->
  `chunk_seed = mix(floor_seed, cx, cy)` with `mix` = blake2b over the packed ints (stable across processes/platforms,
  negative coordinates fine).
- Noise: 4 tcod `Noise` generators (2 height, 2 vegetation, as before) seeded from `floor_seed`, kept on the World and
  rebuilt from the seed after loading.
- A chunk is generated on a **padded** 74x44 region (margin 2) so the neighbour-dependent steps (lake dilation, edge
  variations) see the same neighbours on both sides of a border; the 70x40 interior is kept. Everything random inside a
  chunk (variation "center" pick, tree map, tree/shrub choice, spawns, and the incidental `random` use in constructors:
  shades, names, mirroring) runs inside `seeded_rng(chunk_seed)`, which seeds the global `random`/`np.random` and
  restores their previous state afterwards. So regenerating a chunk gives identical terrain and identical entities
  (kinds, positions, stats, colours); only uids differ.
- Per floor (World): one tree species and one shrub species (as before), made from `floor_seed`.
- Spawns: per chunk, the old per-map rules (`max_monsters_by_floor`, `max_items_by_floor`, walkable + unblocked tiles).
- Player start: a deterministic walkable, unblocked tile in chunk (0, 0) (spiralling to other chunks if none).

## Persistence: whole chunks, not deltas
- **Decision: once a chunk has been generated it is persisted whole and never regenerated.** Deltas would need every
  mutation path (AI eating, plant growth, inventories, crafting, campfires, deaths) to emit replayable events and the
  delta replay to reproduce internal AI state; that is a large, fragile surface. Whole-chunk pickles reuse the Phase 2
  picklable entities, and a chunk is ~5-15 KiB lzma-compressed. Determinism is still required and tested, because chunks
  that were never generated are not stored at all and must come out the same whenever they are first generated.
- **Save = a directory** (default `savegame/`):
  - `manifest.lzma`: `{"version": 4, "floor", "time", "seed", "player" (pickled), "message_log", "loaded": [keys],
    "chunks": {key: filename}, "next_uid", "downstairs", "procedural": [species/fruit definitions]}`.
  - `floor<N>/chunk_<cx>_<cy>.<generation>.lzma`: `{"key", "tiles", "explored", "entities" (positions included)}`.
  - Atomicity: chunk files are written under a **new generation number** (temp file + `os.replace`), then the manifest is
    written the same way (the commit point), then files no longer referenced are deleted. A crash at any point leaves
    the previous manifest pointing at complete files. Unchanged chunk blobs are not rewritten.
  - Pickling uses `persistent_id`: the World, the Engine, the player and the floor's procedural definitions are written
    as references and re-bound on load, so a chunk file never drags the rest of the world in. References to entities of
    other chunks (not expected; AI targets are transient) are stored by uid and resolve to None if not loaded.
  - Loading reads the manifest, rebuilds the World from the seed, loads only the chunks in the loaded set (unvisited
    chunks are not needed; visited-but-far ones are read when the player comes back), places the player and applies
    catch-up. Older single-file saves (version <= 3) raise `IncompatibleSave`.

## Floors and stairs (open question, default taken)
- **Each floor is its own `World`** (own seed, own chunk grid). `TakeStairsAction` on the down staircase makes
  `GameWorld` create the next floor's World and moves the player there; the previous floor is discarded (there is no way
  back up; its files are deleted at the next save). The staircase is placed deterministically in chunk (0, 0) at a
  walkable tile 8-20 tiles from the start, and the `down_stairs` tile becomes walkable so it can be stood on (it was
  unreachable before: the noise map never placed stairs and the old room generator that did is dead code).

## UI
- The camera follows the player; mouse cells are converted to world coordinates; highlights, the area-target frame and
  cursor clamping use the camera. Side panel shows floor, position and chunk. Smooth pixel scrolling (nice-to-have,
  behind `GameConfig.smooth_scroll`) only if time allows.

## Tests and benchmark (acceptance)
- Walk the player across chunk borders in all four directions; terrain continuity at the border (deterministic base
  terrain + edge variations match a single large generation); an NPC crossing a border keeps identity and state; save/load
  mid-world round trip; far chunks unload and reload with catch-up applied; regenerating a chunk is identical.
- Benchmark: one turn with the NEAR ring populated (plus world generation and chunk load/unload costs).
