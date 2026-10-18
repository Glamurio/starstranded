"""A small passive herbivore for tests that need "some animal" (the game itself only has planet fauna now)."""
from typing import Optional

from components.unit import Unit
from species import AIKind, Diet, UnitSpecies

HOPPER = UnitSpecies(
    "test_hopper", "Hopper", sprite=(3, 20), corpse_sprite=(44, 16), color=None,
    max_hp=1, power=3, defense=0, level_up_base=100, xp_given=35, ai=AIKind.PASSIVE, diet=Diet.HERBIVORE, leather=True,
)


class Animal(Unit):
    def __init__(self, name: Optional[str] = None):
        Unit.__init__(self, HOPPER, name)


# ── a plain pointed stick for the weapon tests (the game's spears are crafted `items.Gear`) ──
from components.equippable import Equippable  # noqa: E402
from damage import DamageType  # noqa: E402
from equipment_types import EquipmentType  # noqa: E402
from species import ItemKind  # noqa: E402

SPEAR_KIND = ItemKind("test_spear", "Spear", sprite=(42, 27), color=(0x8B, 0x6B, 0x3D), material="Wooden",
                      equipment_type=EquipmentType.WEAPON, power_bonus=3, damage_type=DamageType.PIERCE)


class Spear(Equippable):
    def __init__(self, parent=None):
        Equippable.__init__(self, SPEAR_KIND, parent)
