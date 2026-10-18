# Starstranded master plan (branch `gameplay-core`)

Status legend: **done** = implemented, wired into the game and tested; **partial** = works but incomplete; **planned**;
**limitation** = known gap. This file is updated at the end of every milestone.

## Audit (M1) — what the repository was at the start
- pygame-ce app, tcod only for FOV/pathfinding/noise. Entry `src/main.py`; handler stack (`input_handlers.py`, `setup_game.py`);
  endless chunked layered world (`world.py`, `worldgen.py`, `shafts.py`); tiered simulation; versioned atomic saves; 405 tests green.
- Content is frozen dataclasses registered in `species.py` (`ItemKind`, `UnitSpecies`, `PlantSpecies`). One tree + one shrub species
  per floor, terrain = height noise (water / floor / wall), hidden liquid kinds, day/night + light sources, flask/boiling/poison.
- **Missing** (everything the master prompt asks for beyond the base): materials, tags/capabilities, races, backgrounds, sponsors,
  factions, biomes/ecosystems, scanner/knowledge, property-based crafting, material damage, crash site, escape routes, game modes,
  main-menu Settings. Character creation only asks for a name; the player is always a plain `HUMAN`.
- Placeholders vs finished: `voyage_selenite.cfg` is a finished syllable name set (Selenite personal names); `ryou_tree.cfg` is a
  joke/demo set (Despair-wood etc.) and is **not** used by the new naming; the other `jice_*`/`mingos_*` sets are generic fantasy
  libraries (kept, used for places/ruins where they fit). `components/names.py` colour/shape vocab is reused by the new namer.
- TCOD leftovers: only FOV / pathfinding / noise (intended). No rendering use remains.
- Existing hostile NPC `Selenite` (demo creature) is kept; in lore it becomes a *Selenite exile*, distinct from the playable race.

## Cross-cutting decisions (also in DECISIONS.md)
1. **World topology**: keep the existing endless deterministic chunked world. A finite circumnavigable planet would throw away the
   chunk/layer/save work that already passes 400 tests and gains little the crash-site-centred loop needs.
2. **Content format**: frozen dataclasses registered in Python modules (same as `species.py`), validated by `validate_content()`
   and a test. No new dependencies, no JSON loader to keep in sync with enums.
3. **One rule, one place**: tags/modifiers -> `capabilities.py`; material maths -> `materials.py`; damage -> `damage.py`;
   knowledge -> `knowledge.py`; recipes -> `crafting.py`; naming -> `naming.py`.
4. **Property scale**: continuous material properties are 1.0-10.0 floats (1 = negligible, 10 = extreme).

## Milestones
| # | Milestone | Status |
|---|---|---|
| M1 | Audit, plan, branch | done |
| M2 | Core data: tags, capabilities, modifiers, attributes/skills, knowledge model | planned |
| M3 | Materials, thermal, composition, property recipes, construction, damage | planned |
| M4 | World: climate fields, biomes, species suitability, crash site | planned |
| M5 | Races, backgrounds, sponsors, factions; character creation | planned |
| M6 | Scanner and procedural naming | planned |
| M7 | UI: main menu + settings, creation, scanner, codex, crafting requirements, contracts | planned |
| M8 | Escape routes, endings, game modes, death/save rules | planned |
| M9 | Integration, independent review, final report | planned |

## Known limitations (kept current)
- none recorded yet beyond the audit.
