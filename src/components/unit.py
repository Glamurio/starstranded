from __future__ import annotations

from typing import Optional
from entity import Entity
from render_order import RenderOrder

import color
from components.ai import HostileEnemy
from components.inventory import Inventory
from components.equipment import Equipment
from components.level import Level
from components.consumable import Meat

from utilities import clamp, map_codepoints, generate_name, get_shade

class Unit(Entity):
    def __init__(self):
        Entity.__init__(self)
        self.max_hp = 10
        self.hp = self.max_hp
        self.base_defense = 1
        self.base_power = 1
        self.race: str = None

        self.equipment = Equipment(self)
        self.level = Level(self)

        self.max_hunger = 100
        self.hunger = self.max_hunger
        self.max_thirst = 100
        self.thirst = self.max_thirst

        self.ai = None

        self.is_alive: bool = True
        self.blocks_movement: bool = True
        self.render_order = RenderOrder.UNIT

        if self.equipment:
            self.equipment.parent = self
        if self.inventory:
            self.inventory.parent = self
        if self.level:
            self.level.parent = self       

    @property
    def has_ai(self) -> bool:
        """Returns True as long as this unit can perform actions."""
        return bool(self.ai)

    @property
    def defense(self) -> int:
        return self.base_defense + self.defense_bonus

    @property
    def power(self) -> int:
        return self.base_power + self.power_bonus

    @property
    def defense_bonus(self) -> int:
        if self.equipment:
            return self.equipment.defense_bonus
        else:
            return 0

    @property
    def power_bonus(self) -> int:
        if self.equipment:
            return self.equipment.power_bonus
        else:
            return 0

    def die(self, killer: Unit) -> None:
        if self is self.engine.player:
            death_message = "You died!"
            death_message_color = color.player_die
        else:
            death_message = f"{self.get_title()} is dead!"
            death_message_color = color.enemy_die

        self.char = self.char_corpse
        # self.color = color.red
        self.blocks_movement = False
        self.blocks_sight = False
        self.ai = None
        self.is_alive = False
        self.render_order = RenderOrder.CORPSE

        meat = Meat(self.kind, self.inventory)
        self.inventory.items.append(meat)

        self.engine.message_log.add_message(death_message, death_message_color)

        killer.level.add_xp(self.level.xp_given)

    def heal(self, amount: int) -> int:
        if self.hp == self.max_hp:
            return 0

        new_hp_value = self.hp + amount

        if new_hp_value > self.max_hp:
            new_hp_value = self.max_hp

        amount_recovered = new_hp_value - self.hp

        self.hp = new_hp_value

        return amount_recovered

    def handle_health(self, amount: int, entity: Entity) -> None:
        self.hp = clamp((self.hp + amount), 0, self.max_hunger)
        if self.hp == 0 and self.ai:
            self.die(entity)

    def handle_hunger(self, amount: int) -> None:
        self.hunger = clamp((self.hunger + amount), 0, self.max_hunger)

    def handle_thirst(self, amount: int) -> None:
        self.thirst = clamp((self.thirst + amount), 0, self.max_thirst)

    def get_title(self, exclude_attributes: bool = False) -> str:
        """Returns the entity title, including attributes and type. If entity is unnamed, returns type."""
        attributes = [] if exclude_attributes else self.attributes
        description = f'{" ".join(attributes)} {self.kind}' if attributes else self.kind
        if not self.is_alive:
            return f'remains of {self.name}' if self.name else f'{self.kind} remains'
        return f'{self.name}, the {description}' if self.name else description

class Player(Unit):
    def __init__(self):
        Unit.__init__(self)
        self.max_hp = 30
        self.hp = self.max_hp
        self.base_defense = 1
        self.base_power = 2
        self.color=(255, 255, 255)
        self.name="Ardan"
        self.kind="Player"
        self.race="Human"
        self.ai=HostileEnemy(self)
        self.inventory=Inventory(self, capacity=26)
        self.level=Level(self, level_up_base=100, xp_given=50)
        self.equipment=Equipment(self)
        self.sprite_pos=(0, 9)
        self.corpse_sprite_pos=(24, 11)
        char_info = map_codepoints(self.kind, self.sprite_pos, True, self.corpse_sprite_pos)
        self.char = char_info["sprite"]
        self.char_left = self.char
        self.char_right = char_info["mirror"]
        self.char_corpse = char_info["corpse"]

class Selenite(Unit):
    def __init__(self, name: Optional[str] = None):
        Unit.__init__(self)
        self.max_hp = 10
        self.hp = self.max_hp
        self.base_defense = 0
        self.base_power = 3
        self.color = get_shade(color.light_blue)
        self.name = name if name else generate_name("selenite")
        self.kind="Selenite"
        self.race="Selenite"
        self.ai=HostileEnemy(self)
        self.inventory=Inventory(self, capacity=26)
        self.level=Level(self, level_up_base=100, xp_given=35)
        self.equipment=Equipment(self)
        self.sprite_pos=(2, 37)
        self.corpse_sprite_pos=(44, 11)
        char_info = map_codepoints(self.kind, self.sprite_pos, True, self.corpse_sprite_pos)
        self.char = char_info["sprite"]
        self.char_left = char_info["sprite"]
        self.char_right = char_info["mirror"]
        self.char_corpse = char_info["corpse"]