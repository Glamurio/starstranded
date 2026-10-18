"""Sprite overrides: which sheet cell (column, row) a thing is drawn with.

The code keeps its own defaults; ``data/sprites.json`` holds only the *changes* (``{"unit.rabbit": [3, 20]}``), so a missing
or empty file means "all defaults". The debug sprite editor (main menu) writes this file. Keys:

    item.<key>  unit.<key>  unit.<key>.corpse  tile.<name>  tile.<name>.<variation>
    flora.<template>.<index>  fauna.<template>  fauna.<template>.corpse

Definitions ask ``get(key, default)`` when they are built; that call also records the default, so the editor can list every
key and reset it. Changes made in the editor are applied to the live registries and tiles at once; generated flora and fauna
pick theirs up the next time a world is generated.
"""
from __future__ import annotations

import dataclasses
import json
import os
from typing import Dict, List, Optional, Tuple

Pos = Tuple[int, int]

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "sprites.json")
DEFAULTS: Dict[str, Pos] = {}
_overrides: Optional[Dict[str, Pos]] = None


def _load() -> Dict[str, Pos]:
    global _overrides
    if _overrides is None:
        _overrides = {}
        try:
            with open(PATH, encoding="utf-8") as handle:
                for key, pos in json.load(handle).items():
                    _overrides[key] = (int(pos[0]), int(pos[1]))
        except (OSError, ValueError, TypeError, IndexError):
            _overrides = {}   # missing or broken config: draw everything with its default
    return _overrides


def get(key: str, default: Optional[Pos]) -> Optional[Pos]:
    """The sprite for `key`: its override if there is one, else `default` (which is remembered as the key's default)."""
    if default is None:
        return None
    DEFAULTS.setdefault(key, (default[0], default[1]))
    return _load().get(key, (default[0], default[1]))


def current(key: str) -> Optional[Pos]:
    return _load().get(key, DEFAULTS.get(key))


def is_changed(key: str) -> bool:
    return key in _load()


def set(key: str, pos: Pos, *, save_now: bool = True) -> None:   # noqa: A001 - mirrors get()
    pos = (int(pos[0]), int(pos[1]))
    if key in DEFAULTS and DEFAULTS[key] == pos:
        reset(key, save_now=save_now)
        return
    _load()[key] = pos
    _apply_live(key, pos)
    if save_now:
        save()


def reset(key: str, *, save_now: bool = True) -> None:
    _load().pop(key, None)
    if key in DEFAULTS:
        _apply_live(key, DEFAULTS[key])
    if save_now:
        save()


def save() -> None:
    data = {key: list(pos) for key, pos in sorted(_load().items())}
    with open(PATH, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1)
        handle.write("\n")


def reload() -> None:
    """Forget what was read (tests, or after the file was edited by hand)."""
    global _overrides
    _overrides = None


def catalog() -> List[str]:
    """Every editable key, grouped by kind. Makes sure the lazily-built definitions have registered their defaults."""
    import planet
    import species
    import tile_types   # noqa: F401 - importing registers the tile defaults
    for template in planet.FLORA_TEMPLATES:
        for i, sprite in enumerate(template.sprites):
            get(f"flora.{template.key}.{i}", sprite)
    for template in planet.FAUNA_TEMPLATES:
        get(f"fauna.{template.key}", template.sprite)
        get(f"fauna.{template.key}.corpse", template.corpse_sprite)
    order = {"item": 0, "unit": 1, "fauna": 2, "flora": 3, "tile": 4}
    return sorted(DEFAULTS, key=lambda key: (order.get(key.split(".", 1)[0], 9), key))


def label(key: str) -> str:
    kind, _, rest = key.partition(".")
    return f"{kind}: {rest.replace('.', ' ')}"


def _apply_live(key: str, pos: Pos) -> None:
    kind, _, rest = key.partition(".")
    if kind in ("item", "unit"):
        import species
        name, _, part = rest.partition(".")
        registry = species.ITEM_KINDS if kind == "item" else species.UNIT_SPECIES
        for key in [name] + [alias for alias, target in ALIASES.items() if target == name]:
            definition = registry.get(key)
            if definition is not None:
                object.__setattr__(definition, "corpse_sprite" if part == "corpse" else "sprite", pos)
    elif kind == "tile":
        import tile_types
        name, _, variation = rest.partition(".")
        tile = getattr(tile_types, name, None)
        if tile is not None:
            tile.set_sprite(pos, variation or None)
    # flora and fauna: generated per world, so they take the new sprite at the next world generation


ALIASES = {"selenite_people": "selenite"}
"""The playable Selenites look like the Selenites of the caves: one entry in the editor serves both."""


def registered(definition, kind: str):
    """Used by species.register: record the definition's default sprites and return it with any overrides applied."""
    changes = {}
    for attr, suffix in (("sprite", ""), ("corpse_sprite", ".corpse")):
        default = getattr(definition, attr, None)
        if default is not None and definition.key is not None:
            pos = get(f"{kind}.{ALIASES.get(definition.key, definition.key)}{suffix}", default)
            if pos != tuple(default):
                changes[attr] = pos
    return dataclasses.replace(definition, **changes) if changes else definition
