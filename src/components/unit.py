from __future__ import annotations

from typing import Optional
from entity import Entity, EntityCategory
from render_order import RenderOrder

import color
from components.ai import HostileAI, PassiveAI
from components.inventory import Inventory
from components.equipment import Equipment
from components.level import Level
from components.consumable import Meat
from species import AIKind, HUMAN, RABBIT, SELENITE, UnitSpecies

from utilities import clamp, generate_name, get_gaussian_shade, get_random_color

_AI_FOR_KIND = {AIKind.PASSIVE: PassiveAI, AIKind.HOSTILE: HostileAI}


class Unit(Entity):
    """A living (or dead) creature. Static stats come from `kind: UnitSpecies`; this holds the live state."""

    category = EntityCategory.UNIT
    object_type = "Unit"
    has_inventory = True
    kind: UnitSpecies

    def __init__(self, species: UnitSpecies, name: Optional[str] = None):
        Entity.__init__(self, species)
        self.max_hp = species.max_hp  # can grow on level-up, so it is per instance
        self.hp = self.max_hp
        self.base_defense = species.defense
        self.base_power = species.power

        self.max_hunger = species.max_hunger
        self.hunger = self.max_hunger
        self.max_thirst = species.max_thirst
        self.thirst = self.max_thirst

        self.color = species.color if species.color is not None else get_random_color()
        self.shade = self.color if species.shade_sigma is None else get_gaussian_shade(self.color, species.shade_sigma)
        if name:
            self.name = name
        elif species.name_origin:
            self.name = generate_name(species.name_origin)
        else:
            self.name = species.default_name

        self.inventory: Inventory = Inventory(self, capacity=species.inventory_capacity)
        self.equipment = Equipment(self)
        self.level = Level(self, level_up_base=species.level_up_base, xp_given=species.xp_given)

        self.is_alive: bool = True
        self.last_upkeep: Optional[int] = None  # game time of the last hunger/thirst update (simulation.upkeep)
        self.blocks_movement = True
        ai_class = _AI_FOR_KIND.get(species.ai)
        self.ai = ai_class(self) if ai_class else None

    @property
    def radius(self) -> int:
        return self.kind.radius

    @property
    def is_corpse(self) -> bool:
        return not self.is_alive

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

    @property
    def damage_type(self):
        """What this unit's hits deal: its wielded weapon's type, else its natural attack."""
        weapon = self.equipment.weapon if self.equipment else None
        return (weapon.damage_type if weapon is not None else None) or self.kind.damage_type

    def resistances(self):
        return self.kind.resistances

    @property
    def diet(self):
        return self.kind.diet

    def can_eat(self, item) -> bool:
        """Can this unit digest `item` (a food: plant matter for herbivores, meat for carnivores, both for omnivores)?"""
        from species import Diet
        nutrition = getattr(item, "nutrition", None)
        if nutrition == "meat":
            return self.diet is not Diet.HERBIVORE
        if nutrition == "plant":
            return self.diet is not Diet.CARNIVORE
        return False

    def die(self, killer: Unit = None, quiet: bool = False) -> None:
        """Become a corpse (with two pieces of meat). `quiet`: no message (deaths in chunks the player cannot see)."""
        if self is self.engine.player:
            death_message = "You died!"
            death_message_color = color.player_die
        else:
            death_message = f"{self.get_title()} is dead!"
            death_message_color = color.enemy_die

        self.blocks_movement = False
        self.blocks_sight = False
        self.ai = None
        self.is_alive = False
        self.render_order = RenderOrder.CORPSE

        self.inventory.add(Meat(self.species, self.inventory))
        self.inventory.add(Meat(self.species, self.inventory))


        seen = self is self.engine.player or self.game_map is None or self.game_map.is_visible(self.x, self.y)
        if not quiet and seen:
            self.engine.message_log.add_message(death_message, death_message_color)

        if killer:
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

    def handle_health(self, amount: int, entity: Optional[Entity]) -> None:
        self.hp = clamp((self.hp + amount), 0, self.max_hp)
        if self.hp == 0 and self.is_alive:
            self.die(entity)

    def handle_hunger(self, amount: int) -> None:
        """Change hunger by `amount`. At 0 hunger *any* unit loses 1 HP per call (starvation).

        Only the player gets the message, once, when hunger first reaches 0.
        """
        prev_hunger = self.hunger
        self.hunger = clamp((self.hunger + amount), 0, self.max_hunger)
        if self.hunger == 0:
            if self is self.engine.player and prev_hunger > 0:
                self.engine.message_log.add_message(
                    f"{self.get_title()} is starving!", color.enemy_atk
                )
            self.handle_health(-1, None)

    def handle_thirst(self, amount: int) -> None:
        """Change thirst by `amount`. At 0 thirst *any* unit loses 1 HP per call (dehydration).

        Only the player gets the message, once, when thirst first reaches 0.
        """
        prev_thirst = self.thirst
        self.thirst = clamp((self.thirst + amount), 0, self.max_thirst)
        if self.thirst == 0:
            if self is self.engine.player and prev_thirst > 0:
                self.engine.message_log.add_message(
                    f"{self.get_title()} is severely dehydrated!", color.enemy_atk
                )
            self.handle_health(-1, None)

    def get_title(self, exclude_attributes: bool = False) -> str:
        """Returns the entity title, including attributes and type. If entity is unnamed, returns type."""
        attributes = [] if exclude_attributes else self.attributes
        description = f'{" ".join(attributes)} {self.species}' if attributes else self.species
        if not self.is_alive:
            return f'remains of {self.name}' if self.name else f'{self.species} remains'
        return f'{self.name}, the {description}' if self.name else description


class Player(Unit):
    object_type = "Player"

    def __init__(self, name: Optional[str] = None):
        Unit.__init__(self, HUMAN, name)


class Selenite(Unit):
    def __init__(self, name: Optional[str] = None):
        Unit.__init__(self, SELENITE, name)


class Animal(Unit):
    def __init__(self, name: Optional[str] = None):
        Unit.__init__(self, RABBIT, name)
