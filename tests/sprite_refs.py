"""Every sprite the game refers to, by a label that does not depend on where the sprite sits on the sheet.

`tests/data/sprite_golden.json` holds the hash of each one's pixels, recorded when the game used the old 50x50 Urizen sheet.
The merged sheet may put sprites anywhere, but each of these must still look exactly the same.
"""
import hashlib

import numpy as np
import pygame

import atlas
import species
import tile_types
from components import names


def sprite_refs() -> dict:
    refs = {}
    for attr, tile in vars(tile_types).items():
        if isinstance(tile, tile_types.Tile):
            refs[f"tile.{attr}"] = tile.sprite
            for name, sprite in tile.variation_ids.items():
                refs[f"tile.{attr}.{name}"] = sprite
    for key, kind in species.ITEM_KINDS.items():
        if kind.sprite_id is not None:
            refs[f"item.{key}"] = kind.sprite_id
    for key, unit in species.UNIT_SPECIES.items():
        refs[f"unit.{key}"] = unit.sprite_id
        refs[f"unit.{key}.corpse"] = unit.corpse_sprite_id
    for table_name, table in (("fruit", names.fruit_pos_names), ("tree", names.tree_pos_names), ("shrub", names.shrub_pos_names)):
        for coords, words in table.items():
            refs[f"{table_name}.{words[0]}"] = atlas.sprite_id(*coords)
    for category in species.PlantCategory:
        if category in (species.PlantCategory.TREE, species.PlantCategory.SHRUB):
            refs[f"plant.{category.name.lower()}.corpse"] = species.make_plant_species(category).corpse_sprite_id
    for coords in species.STUMP_SPRITES:
        refs[f"stump.{names.tree_pos_names[coords][0]}"] = atlas.sprite_id(*coords)
    return refs


def sprite_hash(sheet: atlas.SpriteAtlas, sprite: int) -> str:
    surface = sheet.get(sprite)
    alpha = (pygame.surfarray.array_alpha(surface) > 0).astype(np.uint8)
    return hashlib.sha1(alpha.tobytes()).hexdigest()
