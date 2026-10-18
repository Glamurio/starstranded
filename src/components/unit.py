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
from capabilities import CapabilitySet, Grant
from skills import SkillSet
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
        self.poison: int = 0  # turns of poison left: 1 damage each
        self.last_upkeep: Optional[int] = None  # game time of the last hunger/thirst update (simulation.upkeep)
        self.blocks_movement = True
        self.skills: SkillSet = SkillSet()                 # trained skill levels (race + background + practice)
        self.skill_practice: dict = {}                     # Skill -> practice points toward the next level
        self.extra_grants: tuple = ()                      # tags from background, sponsor gear, statuses
        self.move_debt: float = 0.0                        # fractional turns carried between steps (move_speed)
        self.cold: int = 0                                 # turns spent below the comfort temperature (survival)
        self.breath: Optional[float] = None                # breath left in bad air (None: breathing normally)
        self.sleeping: bool = False
        ai_class = _AI_FOR_KIND.get(species.ai)
        self.ai = ai_class(self) if ai_class else None

    @property
    def capabilities(self) -> CapabilitySet:
        """Every tag this unit has: its species (race), background and worn gear. Tools it merely carries and
        stations near it are added by the crafting system when it asks (`crafting.unit_tags`)."""
        found = list(self.kind.grants) + list(self.extra_grants)
        armor = self.equipment.armor if self.equipment else None
        if armor is not None:
            found += [Grant(tag) for tag in getattr(armor, "worn_tags", ())]
        return CapabilitySet(found)

    def step_turns(self, dark: bool = False) -> int:
        """Whole turns the next step takes. `move_speed` 2.0 = every second step is free; 0.5 = each takes two turns.
        The remainder is carried in `move_debt`, so the long-run speed is exact and nothing is random."""
        speed = self.capabilities.stat("move_speed", dark=dark)
        self.move_debt += 1.0 / speed
        turns = int(self.move_debt + 1e-9)
        self.move_debt -= turns
        return turns

    @property
    def avoids_liquid(self) -> bool:
        return self.capabilities.has("liquid_averse")

    def refuses_liquid(self, x: int, y: int) -> bool:
        """True if a voluntary step onto (x, y) is refused: liquid terrain and a `liquid_averse` unit (knockback and
        falling do not go through here, so they are allowed)."""
        if not self.kind.grants or not self.avoids_liquid:
            return False
        tile = self.game_map.tile_at(x, y)
        return tile is not None and int(tile["liquid"]) != 0

    def damage_multiplier(self, damage_type) -> float:
        """Extra multiplier from tags (frail exoskeleton: blunt) on top of species `resistances`."""
        if damage_type is None:
            return 1.0
        return self.capabilities.stat(f"damage_taken_{damage_type.value}")

    def practice(self, skill, points: int = 1) -> bool:
        """Use a skill: enough practice raises it one level (thresholds in `skills.PRACTICE_NEEDED`). True on a level-up."""
        from skills import MAX_LEVEL, PRACTICE_NEEDED
        level = self.skills.level(skill)
        if level >= MAX_LEVEL:
            return False
        total = self.skill_practice.get(skill, 0) + points
        if total >= PRACTICE_NEEDED[level]:
            self.skill_practice[skill] = 0
            self.skills = self.skills.combine(SkillSet({skill: 1}))
            return True
        self.skill_practice[skill] = total
        return False

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
        bonus = self.equipment.power_bonus if self.equipment else 0
        weapon = self.equipment.weapon if self.equipment else None
        if weapon is None and self.kind.grants:
            bonus += int(self.capabilities.stat("unarmed_damage"))  # claws
        return bonus

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
        if nutrition == "ration":
            return True  # processed food: every race can digest it
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
        if self.kind.leather:
            from crafting import Leather
            self.inventory.add(Leather(self.species, self.inventory))
        if self.kind.hide is not None:
            from items import Stuff
            import species as defs
            self.inventory.add(Stuff(defs.PIECE_HIDE, self.kind.hide, self.inventory))


        seen = self is self.engine.player or self.game_map is None or self.game_map.is_visible(self.x, self.y)
        if not quiet and seen:
            self.engine.message_log.add_message(death_message, death_message_color)

        if killer:
            killer.level.add_xp(self.level.xp_given)
            if killer is self.engine.player and self.kind.key:
                kills = self.engine.game_world.run.kills
                kills[self.kind.key] = kills.get(self.kind.key, 0) + 1

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

    def apply_poison(self, turns: int) -> None:
        """Poison for `turns` more turns (they add up, to at most `MAX_POISON`)."""
        self.poison = min(self.MAX_POISON, self.poison + turns)

    def tick_poison(self, turns: int = 1) -> None:
        """Let `turns` turns of poison act: 1 damage per turn."""
        if self.poison <= 0 or not self.is_alive:
            return
        hurt = min(self.poison, turns)
        self.poison -= hurt
        self.handle_health(-hurt, None)

    MAX_POISON = 60

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

    def __init__(self, name: Optional[str] = None, species: UnitSpecies = HUMAN):
        Unit.__init__(self, species, name)
        self.background: Optional[str] = None
        self.sponsor: Optional[str] = None


class Selenite(Unit):
    def __init__(self, name: Optional[str] = None):
        Unit.__init__(self, SELENITE, name)


class Animal(Unit):
    def __init__(self, name: Optional[str] = None):
        Unit.__init__(self, RABBIT, name)
