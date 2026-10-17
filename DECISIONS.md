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
  the whole 70x40 map (88 µs), so cropping buys nothing at this map size (revisit for Phase 5's stitched window, where the
  cap is a hard requirement). Legacy `tcod.path.AStar` was 5x faster (17 µs) but returned a costlier route in 12 of 1,602
  random queries, so the exact `Pathfinder` stays. Paths are now *identical* to the old implementation (tested against a
  copy of it); per call 197 → 134 µs, the remainder being tcod's own search.
- FOV: `config.fov_radius`, default **80** = ceil(sqrt(69² + 39²)), i.e. the whole 70x40 map remains visible from anywhere
  (unchanged behaviour while the camera is fixed). Phase 5 (camera centred on the player) should lower it to ~41 (half-diagonal of the view).
- Render: iterate render buckets in order (no per-frame sort).
- Procgen: lake dilation via array shifts; `replace_variations` vectorised (neighbour masks → 16-case lookup); vegetation via
  `np.argwhere`. Old implementations kept in tests as reference to prove identical output.
- AI: only `actors` are iterated per turn; food search is a ring scan over the index; `flee` gets a bounded number of tries.
