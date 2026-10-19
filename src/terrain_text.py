"""Short descriptive names for the terrain layer, for the hover line: a tile that is plainly made by someone (path, flooring,
bridge, opening) is named; ordinary ground stays unnamed so the line is not noise."""
from __future__ import annotations

from typing import Dict, Optional, Tuple

import tile_types

_LABELS: Dict[Tuple[int, Tuple[int, int, int]], str] = {}


def _register() -> None:
    names = {
        "built_floor": "Wooden flooring", "bridge": "Bridge", "bridge_vertical": "Bridge", "path": "Trodden path",
        "street": "Paved street", "farmland": "Tilled soil", "crops": "Crops", "fence": "Fence",
        "down_stairs": "Stairs down", "up_stairs": "Stairs up", "open_air": "Opening to the level below",
    }
    for key, label in names.items():
        tile = getattr(tile_types, key)
        _LABELS[(int(tile.sprite), tuple(int(c) for c in tile.light_fg))] = label
    for key in ("bridge_h_start", "bridge_h_mid", "bridge_h_end", "bridge_v_start", "bridge_v_mid", "bridge_v_end"):
        tile = getattr(tile_types, key)
        _LABELS[(int(tile.sprite), tuple(int(c) for c in tile.light_fg))] = "Bridge"


def label_of(tile) -> Optional[str]:
    """The name of a special terrain tile record, else None."""
    if not _LABELS:
        _register()
    if bool(tile["open"]):
        return _LABELS.get((int(tile_types.open_air.sprite), tuple(int(c) for c in tile_types.open_air.light_fg)))
    light = tile["light"]
    return _LABELS.get((int(light["sprite"]), tuple(int(c) for c in light["fg"])))


def below(game_map, x: int, y: int) -> Optional[str]:
    """For an opening: what is known to lie beneath it ("nothing known below", a floor, or the things seen there)."""
    engine = getattr(game_map, "engine", None)
    game_world = getattr(engine, "game_world", None)
    if game_world is None:
        return None
    lower = game_world.world_at(game_map.z - 1)
    if lower is None or not lower.is_explored(x, y):
        return "unexplored below"
    things = [e.get_title() for e in lower.stack_at(x, y)]
    if things:
        return "below: " + ", ".join(things[:3])
    tile = lower.tile_at(x, y)
    if tile is not None and bool(tile["open"]):
        return "below: another drop"
    return "below: " + (label_of(tile) or "bare floor") if tile is not None else None


def describe(game_map, x: int, y: int) -> Optional[str]:
    """The terrain line for (x, y): the tile's name, plus for an opening what lies under it."""
    tile = game_map.tile_at(x, y)
    if tile is None:
        return None
    label = label_of(tile)
    if label is None:
        return None
    if bool(tile["open"]):
        note = below(game_map, x, y)
        return f"{label} ({note})" if note else label
    return label
