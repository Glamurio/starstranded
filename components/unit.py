from __future__ import annotations
import copy

from typing import TYPE_CHECKING

from components.base_component import BaseComponent
from render_order import RenderOrder

import color
import entity_factories
from utilities import clamp

if TYPE_CHECKING:
    from entity import Actor

class Unit(BaseComponent):
    parent: Actor

    def __init__(self, hp: int, base_defense: int, base_power: int, thirst: int = 100, hunger: int = 100):
        self.max_hp = hp
        self._hp = hp
        self.base_defense = base_defense
        self.base_power = base_power
        self.max_hunger = hunger
        self.hunger = hunger
        self.max_thirst = thirst
        self.thirst = thirst

    @property
    def hp(self) -> int:
        return self._hp

    @hp.setter
    def hp(self, value: int) -> None:
        self._hp = max(0, min(value, self.max_hp))
        if self._hp == 0 and self.parent.ai:
            self.die()

    @property
    def defense(self) -> int:
        return self.base_defense + self.defense_bonus

    @property
    def power(self) -> int:
        return self.base_power + self.power_bonus

    @property
    def defense_bonus(self) -> int:
        if self.parent.equipment:
            return self.parent.equipment.defense_bonus
        else:
            return 0

    @property
    def power_bonus(self) -> int:
        if self.parent.equipment:
            return self.parent.equipment.power_bonus
        else:
            return 0

    def die(self) -> None:
        if self.engine.player is self.parent:
            death_message = "You died!"
            death_message_color = color.player_die
        else:
            death_message = f"{self.parent.get_title()} is dead!"
            death_message_color = color.enemy_die

        self.parent.char = "%"
        self.parent.color = color.red
        self.parent.blocks_movement = False
        self.parent.ai = None
        self.parent.is_alive = False
        self.parent.render_order = RenderOrder.CORPSE

        meat = copy.deepcopy(entity_factories.meat)
        meat.add_attribute(self.parent.type)
        self.parent.inventory.items.append(meat)

        self.engine.message_log.add_message(death_message, death_message_color)

        self.engine.player.level.add_xp(self.parent.level.xp_given)

    def heal(self, amount: int) -> int:
        if self.hp == self.max_hp:
            return 0

        new_hp_value = self.hp + amount

        if new_hp_value > self.max_hp:
            new_hp_value = self.max_hp

        amount_recovered = new_hp_value - self.hp

        self.hp = new_hp_value

        return amount_recovered

    def take_damage(self, amount: int) -> None:
        self.hp -= amount

    def handle_hunger(self, amount: int) -> None:
        self.hunger = clamp((self.hunger + amount), 0, self.max_hunger)

    def handle_thirst(self, amount: int) -> None:
        self.thirst = clamp((self.thirst + amount), 0, self.max_thirst)
