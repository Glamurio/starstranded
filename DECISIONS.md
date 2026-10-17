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

## Phase 1 verification (verdict per listed item; filled in as fixed)
| # | Item | Verified against code? | Status |
|---|---|---|---|
| 1 | `handle_hunger/thirst` condition `not self.engine.player` | Yes: always False ⇒ **no starvation/dehydration damage and no message, for anyone** (`test_current_starvation_*`) | pending |
| 2 | `handle_health` clamps to `max_hunger` | Yes: HP can reach 100 with `max_hp` 30 (`test_current_handle_health_clamps_*`) | pending |
| 3 | Mutable defaults / class-level mutables | Yes. Defaults never mutated today (latent): `map_codepoints(variations=[])`, `Tile(variations=[])`, `MovementAction(path=[])`, `Fruit(factory={})`, `InventoryLootHandler(entities=[])`. **Shared class-level state that is live**: `InventoryEventHandler.buttons/inventory_entries`, `MainMenu.buttons/button_highlight`, `BaseAI.path`, and `CharacterCreation.PLAYER` (a Player built at import). | pending |
| 4 | `get_entities_at_location` annotation | Yes (returns `list`) | pending |
| 5 | `get_path_to` returns `None` out of bounds | Yes; `MainGameEventHandler.on_render` iterates the result (crashes if the cursor were out of bounds; cursor is clamped in practice) | pending |
| 6 | `AreaRangedAttackHandler.on_render` frame | Yes: `width=radius**2`, origin `x-radius-1` | pending |
| 7 | `matplotlib` import in `procgen` | Yes; also in pyproject deps | pending |
| 8 | `utilities.text_input` | Yes broken (`tcod.eventKeySym` does not exist in 21.2.1) **and unused** ⇒ delete | pending |
| 9 | `generate_name` re-parses cfgs per call | Yes. `tcod.namegen_*` still exists but only via the deprecated implicit `libtcodpy` alias (FutureWarning "Soon the 'tcod' module will no longer be an implicit reference to 'libtcodpy'"). Replace with cached pure-Python generator | pending |
| 10 | `map_codepoints` index scheme | Noted, **not fixed** (removed in Phase 3). Overflow only for sprites in rows ≥ 28 that also use mirror/corpse; variation index `1 + i + …` can collide with neighbouring sprite codepoints | n/a |
| 11 | Noise axes | Consistent **by luck of tcod's grid axis order**: `grid(shape=(h, w))` → array `(w, h)` in 21.2.1. Documented in ARCHITECTURE_NOTES; Phase 5 must be explicit | documented |
| 12 | `Plant.die` swaps in a blocking, opaque roots tile | Yes. Also **unreachable today** (plants cannot be attacked) | flagged, **not changed** |

### Additional defects found while reading (not in the brief)
| Item | Evidence | Plan |
|---|---|---|
| Level-up crashes: `Level.increase_max_hp/power/defense` touch `self.max_hp/hp/base_power/base_defense` on the Level component | `test_current_level_up_crashes` | fix in Phase 1 (separate commit): obviously intended to modify `self.parent` |
| Opening the inventory with a Health Potion crashes: `chr(entity.char)` with `char == "!"` | `test_current_inventory_render_crashes_with_a_health_potion` | The whole `char` mechanism is deleted in Phase 3; minimal Phase 1 fix so the game is playable meanwhile |
| `get_unit_at_location` can return a *corpse* when a living unit shares the tile (`units` includes dead units) ⇒ melee/bump can target the corpse | `test_current_get_unit_at_location_may_return_a_corpse` | gameplay semantics ⇒ **Needs owner decision** (proposal below) |
| `setup_game` does `from asyncio import exceptions` | `test_current_setup_game_uses_asyncio_exceptions_module` | fix (trivial) |
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
