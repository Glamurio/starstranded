# Decisions

## Repository / process decisions
- **Branch:** all work is on `modernize`, forked from `crafting` (the checked-out branch, e01d7a4).
- **Owner WIP:** `src/components/ai.py` had an uncommitted `PassiveAI` change (`seeking` reset: dropped `not self.seeking and`
  from the hunger check and added `self.seeking = False`). Per owner choice it is committed unchanged as the first commit on
  `modernize`. Behavior from here on includes it.
- **Line endings:** the repo stores LF; the owner's Windows checkout is CRLF. Commits from the dev VM use
  `git -c core.autocrlf=input` so blobs stay LF and diffs stay minimal. Edits to existing files preserve CRLF.
- **Commit identity:** `Pascal <p.kammer@satzweiss.com>` via `GIT_AUTHOR_*`/`GIT_COMMITTER_*` env vars (no git config changed).
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

## Needs owner decision
1. **Hunger/thirst semantics (Phase 1).** Proposed: starvation/dehydration costs **1 HP per tick for any unit**; the
   "is starving"/"severely dehydrated" messages only for the player (message fires on the tick it first reaches 0).
2. **Corpse vs living unit on one tile.** Proposed: lookups for "the unit at x,y" for combat/bump prefer a *living* unit; corpses
   remain visible/lootable; PassiveAI ignores corpses when choosing something to flee from. Changes behavior ⇒ your call.
3. **`Plant.die` / tile swap:** keep (dead plant → opaque, unwalkable roots) or let the tile become walkable/transparent again?
   Currently unreachable, so no gameplay impact until plants can be attacked.
4. **Stairs / floors:** `generate_noise` never creates stairs, so `L` only works standing on (0,0). Phase 5 default (each floor is its own
   World) stands unless you say otherwise; do you want stairs placed in the noise terrain at all?
5. **`requirements.txt` pins `tcod==20.1.0`** while `pyproject.toml` needs `>=21.0.0`. Proposed: update `requirements.txt` to match pyproject.
6. **Free actions:** pickup, mass pickup and equip/unequip take no game time. Intentional?
7. **`Selenite`, `Sword`, `ChainMail`, fireball/lightning/confusion consumables** are defined but never spawned. Keep as future content
   (default: keep, port them) or delete?
8. **`CharacterCreation.PLAYER`** is one player shared across menu round-trips (state leaks if you go New Game → Esc → New Game).
   Proposed: create a fresh player per New Game.
