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

# Phase 5 outcome (what was built; supersedes the plan where they differ)

The plan above was implemented as written, with these specifics and deviations:

| Topic | Outcome | Why |
|---|---|---|
| Tier radii | `GameConfig.active_radius` (0), `near_radius` (1), `unload_radius` (2), `near_interval` (2), `path_radius` (40), `fov_radius` 41. | All configurable as required; ACTIVE radius added so the player's neighbours can be made fully simulated without code changes. |
| NEAR movers | Cannot step into unloaded chunks (`in_bounds` is False there), so no separate frozen margin is needed for them; the hysteresis band between `near_radius` and `unload_radius` is loaded but frozen. | Simplest correct rule; a unit never ends up in a chunk that is not loaded. |
| Identity across unload | Crossing a border while loaded keeps the *same object*. After a chunk is unloaded and reloaded its entities are new objects with the same uid and state (pickled). | Objects cannot survive serialisation; `uid` is the stable identity (save, `World.find_uid`). |
| Catch-up rules | Units: exact hunger/thirst arithmetic for the gap; if the gap is longer than `2 * near_interval` and the chunk has food, hunger/thirst do not drop below half (foraging assumption), otherwise starvation damage applies and the unit can die (no message). Plants: growth cycles add branch + fruit while there is room; the per-turn "drop onto a neighbour when full" is not modelled. | Analytic and cheap; documented as approximations. |
| Wander / flee targets | Picked within 12 tiles (wander) / 2 x flee distance around the unit instead of anywhere on the 70x40 map. | There is no "whole map" any more; the old loops could also spin forever. |
| Window | Rebuilt on centre change, chunk load/unload or `terrain_version` change; keeps the FOV result for the overlap. `explored` and `blocked` are read live from the chunks. | `explored` changes every FOV update and `blocked` every move; caching them would only add invalidation work. |
| Bounded maps | `GameMap` is a single-chunk World (landscape must fit 70x40) with the old array views; used by tests, the screenshot script and the benchmark scenario. | Keeps the 290 earlier tests meaningful with minimal churn. |
| Saves | As planned (directory, generation-numbered chunk files, manifest as commit point, persistent ids). In-memory unloaded chunks are the same lzma bytes that are written. Default location `src/savegame/`; game over deletes it. | – |
| Stairs | Placed in chunk (0, 0) 8–20 tiles from the start and made walkable; the previous floor is dropped. | Default from the brief; the old stairs were unreachable. |
| Not done | Smooth pixel scrolling (`GameConfig.smooth_scroll` is reserved, the camera moves per tile); no performance pass (owner postponed it): border crossings cost ~40 ms (serialising leaving chunks), saving a large explored area ~100 ms; `g.py` was not reduced further (it only holds the handler stack, display and canvas, nothing was added). | Scope / owner instruction. |


## Performance pass 1

- **Persistent wander paths.** `BaseAI.wander` keeps `self.path` until it is walked or blocked (a blocked step clears it).
  Alternative: cache paths per (origin, destination); rejected, the stale-path risk is the same and the AI owns its path anyway.
- **Trip-sized path search.** `get_path_to` crops to `min(path_radius, 2*trip + PATH_MARGIN)`; a detour longer than that margin
  finds no path (the caller re-plans or wanders). Long trips are unchanged.
- **Hostile path reuse.** A chaser re-plans when its path is empty or the player is more than 2 tiles from where it ends.
- **zlib for chunks.** Unloading serialised chunks that are re-read within seconds; lzma cost 6 ms per chunk for a size nobody
  needs. Manifest stays lzma (tiny). Level 3 over 1: ~15% smaller for ~10% more time. `SAVE_VERSION = 5`.
- **Event-driven plants.** A plant does nothing between harvests, so `World.plant_queue` (heap of `(due, n, plant)`, lazily
  validated) wakes only the plants whose cycle completes. `upkeep` now also *is* the catch-up for plants, and replays every
  missed cycle through `Plant.complete_cycle` (including dropping surplus fruit on neighbours), so long absences are no longer
  an approximation for plants. Plants have no `ai` any more (`PlantAI` removed). They tick in all loaded chunks: the cost is
  proportional to harvests, not to plants.
- **Not done:** render caching (already 5 ms, drawn on change only), pre-generating chunks ahead of the player (border crossing
  is ~20 ms, below one frame at 60 FPS plus a turn).


## Demo leftovers removed
- Removed: HealthPotion/HealingConsumable, Sword, ChainMail, the three scrolls and their consumable classes,
  `ConfusedEnemy`, `entity_factories.py` (all commented out), `ItemKind.heal_amount/damage/radius/max_range/turns`, the
  `item_chances` entries. Kept: Selenite (owner), dagger/leather armor (the player's start kit), wooden spear and campfire
  (crafting), meat/fruit/branch.
- `item_chances` is now an empty table rather than deleted so loot can return without touching the generator;
  `get_entities_at_random` returns `[]` for an empty table. World generation therefore draws different random numbers
  than before (same seed, different monster layout), which nothing depends on.
- The area/single-target handlers are kept: generic UI with their own tests, and ranged weapons will want them.


## `g.py` replaced by `Session`
- **What:** `session.Session(display, canvas)` owns the window, the canvas and the handler stack; `layout.py` holds the cell
  constants. Engine handlers reach it through `engine.session`; the two engine-less handlers (`MainMenu`,
  `CharacterCreation`) take it as a constructor argument and pass it on.
- **Why on the Engine:** handlers, and items that open a placement screen (`Constructable.activate`), already have an engine and
  nothing else in common; the save code never pickles the engine (references only), so the session is not saved.
- **Alternative:** pass the session to every handler constructor (about 25 call sites and a lot of test churn for no gain), or keep
  a module-level "current session" (that is just `g` again).
- **Tests:** `conftest` makes engines built without a session share one headless window (`session.detached` is swapped; the
  default builds a window-less session), and `tests/ui_helpers.SESSION` is that window.


## Combat core: damage types and destructible plants
- **Model:** `damage.resolve(power, defense, type, resistances)`: flat defense first, then a per-type multiplier, min 1 if it gets
  through, 0 if immune. Resistances live on the species definitions (`resistances`, tuples so definitions stay hashable);
  armor only has flat defense for now. Alternative: separate armor values per type; deferred until there is more than leather.
- **Attacker type:** wielded weapon's `damage_type`, else the species' natural one (`Unit.damage_type`).
- **Plants:** tree 30 HP (blunt 0.2, sharp 1.0, pierce 0.3), shrub 8 HP (0.5/1.0/0.5). `MeleeAction` targets a unit, else a plant;
  `BumpAction` attacks a *blocking* plant only when a weapon is wielded, so walking into trees with bare hands is not an attack.
- **`Plant.die` fixed:** the old version (never reachable) swapped in an unwalkable roots tile. Now the plant is removed, the tile gets
  back the walkable/transparent/dark values it had before the plant shaped it (`Plant._ground`), and fruit + 2 branches drop.
- **Dying:** `handle_health` and the bulk starvation path use `is_alive` instead of "has an AI" (the player's dummy AI is no longer
  load-bearing for that).
- **Open:** no stump/log entity yet; no tool-power gating (e.g. a stone axe for hardwood); ranged attacks and elemental damage later.


## AI rework: one behaviour routine for every tier
- **Structure:** `behavior.act(unit, ai, cheap)` holds the decisions (flee > hostile hunt of the player > needs > idle). `CreatureAI`
  (`PassiveAI`/`HostileAI`, the latter `is_hostile`) calls it with `cheap=False`; `simulation.near_step` calls it with
  `cheap=True` (greedy steps instead of A*, no walking paths). The eating and attacking code is shared, so what happens off
  screen is what would happen on screen: that is the "if the player cannot tell the difference, simulate it" rule applied to AI.
- **Relations:** `Diet` on the species (herbivore / carnivore / omnivore). `preys_on(hunter, other)`: a living meat eater (carnivore
  or omnivore, so also the player) hunts a living herbivore. Flee = being preyed on by someone within 4 tiles, found via a cached
  list of the world's meat eaters (`behavior.hunters`, keyed by `World.entity_version`) instead of scanning rings.
- **Needs:** `is_hungry` = hunger or thirst <= 90 (`SEEK_THRESHOLD`, unchanged). Food is found ring by ring (radius = the creature's
  sight): ground food, corpses holding edible food, fruiting plants, prey. Eating is "loot, then consume next turn" in the full tier,
  immediate in the cheap one.
- **Hostile creatures** keep the old rule (chase when seen by the player, re-plan only if the player moved > 2 tiles from the path's
  end) and fall back to the needs routine when the player is out of sight.
- **Greedy movement** sidesteps on a plateau and takes a random step when boxed in; without that, NEAR-tier animals froze behind
  trees and starved (found by a 1200-turn soak: 21 of 31 rabbits died of thirst).
- **Ecology numbers:** Meat now gives 10 hunger + 15 thirst so a carnivore needs a kill about every 60-80 turns. Without drinking
  water this is a stopgap; real drinking needs a liquid flag in the tile data (not done).
- **Open:** Selenites spawn at weight 8 (~8 %); they are hostile and mostly chase the player, so they rarely hunt rabbits. A
  proper ecology (reproduction, herds, territories) is a design item of its own.
- **Perf note:** with 200 creatures a turn costs 15-35 ms in the full tier (path planning dominates); NEAR is ~5 ms.

## Lighting and visible map size
- **What:** visibility = ambient FOV (radius follows `daylight`: 4 at night, 41 at noon) OR (tiles lit by light sources AND in the
  player's FOV up to `fov_radius` 42). Light sources are any entity with `light_radius > 0` and `emits_light` (new `Entity` API,
  indexed per chunk in `Chunk.lights`; a campfire emits only when lit and placed). `World.has_sky` (floor <= 1) decides whether
  the sun counts. Night is drawn as a dark tint over seen-but-unlit tiles.
- **Why:** the old code special-cased `Campfire` inside `Engine.update_fov`; lighting is now a generic mechanism in `lighting.py`
  that torches, glowing creatures or lava can reuse, and it keeps the FOV cost at one shadowcast per source in the window.
- **Alternative:** a per-tile light-level map with falloff (smoother, but costs a float array per window and needs recomputing
  when anything moves); deferred until there is more than one light colour or strength.
- **Visible map size:** fixed at one 70x40 view (like Caves of Qud's single 80x25 zone screen: the world is bigger than what is
  shown, the window only scales it). Chosen so the sprite grid stays crisp and gameplay does not depend on monitor size; the
  alternative, a window-dependent view, would make the visible area (and so difficulty) vary per player.

## Layered world (z-levels) and real stairs — design
- **What:** the world is a stack of layers keyed by `z` (0 = surface, < 0 caves, > 0 upper floors of buildings), all sharing
  one (x, y) grid. Each layer is its own `World` (own chunk grid, own `ChunkSource`) held by `GameWorld.layers`; the player is on
  one of them (`engine.game_map`). Only that layer is simulated; leaving a layer stores all its chunks (like far chunks), and
  returning replays elapsed time through the existing `upkeep` catch-up (creatures) and the plant queue (plants).
- **Stairs are deterministic "links":** `shafts.links(master_seed, chunk_key)` is a pure function giving the stair points
  `(x, y, z)` that connect layer `z` and `z+1` in a chunk. Layer `z` puts `stairs_up` there, layer `z+1` `stairs_down`, so any
  layer can be generated independently, in any order, and unloaded/reloaded without cross-layer bookkeeping. Surface chunks may
  have a cave shaft (1-3 floors deep) or a building (1-3 floors up); the start chunk always has a cave entrance 8-20 tiles from
  the spawn. A shaft's stairs are 4 tiles apart per floor, so a floor can have both an up and a down staircase.
- **Terrain:** caves (z < 0) are noise-thresholded open space with 3x3 rooms and a corridor to the chunk centre carved at every
  stair so a staircase is never walled in; buildings are walled rectangles with a door, whose upper floors are walled rooms
  surrounded by `open_air`.
- **Tile flags:** `tile_dt` gains `open` (no floor here: you see the layer below through it; not walkable) and `stairs`
  (+1 up, -1 down, 0 none). Stairs are found by flag, not by comparing sprites.
- **Seeing down (Dwarf-Fortress style):** a visible `open` tile draws the layer below's terrain at that position, dimmed. The
  lower layer's terrain comes from its resident chunk, its stored chunk (terrain is the cheap outer part of the chunk blob), or
  the pure generator, so nothing has to be loaded or simulated for it.
- **Player building:** a placeable *wooden floor* turns an `open` tile (or any floor-less tile) into a walkable built floor.
- **Alternatives:** (1) one 3D chunk array — rejected: every system (FOV, pathfinding, chunk index, saves) is 2D and tuned; layers
  reuse all of it unchanged. (2) simulating adjacent layers too — rejected for now (cost); a creature on another layer is
  "frozen then caught up", the same approximation already used for far chunks. (3) falling when walking onto `open` tiles —
  deferred; `open` tiles are simply not walkable.
- **Saves:** version 6, one directory per layer (`z<N>/`); old saves are rejected (no migration needed, per the brief).

## Simulated radius 2
- **What:** new `GameConfig.sim_radius` (default 2) is the NEAR tier; `near_radius` (1) now only sizes the view window; `unload_radius`
  default 3. `load_radius = max(near_radius, sim_radius)`.
- **Why:** "if the player can't tell the difference, simulate it": the screen shows 70x40 tiles, so one chunk of margin was
  already invisible, but creatures two chunks away are what you meet after walking for a minute. Cost measured in BENCHMARKS.md.
- **Alternative:** simulate stored chunks abstractly (population dynamics) — rejected: the catch-up in `upkeep` already
  covers hunger/growth, and a second ecology model would need to agree with the real one. Layers you are not on stay frozen
  and catch up (same approximation as far chunks).

## Flask, boiling and poison
- **What:** `Flask` item (sips, liquid kind, boiled flag), `UseFlaskAction` (boil if next to a lit campfire, else drink, else fill),
  `Unit.poison` (turns of 1 damage, capped at 60, ticks in `pass_time` and in the catch-up `upkeep`), creatures drink impure liquid
  when thirst is the lowest need (`behavior._drink`).
- **Why:** the brief: drinkable only after boiling, toxic stays toxic, acid eats the flask, kind is learned by risk. The flask never
  names its contents so tests (science gear) can come later without changing the item.
- **Alternative:** a boolean "safe" flag on tiles — rejected: three kinds are needed for the later science gear. Making animals
  immune to impure liquid vs. sickening them — chose immune/avoiding toxic, so ecology stays stable.

## Creature movement across chunks and layers
- **What:** `HOSTILE_SIGHT` 45 / `HOSTILE_CLOSE` 15 in `behavior`; a stuck greedy hunter (two steps without progress) plans with A*;
  `GameWorld.arrivals` queues followers (due = turns equal to their distance), flushed on layer change and before saving;
  `GameWorld.send` moves an idle creature standing on stairs (`STAIRS_CHANCE` 4 %/turn) to the next layer.
- **Why:** hunting must not stop at a chunk border and stairs must not be a safe haven; the cheap tier stays pathfinding-free except
  when stuck, so benchmarks are unchanged (BENCHMARKS.md).
- **Alternatives:** simulate every layer near the player (cost, rejected: frozen-then-caught-up stays the model); followers
  appearing instantly (rejected: you get a head start equal to their distance); persisting the arrivals queue in saves
  (rejected: flushing it before saving is simpler and invisible).
- **Single-player view:** nothing lets you look at or target another layer; I read the request as exactly that, so the
  look-down through open air (terrain only) is the sole exception, as before.

## Liquid colours: exactly two
- **What:** shallow `(92,150,186)` and deep `(58,104,148)` for every liquid tile; depths 2 and 3 share the deep colour.
- **Why:** per-lake hue noise plus three brightness steps produced a gradient and harsh bright/dark edges; the brief was two colours.
- **Alternative:** a per-lake hue — dropped: a pure per-chunk generator cannot tell where a lake ends, so hues seamed.

## Merged sprite sheet
- **What:** `scripts/build_tileset.py` builds `src/urizen_white.png` (125x50 cells of 24 px, white on alpha) from the official sheet
  (columns in official order) plus 48 legacy sprites that are not in it, copied at full resolution into columns 100-124. Sprite
  coordinates in `species.py`, `tile_types.py`, `names.py` were rewritten to the new positions (`tilesets/legacy_map.json`).
- **Why:** a real merge keeps the sheet in the official layout so a future Urizen update drops in; an old sprite is only copied
  when it is not pixel-identical to an official one, so nothing changes in game. `tests/test_tileset_migration.py` hashes 92
  sprite references against hashes recorded on the old sheet.
- **Alternatives:** keep the old 50x50 layout and append the new sheet (no coordinate changes, but two copies of everything);
  a runtime legacy-to-new coordinate table (hidden indirection); a slot picker that reads the gridded sheet directly (the build
  step makes the grid disappear instead). Official art that is 1-2 pixels different from your version was not adopted.

## Render key width and save version after the sheet merge
- **What:** `world.SPRITE_BITS` 14 (was a hard-coded 12) with an import-time assert against `atlas.COLUMNS * atlas.ROWS`; `SAVE_VERSION` 7.
- **Why:** the merged sheet has 6250 cells; ids above 4095 wrapped in the packed terrain key and drew the wrong sprite (lake edges as
  figures). Chunk blobs hold sprite ids, so pre-merge saves would draw wrong sprites too.
- **Alternative:** migrate old saves with `legacy_map.json` — not done: procedural fruit and plant definitions inside the pickles also
  carry old coordinates; the project already accepts rejecting old saves.

## Gameplay core: items made of materials, property-based recipes (branch `gameplay-core`)
- **What:** every gathered thing is a `Stuff` (one piece of one planet `Material`); crafted things are `Composite`s (`Gear`, `Made`,
  `Placed`, built floors/stairs/walls) that remember which material filled which role and derive their properties from them with the
  recipe's rules (`materials.derive_properties`). Recipes (`recipes.py`) are lists of `Need`s (role, accepted forms, property
  thresholds on the 0-10 scale) plus tool/station tags, skill, heat and time; `crafting.check` reports each requirement as met or
  not, `crafting.craft` consumes exactly the pieces it picked. All pieces of one role are one material (no mixing).
- **Why:** the old recipes were fixed ingredient counts of an object type; the same hatchet whatever you made it from. Thresholds
  and derivation make material choice matter and let planets with different materials still be playable.
- **Race efficiency** (`craft_cost`, Human) trims counts above 1 by the stat, never below one piece per role, never touching thresholds.
- **Refining** is a recipe at a placed furnace that burns fuel pieces from the pack: furnace temperature = 450 + 125 x the best fuel's
  combustibility (wood ~1200 C, coal ~1575 C). Smelting needs the metal's melting point, glass the sand's. Ignition of a fire uses
  `materials.ignite` with a 450 C spark from a hard stone (hardness >= 7): fuel that cannot ignite or only flashes is reported.
- **Acquisition paths:** `acquisition.reachable(planet)` plays the tree forward from what the planet gives; a test requires every
  recipe to be reachable on 8 sample planets. Skills are ignored there on purpose (earned by `Unit.practice`).
- **Mining:** rock faces yield the deposit of their 5x5 cell (`resources.wall_material`: stone of the biome, ore veins, coal, crystal,
  radioactive ore in caves), a pickaxe head must be harder than the rock (`mine_difficulty`). Loose stones are scattered entities
  (so they persist like any item); sand and clay are dug from shores and the right biomes.
- **Material damage:** `actions.material_damage` multiplies a hit by `materials.attack_factor` against the target's material
  (plants' wood, built walls); creatures use their plain numbers.
- **Limitations:** sprites for new items reuse the nearest existing art (stone, ore, pieces share icons, furnace/workbench are
  placeholders) - tinted by material colour; held torches do not light the carrier (torches are placed).

## Survival-game layer: people, sponsors, crash site, escape, survival, lore (branch `gameplay-core`)
- **Capabilities, not flags.** Races, backgrounds and sponsor perks are `Grant`s of tagged capabilities (`capabilities.py`: capability,
  modifier, restriction, trait; stats such as `breath_turns`, `scan_depth`). Gameplay asks `caps.has(tag)` / `caps.stat(name)`. Tool and
  station tags are derived from what is carried or nearby. Alternative (per-race `if` branches) rejected: three races x nine backgrounds.
- **Races** (`species.py`, lore in `characters.py`): Human (less crafting waste, omnivore, slowed in the dark), Selenite (crops, breath x3,
  herbivore, brittle shell: blunt x1.5), Mau (agility 2.0, darkvision, claws, carnivore, will not wade into liquid). Diet and liquid
  rules apply to the player as well as creatures (review defect #2).
- **Backgrounds**: the six asked for plus Survivalist, Pilot and Archaeologist, each justified by an escape route (fire/shelter, ship
  repair needs a pilot, ruins need linguistics/digging). Kits are built from standard-issue materials with the same item classes crafting
  produces, so a corporate knife is just a knife made of better stuff.
- **Sponsors** (`sponsors.py`, `factions.py`): value = base x sponsor premium x quality x saturation (0.9^n, floor 0.3). Factions carry
  stance, trade link and a hawk/dove division; earning reputation spills over to allies/rivals, and every fifth native kill moves each
  board by its leaning. Reputation is clamped to +-100. A kill pays at most one bounty (`run.hunt_claimed`).
- **Run state** (`run.py`) is plain data inside the save (SAVE_VERSION 8): mode, seed, sponsor, credits, reputation, contracts, knowledge,
  flags. No live objects. Old saves are refused, as before.
- **Escape routes** (`structures.py`, `endings.py`): repair (4 hull plates, nav unit, power cell, a pilot), corporate rescue (reputation
  >= 40 and >= 2 finished contracts, build a beacon, survive 60 turns), ancient gate (3 keys + 3 inscriptions read in full). Eight
  endings. Keys are not for sale; each ruin also yields a sellable curio. Glyph study teaches once per 60 turns (no grinding at the stone).
- **Survival** (`survival.py`): effective temperature = ambient + insulation x 1.5 + fire + shelter + bed; cold counter costs HP, heat
  drains thirst; gas pockets below z=-2 use `breath_turns`. Costs 0.02 ms/turn (measured); the ~20-35 ms/turn is the pre-existing creature
  simulation (`find_liquid`), not touched.
- **Modes**: Roguelike = permadeath; the active save is deleted on death only if this run was loaded from it, and a finished run is never
  written by the exit save. Casual = sleeping in a bed writes `savegame_bed`; death offers `R` to wake there; Continue falls back to the
  bed save; a new run clears any stale bed save. One save slot: starting New Game and quitting overwrites it (documented, not warned).
- **Lore** (`lore.py`, `knowledge.py`): facts have a difficulty and a skill domain; scanning reveals none/partial/full from scanner tier 1 +
  skill + capability. Materials and creatures keep provisional names until learned (scan or craft). Scanning costs a turn, range 8, line of sight.
- **UI**: main menu New Game / Continue / Settings / Exit; settings (3 volumes, fullscreen) persisted to `settings.json`; stepped character
  creation (name, people, background, sponsor, mode, confirm) with lore and strengths/weaknesses; side panel shows temperature, breath,
  rescue countdown, credits; screens for pod, codex (O), navigation (M), help (H).
- **Audio**: the game has no sound assets, so volumes are saved and applied to pygame's mixer when it is running; nothing audible yet.
- **Review**: an independent reviewer agent scored the first pass 5-9 per category and found 11 defects (H/M crash, player diet, save leaks,
  sleeping death, key sale, hunt double pay, study grind, pod value, ...); all were fixed with regression tests in `tests/test_review_fixes.py`.

## Sprite config and debug sprite editor
- **What:** which sheet cell a thing uses lives in `src/data/sprites.json` (overrides only; `{}` = all defaults). `spriteconfig.py` reads it; `species.register`, `tile_types`, and the planet flora/fauna builders ask `spriteconfig.get(key, default)`, which also records the default. A "Sprite editor" button on the main menu (`sprite_editor.py`) lists every key (133 today), shows the sheet at 1:1, and a click assigns that cell and saves at once; Ctrl+R resets a key.
- **Why:** sprite coordinates were scattered over code; the artist/designer needs to retarget them without touching Python.
- **Alternative:** a full JSON of every sprite (generated by a dump tool). Rejected: it would duplicate the code defaults and drift. Overrides-only keeps the code as the source of truth and the file tiny.
- **Limits:** items/units/tiles update live; generated flora/fauna and already-generated terrain take the change on the next new world. Structures keep their sprites in code for now.

## Keypress playthrough as a test
- **What:** `tests/test_campfire_playthrough.py` plays from the main menu with `KeyDown`/`MouseMotion`/`TextInput` events through
  `main.process` + `main.render`: fell a tree with the wielded knife, pick up branches (G + letter), craft a campfire (R), place it
  (I, cursor, Enter), light it (F). Runs on three seeds (about 3 s each).
- **Why:** unit tests call actions directly and miss UI flow bugs. This one found that targeting screens stayed open after use.
- **Limits:** the bot reads the map for positions (what a player sees on screen); it relies on the starting knife and ferro rod, so
  finding flint is not exercised.

## Feedback round of 19 Oct 2026 (items 1-17)
- **Removed vs kept:** the ferro rod, `wooden_spear`, `selenite_people` and the `selenite_people` corpse are gone. `hide_armor` and `wooden_stairs` stay: recipes, the starting kit and `BuiltStairs` depend on them. Alternative: rewrite those recipes; rejected as out of scope for a removal request.
- **Selenite names** are built only from the syllables in `voyage_selenite.cfg` (Start+Middle+End, seeded per concept, no triple letters). Alternative: hand-written words; rejected, the cfg is the single source of truth.
- **Animal coverings** (fur / feathers / chitin / scales / skin) are a `covering` field on the species; each has its own piece, material noun and recipe head. Scale and chitin animals used to roll "hard" because the hardness baseline was hide; `FAMILY_TYPICAL` now has per-covering baselines.
- **Blood** is a `Decal` entity on its own bottom render layer (one per tile), coloured by `blood_color` on the species (red default). Decals never appear in tooltips, loot lists or pickup.
- **HUD**: the log and status moved to an engraved right panel (22 cells); the map view is now 58x45 cells. Bars are 10 segments. Themes are palettes in `ui.PALETTES` (default "ion"), chosen in Settings.
- **Ground cover** (grass, leaves, ferns, mushrooms) is terrain graphics, not entities, and uses a coordinate hash (`TerrainNoise.scatter`) so chunk seams stay invisible; the global RNG caused visible seams. Lily pads are procedural decals. Flowers are real named plants holding a bloom, so they can feed medicine and cooking later.
- **Test speed:** tests load 3x3 chunks instead of 5x5 (marker `full_world` opts out), the glyph-study test stubs the world simulation, and the UI fuzz test runs two seeds x 300 steps by default (`FUZZ_FULL=1` for 4 x 600). Whole suite: about 155 s -> about 55 s. Alternative: pytest-xdist; not used because the VM has two cores and it adds a dependency.
- **Plant cycles** no longer build items when the inventory is full (`Inventory.add` discarded them anyway).

## Defect fixes after the review of 19 Oct 2026
- **Steps and walks:** `MovementAction.perform` repeats only while path steps remain (it used to repeat after every step, the repeat raised "That way is blocked.", and `handle_action` then returned False). `handle_action` stops repeating when the player dies or the run ends, and `handle_events` runs the game-over/ending checks even after a failed action. Alternative: have the repeat loop swallow the final Impossible; rejected, it would hide real blocked steps.
- **Corpses keep their parts:** `Inventory.add(..., force=True)` skips the capacity check; `Unit.die` uses it. A full player pack used to abort the death half-way. Side effect: full non-player inventories no longer lose their meat silently.
- **Needs per minute:** `GameWorld.pass_time` advances the clock one minute at a time and pays hunger (every 4th), thirst (every 2nd), poison and the survival tick each minute, stopping if the player dies. Crafting, mining and the medkit now cost real hunger and thirst, so survival is a little harder than before; no balance pass has been made. Creatures still take one simulation turn per action (unchanged).
- **Eating takes a turn** (`EatAction`): it is checked for digestibility before time passes. Alternative: leave it free as a deliberate rule; rejected, eating mid-fight for nothing is an exploit.
- **Contract board** refills to three open contracts after each delivery (it counted the finished one).
- **Ore into a full pack** lands on the player's tile, as the message says. **Acid** messages use `get_title()` (wild creatures have no `name`).
- **Shared definitions:** `savegame._definitions` lists the planet's definitions first on every layer, so cave and sky chunks reference the planet's species instead of copying them. Surface blobs are unchanged and old chunk blobs still load, so `SAVE_VERSION` stays 8.

## World exploration round, stage 1-2: audit and God Mode (19 Oct 2026)
- **Audit findings that shape the plan:** terrain is one height noise cut into water / floor / wall (`worldgen.base_terrain`), so rivers, beaches, marshes and real mountains are new work, not a tweak. The biome table has three special overlays (volcanic, crystalline, fungal) that the landmark system replaces. The game plays no music at all yet (only volume settings exist). The code uses no bridge, road, vehicle, pillar or farm sprite yet; they have to be found on the sprite sheet. The world is one global tile grid (chunks 70x40 partition it, tiles are never shared or duplicated) and the view stitches chunks, so there is no per-chunk map to make seamless.
- **Chunk borders:** the proposed one-tile shared border (chunks shrunk by one tile each side) is not implemented: tile coordinates are already unique and global, terrain is generated on a padded region so chunk edges agree by construction, and shrinking the chunk would change every world coordinate and break saves for no gain. Seam consistency gets tests instead (stage 8).
- **God Mode** lives in `debug.py` and is only reachable in a debug run (`--debug` or `STARSTRANDED_DEBUG=1`), never in a normal game and never saved. It ignores damage, hunger, thirst, poison, cold and acid, walks through walls, water and entities (straight-line click walks), and has Ctrl/Alt jumps of 10 tiles / one chunk. Alternative: a normal in-game cheat key; rejected, cheats should not be one keypress away in ordinary play.

## Stage 3: landmarks (19 Oct 2026)
- **Landmarks are a layer above the biome, not biomes** (`src/landmarks.py`). The old volcanic / crystalline / fungal "special biomes" and their region noise are gone; `biomes.classify` is now climate only (plus the wetland overlay). A landmark has its own noise (one generator each, indexes 8 and up), a `Habitat` for the climate it may form in, a ground colour, its own ground cover, a vegetation multiplier, a temperature bonus, extra stones and a music key. Adding one is one `_landmark(...)` line. Alternative: keep them as biomes; rejected, a biome is climate, and a mushroom forest can stand in several climates.
- **How a tile gets a landmark:** soft-thresholded noise x climate suitability; the strongest landmark wins, so they never overlap; the strength (0..1) blends ground colour, vegetation density and the share of tiles using the landmark's cover, so edges are gradual. Landmarks judge the climate on temperature, moisture and the *smooth* relief only (the rough elevation and the per-biome fertility step would speckle the edges). Nothing is saved: the field is a pure function of the seed, so chunks agree.
- **Landing site stays clear:** landmarks fade out within 60 tiles of the spawn and reach full strength at 160.
- **Tree vs foliage rule:** ground cover is never drawn on a tile that holds a tree (`generate_terrain` passes `open_ground & ~tree_map`). To make that independent of how the world is cut into chunks, the tree roll now uses the coordinate hash (`TerrainNoise.scatter`) instead of the global RNG, so tree layouts differ from before for the same seed. Flowers (entities) are exempt, as specified.
- **Fixed tests that depended on luck of the layout:** the sleep test removes wandering creatures (one walked up and bit the sleeper), the campfire bot chases flint only (its pack filled with non-sparking stones).
- **Not yet done in this stage:** beaches and ruins landmarks (they need the hydrology and structure work), and a lava liquid for volcanic mountains (stage 6). Landmark species come in stage 4 (`fungal_tree` is already bound to the mushroom forest via `Habitat.landmarks`).

## Stage 4: landmark flora and fauna (19 Oct 2026)
- **Exclusive species** are templates whose `Habitat.landmarks` names the landmark (`planet.py`): seven plants (spore bush, barrel cactus, shard bush, ash shrub, dead tree, meadow bloom, crystal bloom) and seven animals (sporehopper, dune burrower, shardback, ember beetle, carrion hound, meadow grazer, bloom flitter), plus `fungal_tree`, now bound to the mushroom forest. Their suitability is multiplied by the landmark's strength, so they thin out towards the edge. **Shared species** are everything else: they follow only the climate, so a conifer still grows in a mushroom forest where the climate suits it. Alternative: a separate per-landmark species list; rejected, one habitat rule keeps spawning code unchanged.
- **Sprites are reused** (no new art): the new species borrow existing cells (bush, thorns, acacia, flower, hopper, scuttler ...) and get their look from colour ranges. Dedicated sprites can replace them through `data/sprites.json` later.
- **Tree / foliage rule:** trees and shrubs stand only on the tree map, and ground cover is never drawn there (stage 3); flowers are entities placed on free tiles without any other entity, so they never stand under a tree either. Tests check the generated chunks of three landmarks.
- Layout-dependent tests (sleep tests) now clear wanderers first.

## Stage 5a: relief (19 Oct 2026)
- **New large-scale relief** (`src/relief.py`) replaces "one height noise cut into water / floor / wall" (the old terrain was 93% floor, 5% water, 2% scattered walls). A continent noise gives seas, bays, peninsulas and (where a hilly coast dips) archipelagos; a ridge-contour noise gated by a zone noise gives mountain ranges with foothills, crests and passes; the old height noise stays as local roughness (stronger on mountains). Water stands where the *smooth* height is below sea level (`basin_height`), so shores are lines, not a spray of wet tiles; rock is `elevation > ROCK_LEVEL` plus the old odd outcrop, so there is stone to mine on any plain. Alternative: keep the old terrain and paint rivers on it; rejected, it has no relief for water to flow over.
- **The landing site is chosen, not forced.** Forcing land at the spawn left a visible round coast, so each seed instead reads the noise from a shifted origin (`relief.find_shift`, cached per seed): the shift is the first of up to 120 candidates that puts the landing chunk well inside a continent, clear of ranges and in a mild climate (temperature and moisture shift with it). A small pond 75-105 tiles from the spawn is always cut in, so the first days are not a hunt for water. The temperature falls with the smooth height above the snowline, so crests are cold and carry glacial ground.
- **Landmarks fade out at the coast** and are never at sea.
- **Test changes:** the seam test's "mostly the same" bound is 0.3 (seas and mountains are random-sprite 'surrounded' tiles), the shallow-colour gradient bound is 5 colours (fewer shores near the spawn).
- Tool: `tools/render_map.py SEED OUT.png` paints a 1200x700 map (1 px per tile) of the generated world for a look at continents, ranges and landmarks.

## Stage 5b: rivers, wetlands, beaches (19 Oct 2026)
- **Rivers are traced, not painted** (`src/hydrology.py`). A chunk cannot see the whole land, so each 120x120-tile cell may hold one source (hash of the seed and cell) on high, not-bone-dry ground; from it the river steps over a 6-tile node lattice to the lowest neighbouring node of `relief.drainage` (a smooth height with no local detail, so its only basins are real ones) until it reaches the sea or a pit. Because nodes sit on a shared lattice, rivers that meet *merge* and share everything downstream; flow (the number of sources through a node, plus one tributary's worth per 12 nodes of course) sets the width: a trickle you can wade, a river you cannot, with a ford every few nodes (width capped at 2). Sources are springs, or thaw where the air is cold at that height. A river reaching the sea runs on a few nodes and opens into an estuary; one that finds a pit, or outlives 80 nodes, ends in a lake, so no river just stops. A river passing within 70 tiles of the landing site is dropped whole. Alternative: carve rivers from a ridged noise; rejected, it has no sources, direction or ends.
- **Rivers are water tiles of the ordinary kind** (`kinds == 0` after the sea and lakes are made), so liquids, depth, shores and pathfinding work unchanged; they cross rock as canyons. The liquid kind of a river still follows the lake-kind noise at each tile.
- **Wetlands:** low ground within 6 tiles of any water gets extra moisture (fading with distance), so the biome table's swamp and bog overlay takes river banks, shores and estuaries. The generation margin grows from 4 to 8 tiles so chunk seams stay invisible. Landmarks read the climate's own moisture, not the damp.
- **Beach** is a landmark (`coastal`: on land only, not faded towards the sea) judged on a smooth shore proximity (`env["shore"]`), with its own palm, grass, crab and sea bird. Beaches also line lakes and river mouths in warm climates.
- **Landmark vegetation floor:** a landmark can set a minimum plant density (mushroom forests and decayed woods are wooded even on poor soil); the multiplier alone left desert-based ones nearly empty.
- Still to do in this stage: hot springs, fjords. Deltas are estuaries only (no branching distributaries); deferred.

## Stage 5c: hot springs and fjords (19 Oct 2026)
- **Hot springs** are a new liquid kind `HOT` (`liquids.py`): small irregular pools in deep volcanic country (one candidate per 36x36 tiles, kept where the volcanic landmark is strong), a paler green-blue. Wading scalds for 1 damage a step; drinking is treated like impure liquid (boil first); the codex lists it. Alternative: a purely cosmetic pool; rejected, a hot spring that does nothing is not a feature. Warmth near a spring is not modelled (the volcanic landmark already runs hot).
- **Fjords** are flooded river valleys: when a river reaches the sea through a range, its last stretch (3-14 nodes, while the range is still under it and the land is within 1.3 of sea level) is drowned 8.5 tiles wide, cutting a canyon with mountain walls. First attempt: contours of a channel noise gated to coasts near ranges; it left isolated arcs of water inland (nothing guarantees a contour connects to the sea), so it was dropped. Fjords are rare (one or two per 2000x1200 tiles on some seeds).
- Peninsulas, bays and archipelagos are not features of their own: they come from the continent shape and the coast detail (stage 5a). **Deltas** are estuaries only. Both are limitations, listed in the final report.
