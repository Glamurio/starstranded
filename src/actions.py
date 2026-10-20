from __future__ import annotations

from typing import List, Optional, Tuple, TYPE_CHECKING
import color
import exceptions
import lighting
from entity import EntityCategory
from materials import Material, attack_factor

if TYPE_CHECKING:
    from components.unit import Unit
    from engine import Engine
    from entity import Entity, Item
    from crafting import Recipe


class Action:
    def __init__(self, entity: Unit) -> None:
        super().__init__()
        self.entity = entity

    @property
    def engine(self) -> Engine:
        """Return the engine this action belongs to."""
        return self.entity.game_map.engine

    @property
    def target_unit(self) -> Optional[Unit]:
        """Return the unit at this actions destination."""
        return self.engine.game_map.get_unit_at_location(*self.dest_xy)

    @property
    def target_plant(self) -> Optional[Entity]:
        """Return the living plant at this actions destination (the one that blocks movement first)."""
        plants = [e for e in self.engine.game_map.get_entities_at_location(*self.dest_xy)
                  if e.category is EntityCategory.PLANT and not e.dead]
        return next((p for p in plants if p.blocks_movement), plants[0] if plants else None)

    @property
    def target_structure(self) -> Optional[Entity]:
        """Return the built structure (a wall) at this actions destination."""
        return next((e for e in self.engine.game_map.get_entities_at_location(*self.dest_xy)
                     if getattr(e, "is_structure", False) and not getattr(e, "dead", False)), None)

    def perform(self) -> bool:
        """Perform this action with the objects needed to determine its scope.

        `self.engine` is the scope this action is being performed in.

        `self.entity` is the object performing the action.

        If the action is supposed to pass time, it must be inherited via `super().perform()`.

        If the action is supposed to repeat, return `True`.
        """
        # Always pass time when an action occurs
        self.engine.game_world.pass_time(unit=self.entity, time=1)

        return False


class PickupAction(Action):
    """Pickup an item and add it to the inventory, if there is room for it."""

    def __init__(self, entity: Unit, item: Item):
        super().__init__(entity)

        self.item = item

    def perform(self) -> None:
        # super().perform()

        self.entity.inventory.loot(self.item)
        self.engine.message_log.add_message(f"You picked up {self.item.get_title()}!")

class MassPickupAction(Action):
    """Pickup a list of items and add it to the inventory, if there is room for it."""

    def __init__(self, entity: Unit, items: List[Item]):
        super().__init__(entity)
        self.items = items

    def perform(self) -> None:
        inventory = self.entity.inventory
        picked, full = [], False
        for item in list(self.items):
            if getattr(item, "has_inventory", False):  # units/plants are containers, not loot
                continue
            try:
                inventory.loot(item)
            except exceptions.Impossible:
                full = True
                break
            if item in inventory.items:                # (only what really went into the pack is reported)
                picked.append(item)
            else:
                full = True
                break
        log = self.engine.message_log.add_message
        if picked:
            title = picked[0].get_title()
            log(f"You picked up {title}!" if len(picked) == 1 else f"You picked up {title} x{len(picked)}!")
            self.engine.game_world.pass_time(unit=self.entity, time=1)
        if full:
            raise exceptions.Impossible("Your Inventory is full." if picked else "Your Inventory is full: you picked up nothing.")


class ItemAction(Action):
    def __init__(self, entity: Unit, item: Item, target_xy: Optional[Tuple[int, int]] = None):
        super().__init__(entity)
        self.action = 'activate'
        self.item = item
        
        if not target_xy:
            target_xy = entity.x, entity.y
        self.target_xy = target_xy

    def perform(self) -> None:
        """Invoke the items ability, this action will be given to provide context."""
        super().perform()

        if self.item and self.action == 'activate':
            self.item.activate(self.entity)


class DropItem(ItemAction):
    def __init__(self, entity: Unit, item: Item, target_xy: Optional[Tuple[int, int]] = None):
        super().__init__(entity, item, target_xy)
        self.action = 'drop'

    def perform(self) -> None:
        super().perform()

        from components.equippable import Equippable
        if isinstance(self.item, Equippable) and self.item.equipped:
            self.entity.equipment.toggle_equip(self.item)

        self.entity.inventory.drop(self.item, self.target_xy)


class DropStack(Action):
    """Drop every item of a stack (identical things sharing one row of the inventory) at your feet: one turn, one message."""

    def __init__(self, entity: Unit, items):
        super().__init__(entity)
        self.items = list(items)

    def perform(self) -> None:
        from components.equippable import Equippable
        held = [i for i in self.items if i in self.entity.inventory.items]
        for item in held:
            if isinstance(item, Equippable) and item.equipped:
                self.entity.equipment.toggle_equip(item)
            self.entity.inventory.drop(item, None, announce=False)
        if held:
            title = held[0].get_title()
            self.engine.message_log.add_message(f"You dropped {title}." if len(held) == 1 else f"You dropped {title} x{len(held)}.")


class EquipAction(Action):
    def __init__(self, entity: Unit, item: Item):
        super().__init__(entity)
        self.item = item

    def perform(self) -> None:
        self.entity.equipment.toggle_equip(self.item)


class WaitAction(Action):
    def perform(self) -> None:
        super().perform()


class TakeStairsAction(Action):
    """Use the staircase under the entity: `direction` +1 climbs, -1 descends, 0 (default) takes whichever is here."""

    def __init__(self, entity: Unit, direction: int = 0):
        super().__init__(entity)
        self.direction = direction

    def perform(self) -> None:
        super().perform()
        game_world = self.engine.game_world
        before = game_world.current_z
        game_world.take_stairs(self.direction)
        self.engine.message_log.add_message(
            "You climb the staircase." if game_world.current_z > before else "You descend the staircase.", color.descend
        )


class ActionWithDirection(Action):
    def __init__(self, entity: Unit, dest_x: int, dest_y: int):
        super().__init__(entity)

        self.dest_x = dest_x
        self.dest_y = dest_y

    @property
    def dest_xy(self) -> Tuple[int, int]:
        """Returns this action's destination."""
        return self.dest_x, self.dest_y

    @property
    def blocking_entity(self) -> Optional[Entity]:
        """Return the blocking entity at this actions destination.."""
        return self.engine.game_map.get_entities_at_location(*self.dest_xy, True)

    def get_path(self, x: int, y: int) -> List[Tuple]:
        return self.engine.get_path_to(self.entity, x, y)

    def perform(self) -> None:
        super().perform()


def material_damage(attacker, target, damage: int, damage_type) -> int:
    """Scale a hit by how well the weapon's material delivers the damage type against the target's material
    (`materials.attack_factor`): an iron axe bites wood, a wooden club barely dents stone. Targets without a material
    (creatures, old-style plants) take the plain damage. Bare hands count as an ordinary weapon."""
    if damage <= 0:
        return damage
    material = getattr(target, "material", None) if getattr(target, "is_structure", False) else getattr(target.kind, "material", None)
    if not isinstance(material, Material):
        return damage
    weapon = attacker.equipment.weapon if getattr(attacker, "equipment", None) else None
    props = getattr(weapon, "props", None)
    factor = attack_factor(damage_type, props, material)
    return max(1, round(damage * factor))


class MeleeAction(ActionWithDirection):
    """Hit the unit (or, failing that, the plant) at the destination with the attacker's damage type."""

    def perform(self) -> None:
        from damage import resolve

        attacker: Unit = self.entity
        target = self.target_unit or self.target_plant or self.target_structure

        if not target:
            raise exceptions.Impossible("Nothing to attack.")

        if attacker == target:
            return

        damage_type = attacker.damage_type
        from skills import Skill
        skills = getattr(attacker, "skills", None)
        training = skills.level(Skill.COMBAT) if skills is not None else 0
        damage = resolve(attacker.power + training, getattr(target, "defense", 0), damage_type, target.resistances())
        damage = material_damage(attacker, target, damage, damage_type)
        if damage > 0 and hasattr(target, "damage_multiplier"):
            damage = max(1, round(damage * target.damage_multiplier(damage_type)))

        attack_desc = f"{attacker.get_title()} attacks {target.get_title()}"
        if attacker is self.engine.player:
            attack_color = color.player_atk
        else:
            attack_color = color.enemy_atk
        world = self.engine.game_map  # fights the player cannot see are not reported
        seen = target is self.engine.player or world.is_visible(attacker.x, attacker.y) or world.is_visible(target.x, target.y)
        if damage > 0:
            if seen:
                self.engine.message_log.add_message(
                    f"{attack_desc} for {damage} {damage_type} damage.", attack_color
                )
            target.handle_health(-damage, attacker)
        elif seen:
            self.engine.message_log.add_message(
                f"{attack_desc} but does no damage.", attack_color
            )
        if attacker is self.engine.player and self.target_unit is not None:
            attacker.practice(Skill.COMBAT, 1)   # every blow against a creature is practice

        self.engine.game_world.pass_time(unit=self.entity, time=1)

class MovementAction(ActionWithDirection):

    def _swim_step(self) -> bool:
        """Is this step a swim the player may make (deep water, nothing in the way, breath to spare)? Refuses a step into
        deep water when the breath is nearly gone: the way back to land is always open."""
        import liquids
        engine = self.engine
        if self.entity is not engine.player or not engine.game_map.in_bounds(self.dest_x, self.dest_y):
            return False
        if not liquids.swimmable(engine.game_map.tile_at(self.dest_x, self.dest_y)):
            return False
        if engine.game_map.get_entities_at_location(self.dest_x, self.dest_y, True):
            return False
        capacity = self.entity.capabilities.stat("breath_turns")
        breath = self.entity.breath
        if breath is not None and breath <= max(2.0, 0.2 * capacity) * liquids.SWIM_COST:
            raise exceptions.Impossible("You are running out of breath: get out of the water!")
        return True

    def __init__(self, entity: Unit, dest_x: int, dest_y: int, path: Optional[List[Tuple]] = None):
        super().__init__(entity, dest_x, dest_y)

        self.dest_x = dest_x
        self.dest_y = dest_y
        self.path = path if path is not None else []

    def perform(self) -> bool:

        if not self.path:
            raise exceptions.Impossible("That way is blocked.")

        self.dest_x, self.dest_y = self.path.pop(0)

        import debug
        if self.entity is self.engine.player and debug.is_god(self.engine):
            from chunks import chunk_key
            self.engine.game_map.load_chunk(chunk_key(self.dest_x, self.dest_y))   # God Mode walks through anything, even the unloaded
            if not self.engine.game_map.in_bounds(self.dest_x, self.dest_y):
                raise exceptions.Impossible("Nothing can be reached there.")
        else:
            if self.entity.refuses_liquid(self.dest_x, self.dest_y):
                raise exceptions.Impossible(f"{self.entity.get_title()} will not wade into the liquid.")
            swimming = self._swim_step()
            if not swimming and not self.engine.can_move(self.dest_x, self.dest_y):
                raise exceptions.Impossible("That way is blocked.")

        self.entity.move(self.dest_x, self.dest_y)
        turns = self.entity.step_turns(dark=self.entity is self.engine.player and lighting.is_dark_at(self.engine))
        if self.entity is self.engine.player:
            import liquids
            import survival
            tile = self.engine.game_map.tile_at(self.dest_x, self.dest_y)
            if liquids.swimmable(tile):
                turns = turns * liquids.SWIM_COST if turns else 1       # swimming takes twice as long as walking
            survival.soak(self.entity, tile)
        if turns:
            self.engine.game_world.pass_time(unit=self.entity, time=turns)
        elif self.entity is self.engine.player:
            self.engine.update_fov()  # a free step still moves the view

        if not self.entity == self.engine.player:
            return

        import debug
        if debug.is_god(self.engine):
            return bool(self.path)        # God Mode: nothing is an enemy
        # Move player until an enemy is visible (an enemy = a unit with a hostile AI)
        for enemy in self.engine.game_map.actors:
            if enemy is self.entity or enemy.category is not EntityCategory.UNIT:
                continue
            import allegiance
            if not allegiance.threatens(enemy, self.entity):
                continue
            if max(abs(enemy.x - self.entity.x), abs(enemy.y - self.entity.y)) > 8:
                continue  # cheap reject before the line-of-sight test

            if self.engine.can_see(self.entity.x, self.entity.y, enemy.x, enemy.y, 8):
                return False

        return bool(self.path)   # repeat only while there are steps left (a single step used to repeat into "blocked")


class BumpAction(ActionWithDirection):

    def perform(self) -> None:
        path: List[Tuple] = self.get_path(self.dest_x, self.dest_y)

        distance = max(abs(self.dest_x - self.entity.x), abs(self.dest_y - self.entity.y))  # Chebyshev distance.

        if self.target_unit and not self.target_unit == self.entity and self.target_unit.is_alive and distance <= 1:
            return MeleeAction(self.entity, self.dest_x, self.dest_y).perform()

        import debug
        if self.entity is self.engine.player and debug.is_god(self.engine):
            return MovementAction(self.entity, self.dest_x, self.dest_y,
                                  debug.straight_path(self.entity, self.dest_x, self.dest_y)).perform()

        # A wielded weapon (an axe, say) lets you cut down a plant that is in the way; bare hands just bump.
        plant = self.target_plant
        if plant is not None and plant.blocks_movement and distance <= 1 and self.entity.equipment.weapon is not None:
            return MeleeAction(self.entity, self.dest_x, self.dest_y).perform()

        structure = self.target_structure
        if structure is not None and distance <= 1 and self.entity.equipment.weapon is not None:
            return MeleeAction(self.entity, self.dest_x, self.dest_y).perform()

        if distance <= 1 and is_rock_face(self.engine.game_map, self.dest_x, self.dest_y) and mining_tool(self.entity) is not None:
            return MineAction(self.entity, self.dest_x, self.dest_y).perform()

        return MovementAction(self.entity, self.dest_x, self.dest_y, path).perform()


def is_rock_face(world, x: int, y: int) -> bool:
    """A solid wall tile (not the edge of the world, not a door or stairs)."""
    tile = world.tile_at(x, y)
    if tile is None or tile["walkable"] or tile["transparent"] or tile["liquid"] or tile["stairs"]:
        return False
    from atlas import NO_SPRITE
    return int(tile["dark"]["sprite"]) != NO_SPRITE


def tool_with(unit, tag: str):
    """The best carried tool granting `tag`: the wielded one first, then the one with the hardest head."""
    from components.equippable import Equippable
    tools = [i for i in unit.inventory.items if isinstance(i, Equippable) and tag in getattr(i, "tool_tags", ())]
    weapon = unit.equipment.weapon if unit.equipment else None
    if weapon is not None and weapon not in tools and tag in getattr(weapon, "tool_tags", ()):
        tools.append(weapon)
    if not tools:
        return None
    tools.sort(key=lambda t: (t is not weapon, -tool_head(t).hardness if tool_head(t) else 0))
    return tools[0]


def mining_tool(unit):
    return tool_with(unit, "mining")


def tool_head(tool) -> Optional[Material]:
    parts = getattr(tool, "parts", None)
    if not parts:
        return None
    for role in ("head", "blade", "body"):
        if role in parts:
            return parts[role]
    return next(iter(parts.values()))


class MineAction(ActionWithDirection):
    """Break the rock face next to you with a mining tool: the tile opens up and you get a piece of what it was made of."""

    def perform(self) -> None:
        import resources
        import species as defs
        from crafting import make_piece
        engine, user, world = self.engine, self.entity, self.engine.game_map
        if max(abs(self.dest_x - user.x), abs(self.dest_y - user.y)) > 1 or not is_rock_face(world, self.dest_x, self.dest_y):
            raise exceptions.Impossible("There is no rock face there to mine.")
        tool = mining_tool(user)
        if tool is None:
            raise exceptions.Impossible("You need a pickaxe (or another mining tool) to break rock.")
        game_world = engine.game_world
        planet = game_world.planet
        if planet is None:
            raise exceptions.Impossible("The rock is too hard here.")
        biome = resources.biome_key_at(game_world, world.z, self.dest_x, self.dest_y)
        rock = resources.wall_material(planet, game_world.master_seed, world.z, self.dest_x, self.dest_y, biome)
        head = tool_head(tool)
        need = resources.mine_difficulty(rock)
        if head is None or head.hardness < need:
            raise exceptions.Impossible(
                f"Your {tool.get_title()} cannot break {rock.name}: its head is too soft (hardness {head.hardness if head else 0:.1f} "
                f"against about {need:.1f}).")
        piece = piece_kind_for(rock)
        import tile_types
        world.set_tile(self.dest_x, self.dest_y, tile_types.cave_floor.get_array())
        item = make_piece(piece, rock)
        inventory = user.inventory
        if inventory.is_full():
            world.add_entity(item, user.x, user.y)
            where = "it falls at your feet"
        else:
            inventory.add(item)
            where = "you pick it up"
        engine.message_log.add_message(f"You break out {item.get_title()}; {where}.", color.menu_text)
        from skills import Skill
        user.practice(Skill.GEOLOGY)
        game_world.pass_time(unit=user, time=2)
        engine.update_fov()


def piece_kind_for(rock: Material):
    import species as defs
    from materials import Family
    if rock.family is Family.FUEL:
        return defs.PIECE_COAL
    if rock.refines_to or rock.id.startswith("ore:"):
        return defs.PIECE_ORE
    return defs.PIECE_STONE


class GatherAction(Action):
    """Dig the ground you stand on: sand on shores and in deserts, clay in wet ground. A shovel is fast, bare hands slow."""

    def perform(self) -> None:
        import resources
        import species as defs
        from crafting import make_piece
        engine, user, world = self.engine, self.entity, self.engine.game_map
        planet = engine.game_world.planet
        tile = world.tile_at(user.x, user.y)
        if planet is None or tile is None or tile["liquid"] or tile["stairs"]:
            raise exceptions.Impossible("There is nothing to dig here.")
        found = resources.ground_material(planet, engine.game_world, world, user.x, user.y)
        if found is None:
            raise exceptions.Impossible("The ground here is just loose soil: nothing useful to dig. Look near water, or in sandy country.")
        form, material = found
        item = make_piece(defs.PIECE_SAND if form == "sand" else defs.PIECE_CLAY, material)
        tool = tool_with(user, "digging")
        user.inventory.add(item)  # raises Impossible if the pack is full, before time passes
        engine.message_log.add_message(f"You dig up {item.get_title()}.", color.menu_text)
        engine.game_world.pass_time(unit=user, time=resources.DIG_TURNS_TOOL if tool else resources.DIG_TURNS_BARE)


class SharpenAction(Action):
    """Put an edge on the wielded (or given) tool with an abrasive stone or sand you carry."""

    def __init__(self, entity: Unit, gear=None):
        super().__init__(entity)
        self.gear = gear

    def perform(self) -> None:
        from items import ABRASIVE, Stuff
        user = self.entity
        gear = self.gear or (user.equipment.weapon if user.equipment else None)
        if gear is None or not hasattr(gear, "sharpen"):
            raise exceptions.Impossible("Wield an edged tool first.")
        if not getattr(gear, "dull", False):
            raise exceptions.Impossible(f"{gear.get_title()} is already keen.")
        head = tool_head(gear)
        needed = max(ABRASIVE, (head.hardness if head else 0) - 3.5)
        stones = [i for i in user.inventory.items if isinstance(i, Stuff) and i.form in ("Stone", "Sand") and i.substance.abrasivity >= needed]
        if not stones:
            raise exceptions.Impossible(f"You need a whetstone: a stone or sand with abrasivity of at least {needed:.1f}.")
        gear.sharpen()
        self.engine.message_log.add_message(f"You sharpen {gear.get_title()} on {stones[0].get_title()}.", color.menu_text)
        self.engine.game_world.pass_time(unit=user, time=2)


class EatAction(Action):
    """Eat or drink a food from the pack: it takes a turn (but only if the user can digest it)."""

    def __init__(self, entity: Unit, item):
        super().__init__(entity)
        self.item = item

    def perform(self) -> None:
        self.item.activate(self.entity)   # raises Impossible, before time passes, if it cannot be digested
        self.engine.game_world.pass_time(unit=self.entity, time=1)


class UseMedkitAction(Action):
    def __init__(self, entity: Unit, kit):
        super().__init__(entity)
        self.kit = kit

    def perform(self) -> None:
        user = self.entity
        if user.hp >= user.max_hp:
            raise exceptions.Impossible("You are not hurt.")
        amount = user.heal(10 + round(10 * self.kit.quality))
        if user.inventory.items and self.kit in user.inventory.items:
            user.inventory.remove(self.kit)
        self.engine.message_log.add_message(f"You use the medkit and recover {amount} health.", color.health_recovered)
        self.engine.game_world.pass_time(unit=user, time=3)


class CraftAction(Action):
    """Craft a recipe from what the unit carries (see `crafting.check`) and add the result to the inventory."""

    def __init__(self, entity: Unit, recipe, choices=None):
        super().__init__(entity)
        self.recipe = recipe
        self.choices = choices

    def perform(self) -> None:
        import crafting
        results = crafting.craft(self.recipe, self.entity, self.choices)
        names = ", ".join(r.get_title() for r in results)
        hint = " Use it from your inventory to place it." if self.recipe.is_placeable else ""
        self.engine.message_log.add_message(f"You made {names}!{hint}", color.menu_text)
        from skills import Skill
        skill = self.recipe.skill[0] if self.recipe.skill else (Skill.ENGINEERING if self.recipe.stage >= 3 else None)
        if skill is not None and self.entity.practice(skill):
            self.engine.message_log.add_message(f"Your {skill.value} improves!", color.menu_text)
        self.engine.game_world.pass_time(unit=self.entity, time=max(1, self.recipe.time))


class UseFlaskAction(Action):
    """Use a flask: boil its liquid at a lit campfire, else drink from it, else fill it from a liquid next to you."""

    def __init__(self, entity: Unit, flask):
        super().__init__(entity)
        self.flask = flask

    def _lit_campfire_near(self) -> bool:
        from crafting import Campfire
        world, e = self.engine.game_map, self.entity
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for thing in world.get_entities_at_location(e.x + dx, e.y + dy):
                    if isinstance(thing, Campfire) and thing.emits_light:
                        return True
        return False

    def perform(self) -> None:
        import liquids
        flask, user, log = self.flask, self.entity, self.engine.message_log
        world = self.engine.game_map
        if flask.sips and not flask.boiled and self._lit_campfire_near():
            flask.boiled = True
            log.add_message("You hold the flask over the fire until the liquid boils.", color.menu_text)
            self.engine.game_world.pass_time(unit=user, time=3)
        elif flask.sips:
            flask.sips -= 1
            user.handle_thirst(liquids.SIP_THIRST)
            kind = liquids.LiquidKind(flask.liquid)
            if kind is liquids.LiquidKind.TOXIC:
                user.apply_poison(liquids.POISON_TOXIC)
                log.add_message("You feel terribly sick.", color.enemy_atk)
            elif kind in (liquids.LiquidKind.IMPURE, liquids.LiquidKind.HOT) and not flask.boiled:
                user.apply_poison(liquids.POISON_RAW)
                log.add_message("You feel sick.", color.enemy_atk)
            else:
                log.add_message("You drink. It is refreshing.", color.health_recovered)
            if not flask.sips:
                flask.liquid, flask.boiled = 0, False
            self.engine.game_world.pass_time(unit=user, time=1)
        else:
            found = liquids.nearest_liquid(world, user.x, user.y)
            if found is None:
                raise exceptions.Impossible("The flask is empty, and there is no liquid next to you to fill it from.")
            _, _, kind = found
            if kind is liquids.LiquidKind.LAVA:
                raise exceptions.Impossible("You cannot fill a flask with molten rock.")
            if kind is liquids.LiquidKind.ACIDIC:
                user.inventory.remove(flask)
                log.add_message("The liquid hisses and eats through the flask!", color.enemy_atk)
            else:
                flask.liquid, flask.sips, flask.boiled = int(kind), liquids.FLASK_SIPS, False
                log.add_message("You fill the flask with liquid.", color.menu_text)
            self.engine.game_world.pass_time(unit=user, time=1)


class InteractAction(Action):
    """Interact with a fire on or next to the player's tile: light it (needs fuel in your pack and something to strike a
    spark with), or add fuel to a burning one. Fires with no fuel mechanics (the old toggle) still flip on and off."""

    def __init__(self, entity: Unit):
        super().__init__(entity)

    def _fire(self):
        from crafting import Campfire
        world, e = self.engine.game_map, self.entity
        for dx, dy in [(0, 0)] + [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0)]:
            for thing in world.get_entities_at_location(e.x + dx, e.y + dy):
                if isinstance(thing, Campfire) and thing.is_placed:
                    return thing
        return None

    def _site(self):
        from structures import Structure
        world, e = self.engine.game_map, self.entity
        best = None
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                for thing in world.get_entities_at_location(e.x + dx, e.y + dy):
                    if isinstance(thing, Structure):
                        d = max(abs(dx), abs(dy))
                        if best is None or d < best[0]:
                            best = (d, thing)
        return None if best is None else best[1]

    def perform(self):
        import crafting
        import materials
        from items import Stuff
        fire = self._fire()   # a fire beside you comes first: the fuss over a wreck two tiles away must not stop you lighting it
        site = self._site() if fire is None else None
        if site is not None:
            return self.engine.session.push(handler) if (handler := site.interact(self.entity, self.engine)) else None
        if fire is None:
            raise exceptions.Impossible("There's nothing to interact with here.")
        user, log = self.entity, self.engine.message_log
        fuel = next((i for i in crafting.fuel_candidates(user) if i.form in ("Branch", "Coal")), None)
        own = getattr(fire, "stock", 0)
        if fire.is_lit:
            if fuel is None:
                raise exceptions.Impossible(f"The {fire.kind.object_type.lower()} burns on. You have no fuel to add.")
            burn = materials.burn_turns(fuel.substance)
            user.inventory.remove(fuel)
            fire.add_fuel(burn)
            log.add_message(f"You add {fuel.get_title()} to the fire.", color.orange)
        else:
            if "firestarting" not in crafting.unit_tags(user):
                raise exceptions.Impossible("You need something to strike a spark with: carry a flint or another very hard stone.")
            if own:
                turns = own
                note = ""
            else:
                if fuel is None:
                    raise exceptions.Impossible("The fire needs fuel: carry a branch or some coal to burn.")
                outcome = materials.ignite(fuel.substance, SPARK_TEMPERATURE, self.engine.game_world.planet.oxygen if self.engine.game_world.planet else materials.AMBIENT_OXYGEN)
                if outcome is materials.Burn.NONE:
                    raise exceptions.Impossible(f"{fuel.get_title()} will not catch from a spark: it is too hard to ignite.")
                if outcome is materials.Burn.FLASH:
                    user.inventory.remove(fuel)
                    log.add_message(f"{fuel.get_title()} flares and dies: it cannot sustain a flame in this air.", color.impossible)
                    self.engine.game_world.pass_time(unit=user, time=1)
                    return
                turns = materials.burn_turns(fuel.substance)
                user.inventory.remove(fuel)
                note = f" with {fuel.get_title()}"
            fire.stock = 0
            fire.add_fuel(turns)
            log.add_message(f"You strike a spark and light the {fire.kind.object_type.lower()}{note}. Warm light fills the area.", color.orange)
        self.engine.update_fov()
        self.engine.game_world.pass_time(unit=user, time=1)


SPARK_TEMPERATURE = 450.0
"""Degrees C of a spark struck from a hard stone: enough to ignite anything with flammability >= 3.4."""


PISTOL_RANGE = 9


class FireAction(Action):
    """Fire the wielded pistol at a tile: the first creature on the line of fire is hit (one round used)."""

    def __init__(self, entity: Unit, x: int, y: int):
        super().__init__(entity)
        self.x, self.y = x, y

    def perform(self) -> None:
        import tcod.los
        from damage import resolve
        from items import Ammo
        import species as defs
        user, engine = self.entity, self.engine
        weapon = user.equipment.weapon if user.equipment else None
        if weapon is None or weapon.kind is not defs.PISTOL:
            raise exceptions.Impossible("You are not wielding a pistol.")
        ammo = next((i for i in user.inventory.items if isinstance(i, Ammo) and i.rounds > 0), None)
        if ammo is None:
            raise exceptions.Impossible("You are out of rounds.")
        if (self.x, self.y) == (user.x, user.y):
            raise exceptions.Impossible("You cannot shoot yourself.")
        target = None
        for x, y in tcod.los.bresenham((user.x, user.y), (self.x, self.y)).tolist()[1:PISTOL_RANGE + 1]:
            if not engine.game_map.is_transparent(x, y):
                break
            unit = engine.game_map.get_unit_at_location(x, y)
            if unit is not None and unit is not user and unit.is_alive:
                target = unit
                break
        ammo.rounds -= 1
        if ammo.rounds <= 0:
            user.inventory.remove(ammo)
        from skills import Skill
        bonus = user.skills.level(Skill.MARKSMANSHIP)
        if target is None:
            engine.message_log.add_message("The shot hits nothing.", color.impossible)
        else:
            damage = resolve(user.power + bonus, target.defense, weapon.damage_type, target.resistances())
            engine.message_log.add_message(f"You shoot {target.get_title()} for {damage} {weapon.damage_type} damage.", color.player_atk)
            if damage > 0:
                target.handle_health(-damage, user)
            user.practice(Skill.MARKSMANSHIP, 1)
        engine.game_world.pass_time(unit=user, time=1)


TRACKER_MAX_CHARGES = 5
TRACKER_RECHARGE = 100
"""Turns for one tracker charge to come back."""


def tracker_charges(run, now: int) -> int:
    stored, stamp = run.tracker_charge
    return min(TRACKER_MAX_CHARGES, stored + (now - stamp) // TRACKER_RECHARGE)


class ScanAction(Action):
    """Read what is at a tile with the scanner: the more you know (skills, tags), the more it tells you. One turn."""

    SCAN_RANGE = 8

    def __init__(self, entity: Unit, x: int, y: int):
        super().__init__(entity)
        self.x, self.y = x, y

    def perform(self) -> None:
        import lore
        user, engine = self.entity, self.engine
        if max(abs(self.x - user.x), abs(self.y - user.y)) > self.SCAN_RANGE:
            raise exceptions.Impossible("That is out of scanner range.")
        if not engine.game_map.is_visible(self.x, self.y):
            raise exceptions.Impossible("You cannot see that.")
        self._read(lore.scan(engine, self.x, self.y))

    def _read(self, result) -> None:
        user, engine = self.entity, self.engine
        if result is None:
            raise exceptions.Impossible("There is nothing to scan there.")
        title, learned = result
        engine.game_world.pass_time(unit=user, time=1)
        log = engine.message_log.add_message
        if not learned:
            log(f"Scanner: {title} - nothing new beyond what you know.", color.impossible)
            return
        log(f"Scanner: {title}", color.player_atk)
        run = engine.game_world.run
        import knowledge
        for fact, level in learned:
            label = fact.key.replace("_", " ")
            text = knowledge.format_fact(fact, level)
            suffix = "" if level is knowledge.Know.FULL else " (partial reading)"
            log(f"  {label}: {text}{suffix}" if fact.key != "name" else f"  identified: {text}", color.player_atk)


def _position_of(thing):
    """Where a thing is on the map: its own tile, or that of whatever holds it (a fruit in a plant, a piece in a corpse); (None, None) if nowhere."""
    from components.inventory import Inventory
    for _ in range(5):
        holder = getattr(thing, "parent", None)
        if not isinstance(holder, Inventory):
            break
        thing = holder.parent
    return getattr(thing, "x", None), getattr(thing, "y", None)


class ScanThingAction(ScanAction):
    """Scan one particular thing: an item in a pack, or a body or item in a list of what lies around. One turn; the thing
    has to be in your pack or within the scanner's range."""

    def __init__(self, entity: Unit, thing):
        Action.__init__(self, entity)
        self.thing = thing

    def perform(self) -> None:
        import lore
        user = self.entity
        carried = self.thing in getattr(getattr(user, "inventory", None), "items", ())
        x, y = _position_of(self.thing)
        if not carried and x is not None and max(abs(x - user.x), abs(y - user.y)) > self.SCAN_RANGE:
            raise exceptions.Impossible("That is out of scanner range.")
        self._read(lore.scan(self.engine, 0, 0, entity=self.thing))


class TrackAction(Action):
    """Use the corporate tracker: point toward the nearest marked target within its signal range (costs a charge)."""

    def perform(self) -> None:
        import sponsors
        user, engine = self.entity, self.engine
        caps = user.capabilities
        if not caps.has("target_tracker"):
            raise exceptions.Impossible("You have no tracker.")
        run, now = engine.game_world.run, engine.game_world.current_time
        charges = tracker_charges(run, now)
        if charges <= 0:
            raise exceptions.Impossible("The tracker is recharging.")
        hunts = [c for c in run.contracts if c.is_hunt and not c.done]
        if not hunts:
            raise exceptions.Impossible("You hold no bounty to track.")
        reach = caps.magnitude("target_tracker")
        stored, stamp = run.tracker_charge
        gained = (now - stamp) // TRACKER_RECHARGE
        run.tracker_charge = (TRACKER_MAX_CHARGES - 1, now) if stored + gained >= TRACKER_MAX_CHARGES \
            else (stored + gained - 1, stamp + gained * TRACKER_RECHARGE)
        found = False
        for contract in hunts:
            best = None
            for unit in engine.game_map.actors:
                if unit.category is EntityCategory.UNIT and unit.is_alive and getattr(unit.kind, "key", None) == contract.species_key:
                    d = max(abs(unit.x - user.x), abs(unit.y - user.y))
                    if d <= reach and (best is None or d < best[0]):
                        best = (d, unit)
            if best is None:
                engine.message_log.add_message(f"Tracker: no {contract.label} signal in range.", color.impossible)
                continue
            found = True
            d, unit = best
            dx, dy = unit.x - user.x, unit.y - user.y
            heading = ("N" if dy < 0 else "S" if dy > 0 else "") + ("W" if dx < 0 else "E" if dx > 0 else "")
            engine.message_log.add_message(f"Tracker: {contract.label}, {d} tiles {heading}.", color.orange)
        engine.game_world.pass_time(unit=user, time=1)


BED_SAVE = "savegame_bed"
"""Casual mode: where sleeping in a bed saves the game (death wakes you from this save)."""


class SleepAction(Action):
    """Sleep on a bed next to you: heals, keeps you warmer, and in Casual mode saves the game first. It stops when you are
    hurt, an enemy comes into view, you are starving or dehydrated, or the night is over."""

    MAX_TURNS = 80
    MIN_NEED = 12

    def __init__(self, entity: Unit):
        super().__init__(entity)
        self.slept = 0
        self.hp = None

    def _bed(self):
        world, e = self.engine.game_map, self.entity
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for thing in world.get_entities_at_location(e.x + dx, e.y + dy):
                    if getattr(thing, "station", None) == "bed":
                        return thing
        return None

    def _enemy_in_view(self) -> bool:
        import debug
        if debug.is_god(self.engine):
            return False
        import allegiance
        e = self.entity
        for other in self.engine.game_map.actors:
            if other is e or other.category is not EntityCategory.UNIT or not allegiance.threatens(other, e):
                continue
            if max(abs(other.x - e.x), abs(other.y - e.y)) <= 8 and self.engine.can_see(e.x, e.y, other.x, other.y, 8):
                return True
        return False

    def perform(self):
        user, engine = self.entity, self.engine
        log = engine.message_log
        if self.slept == 0:
            if self._bed() is None:
                raise exceptions.Impossible("You need a bed next to you to sleep. Build one ('R').")
            if self._enemy_in_view():
                raise exceptions.Impossible("You cannot sleep with an enemy in sight.")
            if user.hunger < self.MIN_NEED or user.thirst < self.MIN_NEED:
                raise exceptions.Impossible("You are too hungry or thirsty to sleep.")
            run = engine.game_world.run
            if run.mode == "casual":
                run.bed = (user.x, user.y, engine.game_map.z)
                engine.save_as(BED_SAVE)
                log.add_message("You settle in. Your progress is saved.", color.green)
            else:
                log.add_message("You settle in to sleep.")
            self.hp = user.hp
        elif user.hp < self.hp or self._enemy_in_view() or user.hunger < 4 or user.thirst < 4:
            user.sleeping = False
            log.add_message("You wake up.", color.impossible)
            return False
        user.sleeping = True
        engine.game_world.pass_time(unit=user, time=1)
        user.sleeping = False
        if not user.is_alive or engine.game_world.run.ending:
            return False   # died (or was rescued) in the night: the sleep is over
        self.hp = user.hp
        self.slept += 1
        if self.slept % 3 == 0:
            user.heal(1)
        daylight = __import__("lighting").daylight(engine.game_world.current_time, engine.config)
        if self.slept >= self.MAX_TURNS or (self.slept >= 30 and daylight > 0.6):
            log.add_message("You wake up rested.", color.green)
            return False
        return True


class PlaceConstructableAction(Action):
    """Place a constructable item from inventory onto the map."""

    def __init__(self, entity: Unit, item, dest_x: int, dest_y: int):
        super().__init__(entity)
        self.item = item
        self.dest_x = dest_x
        self.dest_y = dest_y

    def perform(self) -> None:
        # Check distance — must be current tile or adjacent
        dx = abs(self.dest_x - self.entity.x)
        dy = abs(self.dest_y - self.entity.y)
        if dx > 1 or dy > 1:
            raise exceptions.Impossible("Too far away to place that.")

        check = getattr(self.item, "can_place_at", None)
        if check is not None:  # building pieces change the terrain and have their own rules
            reason = check(self.engine.game_map, self.dest_x, self.dest_y)
            if reason:
                raise exceptions.Impossible(reason)
        elif not self.engine.can_move(self.dest_x, self.dest_y):
            # Allow placing on own tile even if "blocked" by self
            if not (self.dest_x == self.entity.x and self.dest_y == self.entity.y):
                raise exceptions.Impossible("Can't place that there.")

        self.item.place_on_map(self.dest_x, self.dest_y, self.engine.game_map)
        self.engine.message_log.add_message(
            f"You build the {self.item.get_title()}." if check is not None else f"You place the {self.item.get_title()}.",
            color.menu_text,
        )
        self.engine.game_world.pass_time(unit=self.entity, time=1)