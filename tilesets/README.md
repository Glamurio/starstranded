# Sprite sheet

`src/urizen_white.png` is generated: `python scripts/build_tileset.py`.

- `urizen_source.png`: the official Urizen sheet (12 px art, 13 px grid, magenta separator columns). Drop an updated one in and re-run the script.
- `legacy/`: the 50x50 sheets the game used before the merge. Needed by the script to find the project's own sprites.
- `legacy_map.json`: where every old (column, row) lives now. The game code was migrated with it; nothing reads it at runtime.
- Columns 0-99 of the merged sheet are the official sprites in official order (sections of 25 columns joined, no grid, no separators, 2x scale).
  Columns 100-124 are the project's own sprites (cacti, mushrooms, Selenites, wall edges, ...). Cell (124, 49) is reserved blank.
- `docs/tileset/sheet_preview.png` shows the sheet with a coordinate ruler (every 5 columns/rows) for picking slots.

Things found in the official sheet while merging (all handled by the script):
- 38 faint, semi-transparent brown pixels form a box around one sprite and spill over a grid line. They are below the alpha cut-off and dropped.
- About 700 near-black pixels (r+g+b < 7) lie in sprite cells. They are treated as background, as they were on the old sheet.
- 94 neighbouring cell pairs continue a drawing across the cell edge (wide or tall art). With the grid gone they join seamlessly.
- 5 pairs of cells draw the same sprite twice; the first one is used.
- 5 of the project's own sprites are one or two pixels off a newer official sprite; the project's version is kept so nothing changes in game.
