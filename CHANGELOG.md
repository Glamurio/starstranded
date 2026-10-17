# Changelog

Behavior changes made by the modernization project (branch `modernize`). Pure refactors are not listed.

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
